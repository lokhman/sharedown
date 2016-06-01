/*!
 * Sharedown
 *
 * @author  Alexander Lokhman
 * @email   alex.lokhman@gmail.com
 * @link    https://github.com/lokhman/sharedown
 */
(function(window, $) {
    'use strict';

    window.Sharedown.Users = new function() {
        var _sharedown = window.Sharedown,
            _self = this;

        if ('Users' in _sharedown)
            return _sharedown.Users;

        var $modal = $('#modal_user'),
            $form = $modal.find('form'),
            $formLogin = $form.find('#_login'),
            $formPassword = $form.find('#_password'),
            $formEnabled = $form.find('[name="is_enabled"]'),
            $formLevel = $form.find('[name="level"]'),
            $usersList = $('.users-list'),
            $usersTotal = $('.users-total'),
            $usersItem = $usersList.find('.users-item').show().detach(),
            apiUsers = $usersList.data('api');

        this.loadUsers = function() {
            $.getJSON(apiUsers).done(function(data) {
                if (!data.users || !Array.isArray(data.users))
                    return;

                $usersList.empty();
                for (var i = 0, len = data.users.length; i < len; i++) {
                    var item = data.users[i];
                    $usersItem.clone()
                        .find('.users-feed')
                            .prop('href', '/feed/' + item.login)
                            .toggle(!!item.has_feed)
                            .tooltip().end()
                        .find('.users-login')
                            .text(function() {
                                if (!item.is_enabled)
                                    $(this).wrap('<s>');
                                return item.login;
                            }).end()
                        .find('.users-storage')
                            .text(item.files + (item.files !== 1 ? ' files' : ' file')).end()
                        .find('.users-level')
                            .text(item.level).end()
                        .find('.users-activity')
                            .html(item.activity_at || '&mdash;').end()
                        .find('.users-created')
                            .text(item.created_at).end()
                        .attr('data-login', item.login)
                        .appendTo($usersList);
                }
            }).always(function() {
                $usersTotal.text('Total: ' + $('.users-item').length);
            });
        };

        $modal.on({
            'show.bs.modal': function(e) {
                var $button = $(e.relatedTarget),
                    login = $button.closest('[data-login]').data('login'),
                    partial = true;

                if (login) {
                    $form.prop({ action: apiUsers + '/' + login, method: 'PATCH' }).data('message',
                        'User "' + login + '" details were successfully updated.');
                    $formPassword.prop('required', false);
                    partial = false;
                } else {
                    $form.prop({ action: apiUsers, method: 'POST' }).data('message',
                        'User was successfully created.');
                    $formPassword.prop('required', true).add($formLogin).val('');
                    $formLevel.filter(':first').add($formEnabled).prop('checked', true);
                }

                _sharedown.form_dynamic($form[0], function() {
                    $modal.modal('hide');
                    _self.loadUsers();
                }, partial);

                $formPassword.val('');
            }
        });

        $usersList.on('click', '.users-delete', function() {
            var login = $(this).closest('.users-item').data('login');

            _sharedown.modal('Delete', 'Do you want to delete this user?', function() {
                $.ajax(apiUsers + '/' + login, {
                    type: 'DELETE',
                    global: false
                }).done(_self.loadUsers).fail(function() {
                    setTimeout(function() {
                        _sharedown.modal('Error', 'Failed to delete the user from the system.');
                    }, 500);
                });
            });
        });

        $(this.loadUsers);
    };
})(window, jQuery);
