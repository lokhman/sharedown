/*!
 * Sharedown
 *
 * @author  Alexander Lokhman
 * @email   alex.lokhman@gmail.com
 * @link    https://github.com/lokhman/sharedown
 */
(function(window, document, $) {
    'use strict';

    window.Sharedown = new function() {
        var _self = this;

        if ('Sharedown' in window)
            return window.Sharedown;

        var $document = $(document),
            $loader = $('.loader');

        this.load = function() {
            _self._ajax_setup();
            _self._form_setup();
            _self._warnings();
            _self._tooltips();

            if (_self.get_login())
                _self._timeout();
        };

        this._ajax_setup = function() {
            var message = 'Failed to load contents from the server.';
            $document.ajaxStart(_self.ajax_start).ajaxStop(_self.ajax_stop).ajaxError(function(_, jqXHR) {
                switch (jqXHR.status) {
                    case 400:
                    case 404:
                        message = 'Parameters sent to the server are incorrect.';
                        break;
                    case 409:
                        message = 'Submitted parameters are conflicting with the existing data.';
                        break;
                    case 503:
                        message = 'Service is currently unavailable. Try again later.'
                }
                _self.modal(jqXHR.statusText, message);
            });
        };

        this.ajax_start = function() {
            $loader.show();
        };

        this.ajax_stop = function() {
            $loader.hide();
        };

        this._form_setup = function() {
            $('form, form :input:not([autocomplete])').attr('autocomplete', 'off');

            $('form [maxlength]').each(function() {
                var $this = $(this),
                    limit = $this.attr('maxlength'),
                    $limit = $('<small />', {
                        'class': 'help-block bg-warning',
                        text: 'Maximum ' + limit + ' characters'
                    }).appendTo($this.closest('.form-group'));

                $this.on('keyup', function() {
                    $limit.text(limit - this.value.length + ' characters left');
                });
            });

            $('form:not(.js-dynamic)').on('submit', function() {
                $(':submit', this).prop('disabled', true);
            });

            $('form.js-dynamic').each(function() {
                _self.form_dynamic(this, undefined, $(this).data('submit-only'));
            });
        };

        this._tooltips = function() {
            $('[title]').tooltip({ container: 'body' });
        };

        this.get_login = function() {
            return $('[data-login]').data('login');
        };

        this.modal = function(title, body, action, button) {
            $('#modal')
                .find('.modal-title').html(title).end()
                .find('.modal-body').html(body).end()
                .find('.btn:last').removeClass()
                .addClass('btn btn-' + (button || 'danger'))
                .off().one('click', function() {
                    $('#modal').modal('hide');
                    switch (typeof action) {
                        case 'function': action(); break;
                        case 'string': window.location.href = action;
                    }
                }).end().modal();
            return false;
        };

        this._warnings = function() {
            $document.on('click', '[data-warning]', function() {
                return _self.modal('Warning', $(this).data('warning'), this.href);
            });
        };

        this.download = function(url, sec) {
            if (!url)
                return;

            setTimeout(function() {
                window.location = url;
            }, (sec || 1) * 1000);
        };

        this.form_dynamic = function(form, callback, submit_only) {
            var $form = $(form);

            if (!submit_only)
                $.getJSON(form.action).done(function(data) {
                    $.each(data, function(key, value) {
                        if (typeof value === 'boolean')
                            value = +value;

                        $('[name="' + key + '"]', form).each(function() {
                            var $this = $(this);
                            if ($this.data('mapped') === false)
                                return;

                            switch ($this.prop('type')) {
                                case 'radio':
                                    $this = $this.filter('[value="' + value + '"]');
                                    $this.closest('label').addClass('active')
                                        .siblings('.active').removeClass('active');
                                    $this.prop('checked', true);
                                    break;
                                case 'checkbox':
                                    $this.filter('[value="' + value + '"]')
                                        .prop('checked', true);
                                    break;
                                default:
                                    $this.val(value);
                            }
                        });
                    });
                });

            $form.off().on('submit', function() {
                $.ajax({
                    url: form.action,
                    method: $form.attr('method'),
                    data: $form.serialize()
                }).done(function() {
                    var $visible = $('.modal:visible');
                    if ($visible.length > 0)
                        $visible.modal('hide');
                    _self.modal('Success', $form.data('message'), callback, 'success');
                });
                return false;
            });
        };

        this._timeout = function() {
            setTimeout(function() {
                $.ajax({
                    method: 'GET',
                    url: '/api/auth',
                    global: false
                }).done(function() {
                    _self._timeout();
                }).fail(function() {
                    window.location.reload();
                });
            }, 300 * 1e3);
        };

        $document.on({
            dragover: function() {
                return false;
            },
            drop: function(e) {
                if (e.originalEvent.dataTransfer.files.length === 0)
                    return false;
                if (confirm('Please drop your files only in the Storage section.\nDo you want to be redirected there?'))
                    window.location.assign('/');
                return false;
            }
        });

        $(this.load);
    };
})(window, document, jQuery);
