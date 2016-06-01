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
        };

        this._ajax_setup = function() {
            $document.ajaxStart(_self.ajax_start).ajaxStop(_self.ajax_stop).ajaxError(function() {
                _self.modal('Internal Error', 'Failed to load contents from the server.');
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

            $('form [maxlength]:not(.js-x-length)').each(function() {
                var $this = $(this),
                    limit = $this.attr('maxlength'),
                    $limit = $('<small />', {
                        'class': 'help-block bg-warning',
                        text: 'Maximum ' + limit + ' characters'
                    }).appendTo($this.closest('.form-group'));

                $this.on('keyup', function() {
                    $limit.text(limit - this.value.length + ' characters left');
                });
            }).addClass('js-x-length');

            $('form:not(.js-dynamic)').on('submit', function() {
                $(':submit', this).prop('disabled', true);
            });

            $('form.js-dynamic').each(function() {
                _self.form_dynamic(this);
            });
        };

        this._tooltips = function(parent, selector) {
            $(selector || '[title]', parent).tooltip({ container: 'body' });
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

        this.download = function(url) {
            if (!url)
                return;

            setTimeout(function() {
                window.location = url;
            }, 1000);
        };

        this.form_dynamic = function(form, callback, partial) {
            var $form = $(form);

            if (!partial)
                $.getJSON(form.action).done(function(data) {
                    $.each(data, function(key, value) {
                        var $input = $('[name="' + key + '"]', form);
                        switch ($input.prop('type')) {
                            case 'radio':
                                $input = $input.filter('[value="' + value + '"]');
                            case 'checkbox':
                                $input.prop('checked', true).closest('label').addClass('active');
                                break;
                            default:
                                $input.val(value);
                        }
                    });
                });

            $form.off().on('submit', function() {
                $.ajax({
                    url: form.action,
                    method: $form.attr('method'),
                    data: $form.serialize()
                }).done(function() {
                    _self.modal('Success', $form.data('message'), callback, 'success');
                });
                return false;
            });
        };

        $(this.load);
    };
})(window, document, jQuery);
