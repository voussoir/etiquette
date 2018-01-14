import flask; from flask import request
import functools
import math
import os
import werkzeug.wrappers

import etiquette

def _generate_token(length=32):
    randbytes = os.urandom(math.ceil(length / 2))
    token = ''.join('{:02x}'.format(x) for x in randbytes)
    token = token[:length]
    return token

def _normalize_token(token):
    if isinstance(token, flask.Request):
        token = token.cookies.get('etiquette_session', None)


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def add(self, session):
        self.sessions[session.token] = session

    def get(self, token):
        token = _normalize_token(token)
        session = self.sessions.get(token, None)
        return session

    def give_token(self, function):
        '''
        This decorator ensures that the user has an `etiquette_session` cookie
        before reaching the request handler.
        If the user does not have the cookie, they are given one.
        If they do, its lifespan is reset.
        '''
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            # Inject new token so the function doesn't know the difference
            token = request.cookies.get('etiquette_session', None)
            if not token:
                token = _generate_token()
                request.cookies = dict(request.cookies)
                request.cookies['etiquette_session'] = token

            response = function(*args, **kwargs)
            if not isinstance(response, (flask.Response, werkzeug.wrappers.Response)):
                response = flask.Response(response)

            # Send the token back to the client
            # but only if the endpoint didn't manually set the cookie.
            for (headerkey, value) in response.headers:
                if headerkey == 'Set-Cookie' and value.startswith('etiquette_session='):
                    break
            else:
                response.set_cookie('etiquette_session', value=token, max_age=86400)
                self.maintain(token)

            return response
        return wrapped

    def maintain(self, token):
        session = self.get(token)
        if session:
            session.maintain()

    def remove(self, token):
        token = _normalize_token(token)
        if token in self.sessions:
            self.sessions.pop(token)

class Session:
    def __init__(self, request, user):
        self.token = _normalize_token(request)
        self.user = user
        self.ip_address = request.remote_addr
        self.user_agent = request.headers.get('User-Agent', '')
        self.last_activity = int(etiquette.helpers.now())

    def maintain(self):
        self.last_activity = int(etiquette.helpers.now())
