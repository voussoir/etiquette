import flask; from flask import request
import functools

from voussoirkit import vlogging

import etiquette

log = vlogging.getLogger(__name__)

class PermissionManager:
    def __init__(self, site):
        self.site = site

    def admin_only(self):
        if request.is_localhost:
            request.checked_permissions = True
            return True
        elif request.session.user and request.session.user.has_permission(etiquette.constants.PERMISSION_ADMIN):
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def localhost_only(self):
        if request.is_localhost:
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def logged_in(self, user=None):
        '''
        Require that the visitor be logged in as any user, or as one
        specific user.
        '''
        if request.session and request.session.user and user is None:
            request.checked_permissions = True
            return True
        if request.session and request.session.user and request.session.user == user:
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def early_read(self):
        '''
        This method does not set request.checked_permissions and must be used
        along with one of the other checks. However, this check can act as a
        cheap blocker against logged-out users before the caller wastes any time
        loading items from the database to check more specific permissions.
        For example, it is used by several of the bulk endpoints before checking
        any of the individual items.
        '''
        if request.is_localhost:
            return True
        elif self.site.server_config['anonymous_read'] or request.session.user:
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def edit_thing(self, thing):
        if request.is_localhost:
            request.checked_permissions = True
            return True
        elif request.session.user and request.session.user.has_object_permission(thing, 'edit'):
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def delete_thing(self, thing):
        if request.is_localhost:
            request.checked_permissions = True
            return True
        elif request.session.user and request.session.user.has_object_permission(thing, 'delete'):
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def permission_string(self, permission_string):
        '''
        Require that the user has this specific permission string (mostly for
        the CREATE permissions rather than edit/delete permissions).
        '''
        if request.is_localhost:
            request.checked_permissions = True
            return True
        elif request.session.user and permission_string in request.session.user.get_permissions():
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def read(self):
        '''
        BE CAREFUL WITH CACHED ENDPOINTS. Use read_decorator instead.
        '''
        if request.is_localhost:
            request.checked_permissions = True
            return True
        elif self.site.server_config['anonymous_read'] or request.session.user:
            request.checked_permissions = True
            return True
        else:
            raise etiquette.exceptions.Unauthorized()

    def read_decorator(self, endpoint):
        '''
        Make sure to place read_decorator ABOVE the cached_endpoint decorator so
        Python runs this one first.
        '''
        log.debug('Decorating %s with basic_decorator.', endpoint)
        @functools.wraps(endpoint)
        def wrapped(*args, **kwargs):
            self.read()
            return endpoint(*args, **kwargs)
        return wrapped

    def global_public(self):
        '''
        This check always passes. Use this for the root and login page so people
        can log in.
        '''
        request.checked_permissions = True
        return True
