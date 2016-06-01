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
            abort = false,
            $dropZone = $('.drop-zone'),
            $modalUpload = $('#modal_upload'),
            $form = $modalUpload.find('form'),
            $formCaption = $('#_caption'),
            $formPassword = $('#_password'),
            $formPermanent = $('#_permanent'),
            $formSubmit = $modalUpload.find(':submit'),
            $uploadList = $modalUpload.find('.upload-list'),
            $uploadItem = $uploadList.find('.upload-item').detach(),
            $uploadProgress = $modalUpload.find('.upload-progress'),
            $uploadProgressBar = $uploadProgress.find('.progress-bar'),
            $uploadSpeed = $uploadProgress.find('.upload-speed'),
            $uploadSize = $uploadProgress.find('.upload-size'),
            $storageUpload = $('.storage-upload'),
            $storageList = $('.storage-list'),
            $storageTotal = $('.storage-total'),
            $storageItem = $storageList.find('.storage-item').show().detach(),
            $storageEmpty = $storageList.find('.storage-empty').detach(),
            apiStorage = $storageList.data('api');

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
            $modalUpload.modal('hide');
        };

        this.loadUsers = function() {
            $.getJSON(apiStorage).done(function(data) {
                if (!data.files || !Array.isArray(data.files))
                    return;

                $storageList.empty();
                var len = data.files.length;
                if (len === 0)
                    return $storageEmpty.appendTo($storageList);

                for (var i = 0; i < len; i++) {
                    var item = data.files[i];
                    $storageItem.clone()
                        .find('.storage-lock')
                            .toggle(!!item.password)
                            .tooltip().end()
                        .find('.storage-name')
                            .text(item.name)
                            .prop({ title: item.caption || item.name, href: '/dl/' + item.key })
                            .on('click', function() {
                                if (window.prompt('The URL for sharing:', this.href) !== this.href)
                                    return false;
                            }).tooltip().end()
                        .find('.storage-size')
                            .text(_self.size(item.size))
                            .prop('title', _self.format(item.size) + ' bytes')
                            .tooltip().end()
                        .find('.storage-created')
                            .text(item.created_at)
                            .prop('title', 'Expires at: ' + (item.expires_at || '(never)') +
                                  '<br>Downloaded ' + (item.downloads === 1 ? 'once' : item.downloads + ' times'))
                            .toggleClass('text-danger', !item.expires_at)
                            .tooltip({ html: true }).end()
                        .attr('data-key', item.key)
                        .appendTo($storageList);
                }
            }).always(function() {
                $storageTotal.text('Total: ' + $('.storage-item').length);
            });
        };

        $storageList.on('click', '.status-info', function() {
            var key = $(this).closest('.storage-item').data('key');

            $.getJSON(apiStorage + '/' + key).done(function(item) {
                _sharedown.modal(item.name, '<dl class="dl-horizontal">' +
                    '<dt>Key:</dt><dd>' + item.key + '</dd>' +
                    '<dt>Name:</dt><dd>' + item.name + '</dd>' +
                    '<dt>Size:</dt><dd><abbr title="' + _self.format(item.size) +
                        ' bytes">' + _self.size(item.size) + '</abbr></dd>' +
                    '<dt>Created at:</dt><dd>' + item.created_at + '</dd>' +
                    '<dt>Expires at:</dt><dd>' + (item.expires_at || '<i>never</i>') + '</dd>' +
                    '<dt>User:</dt><dd>' + (item.login || '<i>deleted</i>') + '</dd>' +
                    '<dt>Password:</dt><dd>' + (item.password || '<s>no password</s>') + '</dd>' +
                    '<dt>Caption:</dt><dd>' + (item.caption || '<s>no caption</s>') + '</dd>' +
                    '<dt>Downloads:</dt><dd>' + item.downloads + '</dd>' +
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
                }).done(_self.loadUsers).fail(function() {
                    setTimeout(function() {
                        _sharedown.modal('Error', 'Failed to delete the item from the storage.');
                    }, 500);
                }).always(_sharedown.ajax_stop);
            });
        });

        $modalUpload.on({
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


                $formPassword.prop('disabled', false).val(_self.random_bytes(8));
                $formPermanent.prop({ disabled: false, checked: false });
                $formCaption.prop('disabled', files.length !== 1).val('');
                $formSubmit.prop('disabled', false);
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

        $form.on('submit', function() {
            var data = _self.serialize($form.serializeArray()),
                _files = data['_files[]'],
                fsize = _self.size(size),
                time = +new Date(),
                requests = 0,
                loaded = 0,
                defers = [],
                failed = [];

            if (!Array.isArray(_files))
                _files = [_files];

            $.each(_files, function(i, index) {
                var $item = $uploadList.children(':has(:hidden[value=' + index + '])'),
                    file = files[index];

                defers.push($.ajax({
                    type: 'POST',
                    data: file,
                    url: $form.prop('action'),
                    headers: {
                        'X-Name': file.name,
                        'X-Caption': data._caption,
                        'X-Password': data._password,
                        'X-Permanent': data._permanent
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

                            var csize = loaded + e.loaded,
                                ctime = +new Date() - time,
                                progress = csize / size * 100,
                                tms = ctime / csize * (size - csize);

                            $item.addClass('upload');
                            $uploadProgressBar.css('width', progress + '%').text(Math.round(progress) + '%');
                            $uploadSpeed.text(_self.size(csize / ctime * 1e3) + '/s ~ ' + _self.time(tms));
                            $uploadSize.text(_self.size(csize) + ' / ' + fsize);
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
                }));
            });

            $formPassword
                .add($formCaption)
                .add($formPermanent)
                .prop('disabled', true);

            $uploadProgress.show();

            $.when.apply($, defers).done(function() {
                _self.hideModalUpload();
                _self.loadUsers();
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
                    files.length && $modalUpload.modal();
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

            files.length && $modalUpload.modal();
            this.value = '';
        });

        $(this.loadUsers);
    };
})(window, jQuery);
