import flask; from flask import request
import functools
import math
import os
import werkzeug.wrappers

import etiquette

SESSION_MAX_AGE = 86400

def _generate_token(length=32):
    randbytes = os.urandom(math.ceil(length / 2))
    token = ''.join('{:02x}'.format(x) for x in randbytes)
    token = token[:length]
    return token

def _normalize_token(token):
    if isinstance(token, (flask.Request, werkzeug.wrappers.Request, werkzeug.local.LocalProxy)):
        request = token
        token = request.cookies.get('etiquette_session', None)
        if token is None:
            message = 'Cannot normalize token for request with no etiquette_session header.'
            raise TypeError(message, request)
    elif isinstance(token, str):
        pass
    else:
        raise TypeError('Unsupported token normalization', type(token))
    return token


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def add(self, session):
        self.sessions[session.token] = session

    def get(self, token):
        token = _normalize_token(token)
        session = self.sessions[token]
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

            try:
                session = self.get(token)
            except KeyError:
                session = Session(request, user=None)
                self.add(session)
            else:
                session.maintain()

            response = function(*args, **kwargs)
            if not isinstance(response, (flask.Response, werkzeug.wrappers.Response)):
                response = flask.Response(response)

            # Send the token back to the client
            # but only if the endpoint didn't manually set the cookie.
            function_cookies = response.headers.get_all('Set-Cookie')
            if not any('etiquette_session=' in cookie for cookie in function_cookies):
                response.set_cookie(
                    'etiquette_session',
                    value=session.token,
                    max_age=SESSION_MAX_AGE,
                )

            return response
        return wrapped

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

    def __repr__(self):
        if self.user:
            return 'Session %s for user %s' % (self.token, self.user)
        else:
            return 'Session %s for anonymous' % self.token

    def maintain(self):
        self.last_activity = int(etiquette.helpers.now())
