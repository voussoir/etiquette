import flask; from flask import request
import functools

from voussoirkit import vlogging

log = vlogging.getLogger(__name__)

class PermissionManager:
    def __init__(self, site):
        self.site = site

    def admin(self):
        if request.is_localhost:
            request.checked_permissions = True
            return True
        else:
            return flask.abort(403)

    def basic(self):
        if request.method not in {'GET', 'POST'}:
            return flask.abort(405)
        elif request.is_localhost:
            request.checked_permissions = True
            return True
        elif request.method == 'GET' and self.site.server_config['anonymous_read'] or request.session.user:
            request.checked_permissions = True
            return True
        elif request.method == 'POST' and self.site.server_config['anonymous_write'] or request.session.user:
            request.checked_permissions = True
            return True
        else:
            return flask.abort(403)

    def basic_decorator(self, endpoint):
        log.debug('Decorating %s with basic_decorator.', endpoint)
        @functools.wraps(endpoint)
        def wrapped(*args, **kwargs):
            self.basic()
            return endpoint(*args, **kwargs)
        return wrapped

    def global_public(self):
        request.checked_permissions = True
