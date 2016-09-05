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
            $formLogin = $('#_login'),
            $formPassword = $('#_password'),
            $formEnabled = $form.find('[name="is_enabled"]'),
            $formLevel = $form.find('[name="level"]'),
            $usersList = $('.users-list'),
            $usersTotal = $('.users-total'),
            $usersItem = $usersList.find('.users-item').show().detach(),
            $usersTokenGroup = $('.users-token-group'),
            $usersTokenShow = $('.users-token-show'),
            $usersTokenUpdate = $('.users-token-update'),
            $usersTokenDelete = $('.users-token-delete'),
            apiUsers = $usersList.data('api');

        this.loadUsers = function() {
            $.getJSON(apiUsers).done(function(data) {
                if (!data.users || !Array.isArray(data.users))
                    return;

                $usersList.empty();
                $.each(data.users, function(_, item) {
                    $usersItem.clone()
                        .find('.users-token')
                                .attr('title', (item.has_token ? 'Has' : 'No') + ' API token')
                                .toggleClass('text-muted-2', !item.has_token).end()
                        .find('.users-feed')
                            .each(function() {
                                if (item.has_feed)
                                    $(this).prop('href', '/feed/' + item.login);
                                else
                                    $(this).attr('title', 'Feed is disabled').addClass('text-muted-2');
                            }).end()
                        .find('.users-login')
                            .text(function() {
                                if (!item.is_enabled)
                                    $(this).wrap('<s>');
                                return item.login;
                            }).end()
                        .find('.users-level')
                            .text(item.level).end()
                        .find('.users-storage > *')
                            .text(item.files + (item.files !== 1 ? ' files' : ' file'))
                            .prop('href', '/web/?login=' + item.login).end()
                        .find('.users-activity')
                            .html(item.activity_at || '&mdash;').end()
                        .find('.users-created')
                            .text(item.created_at).end()
                        .find('[title]')
                            .tooltip().end()
                        .attr('data-login', item.login)
                        .addClass(
                            item.level === 'SUPER' ? 'danger' :
                            item.level === 'ADMIN' ? 'warning' : ''
                        )
                        .appendTo($usersList);
                });
            }).always(function() {
                $usersTotal.text('Total: ' + $('.users-item').length);
            });
        };

        $modal.on({
            'show.bs.modal': function(e) {
                var $button = $(e.relatedTarget),
                    login = $button.closest('[data-login]').data('login'),
                    submit_only = true;

                if (login) {
                    $usersTokenGroup.find('a').data('href', apiUsers + '/' + login + '/token').end().show();
                    $form.prop({ action: apiUsers + '/' + login, method: 'PATCH' }).data('message',
                        'User "' + login + '" details were successfully updated.');
                    $formPassword.prop('required', false);
                    submit_only = false;
                } else {
                    $form.prop({ action: apiUsers, method: 'POST' }).data('message',
                        'User was successfully created.');
                    $formPassword.prop('required', true);
                    $usersTokenGroup.hide();
                }

                _sharedown.form_dynamic($form[0], function() {
                    $modal.modal('hide');
                    _self.loadUsers();
                }, submit_only);
            },
            'hide.bs.modal': function() {
                $formLevel.filter(':first').add($formEnabled).prop('checked', true);
                $formLogin.add($formPassword).val('').trigger('keyup');
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

        $usersTokenShow.on('click', function() {
            $.getJSON($(this).data('href')).done(function(data) {
                _sharedown.modal('API Token', data.token ? '<pre>' + data.token + '</pre>' :
                    'User does not have any API token configured.');
            });
            return false;
        });

        $usersTokenUpdate.on('click', function() {
            if (window.confirm("Do you really want to UPDATE the user's API token?"))
                $.post($(this).data('href')).done(function(data) {
                    _sharedown.modal('New API Token', '<p>API token was successfully updated. The new token is:</p>' +
                        '<pre>' + data.token + '</pre>');
                });
            return false;
        });

        $usersTokenDelete.on('click', function() {
            if (window.confirm("Do you really want to DELETE the user's API token?"))
                $.ajax($(this).data('href'), { method: 'DELETE' }).done(function() {
                    _sharedown.modal('API Token Deleted', 'API token was successfully deleted.');
                });
            return false;
        });

        $(this.loadUsers);
    };
})(window, jQuery);
