/*!
 * Sharedown
 *
 * @author  Alexander Lokhman
 * @email   alex.lokhman@gmail.com
 * @link    https://github.com/lokhman/sharedown
 */
(function(window, $) {
    'use strict';

    window.Sharedown.Storage = new function() {
        var _sharedown = window.Sharedown,
            _self = this;

        if ('Storage' in _sharedown)
            return _sharedown.Storage;

        if (typeof window.FileReader === 'undefined')
            return _sharedown.modal('Browser', 'Your browser is not supported here.');

        var size = 0,
            files = [],
            folders = [],
            abort = false,

            $dropZone = $('.drop-zone'),

            $editModal = $('#modal_edit'),
            $editForm = $editModal.find('form'),
            $editPublic = $('#_edit_public'),
            $editFolder = $('#_edit_folder'),
            $editCaption = $('#_edit_caption'),
            $editPassword = $('#_edit_password'),
            $editPermanent = $('#_edit_permanent'),
            $editTitle = $editModal.find('.modal-title'),

            $uploadModal = $('#modal_upload'),
            $uploadForm = $uploadModal.find('form'),
            $uploadPublic = $('#_upload_public'),
            $uploadFolder = $('#_upload_folder'),
            $uploadCaption = $('#_upload_caption'),
            $uploadPassword = $('#_upload_password'),
            $uploadPermanent = $('#_upload_permanent'),
            $uploadSubmit = $uploadModal.find(':submit'),
            $uploadList = $uploadModal.find('.upload-list'),
            $uploadItem = $uploadList.find('.upload-item').detach(),
            $uploadProgress = $uploadModal.find('.upload-progress'),
            $uploadProgressBar = $uploadProgress.find('.progress-bar'),
            $uploadSpeed = $uploadProgress.find('.upload-speed'),
            $uploadSize = $uploadProgress.find('.upload-size'),

            $storageUpload = $('.storage-upload'),
            $storageList = $('.storage-list'),
            $storageTotal = $('.storage-total'),
            $storageFolder = $storageList.find('.storage-folder').show().detach(),
            $storageItem = $storageList.find('.storage-item').show().detach(),
            $storageEmpty = $storageList.find('.storage-empty').detach(),

            apiStorage = $storageList.data('api'),
            login = _sharedown.get_login();

        this.format = function(integer) {
            return (integer + '').replace(/(\d)(?=(\d{3})+$)/g, '$1,');
        };

        this.size = function(bytes) {
            if (!bytes)
                return '0 bytes';

            var i = Math.log(bytes) / Math.log(1024) | 0;
            return +(bytes / Math.pow(1024, i)).toFixed(2) +
                ' ' + ['bytes', 'KB', 'MB', 'GB', 'TB'][i];
        };

        this.time = function(ms) {
            return new Date(ms).toTimeString().split(' ')[0];
        };

        this.serialize = function(array) {
            return array.reduce(function(o, item) {
                if (item.name in o) {
                    if (!Array.isArray(o[item.name]))
                        o[item.name] = [o[item.name]];
                    o[item.name].push(item.value);
                } else
                    o[item.name] = item.value;
                return o;
            }, {});
        };

        this.random_bytes = function(len) {
            for (var output = ''; len > 0; len -= 8)
                output += Math.random().toString(36).slice(-Math.min(len, 8));
            return output;
        };

        this.hideModalUpload = function() {
            abort = true;
            $uploadModal.modal('hide');
        };

        this.loadStorage = function() {
            $.getJSON(apiStorage + window.location.search).done(function(data) {
                if (!data.files || !Array.isArray(data.files))
                    return;

                $storageList.empty();
                if (data.files.length === 0)
                    return $storageEmpty.appendTo($storageList);

                var _folders = data.files.reduce(function(map, file) {
                    var folder = file.folder || '';
                    if (file.login !== login)
                        folder = '{' + file.login + '} ' + folder;
                    folder = folder.trim();
                    if (!(folder in map))
                        map[folder] = [];
                    map[folder].push(file);
                    return map;
                }, {});

                folders.length = 0;
                folders.push.apply(folders, Object.keys(_folders).sort());

                $.each(folders, function(_, folder) {
                    folder && $storageFolder.clone()
                        .find('div').html(function() {
                                return folder.replace(/^{([^}]+)}/,
                                    '<a href="?login=$1"><mark>$1</mark></a>');
                            }).end()
                        .appendTo($storageList);

                    $.each(_folders[folder], function(_, item) {
                        $storageItem.clone()
                            .find('.storage-lock')
                                .attr('title', item.password ? 'Password protected' : 'Unprotected')
                                .toggleClass('text-muted-2', !item.password).end()
                            .find('.storage-public')
                                .attr('title', (item.is_public ? 'A' : 'Una') + 'vailable in feed')
                                .toggleClass('text-muted-2', !item.is_public).end()
                            .find('.storage-name')
                                .text(item.name)
                                .attr({ title: item.caption || item.name, href: '/dl/' + item.key })
                                .on('click', function() {
                                    if (window.prompt('The URL for sharing:', this.href) !== this.href)
                                        return false;
                                }).end()
                            .find('.storage-size')
                                .text(_self.size(item.size))
                                .attr('title', _self.format(item.size) + ' bytes').end()
                            .find('.storage-created')
                                .text(item.created_at)
                                .attr('title', 'Expires at: ' + (item.expires_at || '(never)') +
                                      '<br>Downloaded ' + (item.downloads === 1 ? 'once' : item.downloads + ' times'))
                                .toggleClass('text-danger', !item.expires_at)
                                .tooltip({ html: true }).end()
                            .find('[title]')
                                .tooltip().end()
                            .attr('data-key', item.key)
                            .appendTo($storageList);
                    });
                });
            }).always(function() {
                $storageTotal.text('Total: ' + $('.storage-item').length);
            });
        };

        $uploadFolder.add($editFolder).typeahead({ source: folders });

        $storageList.on('click', '.status-info', function() {
            var key = $(this).closest('.storage-item').data('key');
            $.getJSON(apiStorage + '/' + key).done(function(item) {
                _sharedown.modal(item.name, '<dl class="dl-horizontal">' +
                    '<dt>Key:</dt><dd>' + item.key + '</dd>' +
                    '<dt>Name:</dt><dd>' + item.name + '</dd>' +
                    '<dt>Size:</dt><dd><abbr title="' + _self.format(item.size) +
                        ' bytes">' + _self.size(item.size) + '</abbr></dd>' +
                    '<dt>User:</dt><dd>' + (item.login || '<s>deleted</s>') + '</dd>' +
                    '<dt>Folder:</dt><dd>' + (item.folder || '<s>default</s>') + '</dd>' +
                    '<dt>Caption:</dt><dd>' + (item.caption || '<s>no caption</s>') + '</dd>' +
                    '<dt>Password:</dt><dd class="text-danger">' + (item.password || '<s>no password</s>') + '</dd>' +
                    '<dt>Feed status:</dt><dd>' + (item.is_public ? 'displayed' : 'hidden') + '</dd>' +
                    '<dt>MIME type:</dt><dd>' + item.mimetype + '</dd>' +
                    '<dt>Created at:</dt><dd>' + item.created_at + '</dd>' +
                    '<dt>Expires at:</dt><dd>' + (item.expires_at || '<s>never</s>') + '</dd>' +
                    '<dt>Downloads:</dt><dd style="margin-bottom: 10px;">' + item.downloads + '</dd>' +
                    Object.keys(item.metadata).sort().map(function(attribute) {
                        return '<dt>[' + attribute + ']:</dt><dd>' + item.metadata[attribute] + '</dd>';
                    }).join('') +
                '</dl>');
            });
        });

        $storageList.on('click', '.storage-delete', function() {
            var key = $(this).closest('.storage-item').data('key');

            _sharedown.modal('Delete', 'Do you want to delete this file?', function() {
                _sharedown.ajax_start();
                $.ajax(apiStorage + '/' + key, {
                    type: 'DELETE',
                    global: false
                }).done(_self.loadStorage).fail(function() {
                    setTimeout(function() {
                        _sharedown.modal('Error', 'Failed to delete the item from the storage.');
                    }, 500);
                }).always(_sharedown.ajax_stop);
            });
        });

        $uploadModal.on({
            'show.bs.modal': function() {
                if (!files.length)
                    return;

                size = 0;
                abort = false;
                $uploadList.empty();
                for (var i = 0, len = files.length; i < len; i++) {
                    var file = files[i];
                    size += file.size;
                    $uploadItem.clone()
                        .attr('data-text', file.name + ' [' + _self.size(file.size) + ']')
                        .find(':hidden').val(i).end()
                        .appendTo($uploadList);
                }

                $uploadPermanent.add($uploadPublic).prop({ disabled: false, checked: false });
                $uploadPassword.prop('disabled', false).val(_self.random_bytes(8));
                $uploadCaption.prop('disabled', files.length !== 1).val('');
                $uploadFolder.prop('disabled', false).val('');
                $uploadSubmit.prop('disabled', false);
                $uploadProgressBar.css('width', 0);
                $uploadProgress.hide();
            },
            'hide.bs.modal': function() {
                if (!abort)
                    return _sharedown.modal('Cancel', 'Are you sure that you want to cancel the upload?',
                        _self.hideModalUpload);

                files = [];
            }
        });

        $uploadForm.on('submit', function() {
            var data = _self.serialize($uploadForm.serializeArray()),
                _files = data['_upload_files[]'],
                fsize = _self.size(size),
                time = +new Date(),
                requests = 0,
                loaded = 0,
                defers = [],
                failed = [],
                ltime = 0;

            if (!Array.isArray(_files))
                _files = [_files];

            $.each(_files, function(i, index) {
                var $item = $uploadList.children(':has(:hidden[value=' + index + '])'),
                    file = files[index];

                defers.push($.ajax({
                    type: 'PUT',
                    data: file,
                    url: $uploadForm.prop('action'),
                    headers: {
                        'X-SF-Name': file.name,
                        'X-SF-Folder': data._folder,
                        'X-SF-Caption': data._caption,
                        'X-SF-Password': data._password,
                        'X-SF-Permanent': data._permanent,
                        'X-SF-Public': data._public
                    },
                    global: false,
                    processData: false,
                    contentType: false,
                    xhr: function() {
                        var xhr = $.ajaxSettings.xhr();
                        xhr.upload.onprogress = function(e) {
                            if (abort)
                                xhr.abort();

                            if (!e.lengthComputable)
                                return;

                            var now = +new Date();
                            if (now - ltime < 100)
                                return /* Safari sleep */;

                            var csize = loaded + e.loaded,
                                progress = csize / size * 100;

                            $item.addClass('upload');
                            $uploadProgressBar.css('width', progress + '%').text(Math.round(progress) + '%');
                            $uploadSize.text(_self.size(csize) + ' / ' + fsize);

                            if (progress < 100) {
                                var ctime = now - time,
                                    tms = ctime / csize * (size - csize);

                                $uploadSpeed.text(_self.size(csize / ctime * 1e3) + '/s ~ ' + _self.time(tms));
                            } else
                                $uploadSpeed.text('Processing files, please wait...');

                            ltime = now;
                        };
                        return xhr;
                    }
                }).done(function() {
                    loaded += file.size;
                    $item.removeClass('upload').addClass('done text-success');
                }).fail(function() {
                    failed.push(file.name);
                    $item.removeClass('upload').addClass('error text-danger');
                }).always(function() {
                    if (++requests < defers.length || !failed.length)
                        return;  // $.when.fail() won't work!

                    if (!abort)
                        _sharedown.modal('Error', 'The following files failed to upload:<ul class="text-danger"><li>' +
                            failed.join('</li><li>') + '</li></ul>Please try again later.');

                    _self.hideModalUpload();

                    if (failed.length < defers.length)
                        _self.loadStorage();
                }));
            });

            $uploadPassword
                .add($uploadPublic)
                .add($uploadFolder)
                .add($uploadCaption)
                .add($uploadPermanent)
                .prop('disabled', true);

            $uploadProgress.show();

            $.when.apply($, defers).done(function() {
                _self.hideModalUpload();
                _self.loadStorage();
            });

            return false;
        });

        $uploadList.on('click', '.close', function() {
            if ($uploadList.children().length > 1)
                $(this.parentNode).remove();
            return false;
        });

        $('html').has($dropZone).on('dragenter', function() {
            $dropZone.show();
        });

        $dropZone.on({
            dragover: function() {
                return false;
            },
            dragleave: function() {
                $dropZone.hide();
            },
            drop: function(e) {
                $dropZone.hide();
                if (files.length)
                    return false;

                $.when.apply($, $.map(e.originalEvent.dataTransfer.files, function(file) {
                    var defer = $.Deferred(), reader;

                    if (file.size === 0) {
                        // deny empty files
                        defer.resolve();
                    } else if (file.size < 1048576) {
                        // check for folders
                        reader = new FileReader();
                        reader.onload = function () {
                            files.push(file);
                            defer.resolve();
                        };
                        reader.onerror = function () {
                            defer.resolve();
                        };
                        reader.readAsDataURL(file);
                    } else {
                        files.push(file);
                        defer.resolve();
                    }

                    return defer.promise();
                })).done(function() {
                    files.length && $uploadModal.modal();
                });

                return false;
            }
        });

        $storageUpload.on('change', function() {
            files = [];

            for (var i = 0, len = this.files.length; i < len; i++) {
                var file = this.files[i];
                if (file.size)
                    files.push(file);
            }

            files.length && $uploadModal.modal();
            this.value = '';
        });

        $editModal.on({
            'show.bs.modal': function(e) {
                var $button = $(e.relatedTarget),
                    $container = $button.closest('[data-key]'),
                    name = $container.find('.storage-name').text(),
                    key = $container.data('key');

                $editForm.prop({ action: apiStorage + '/' + key, method: 'PATCH' }).data('message',
                    'File "' + name + '" was successfully updated.');
                $editTitle.text(name);

                _sharedown.form_dynamic($editForm[0], function() {
                    $editModal.modal('hide');
                    _self.loadStorage();
                });
            },
            'hide.bs.modal': function() {
                $editPassword
                    .add($editCaption)
                    .add($editFolder)
                    .val('').trigger('keyup');

                $editPermanent
                    .add($editPublic)
                    .prop('checked', false);
            }
        });

        $(this.loadStorage);
    };
})(window, jQuery);
