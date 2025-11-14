import datetime
import flask; from flask import request
import functools
import json
import random
import werkzeug.datastructures

from voussoirkit import cacheclass
from voussoirkit import flasktools
from voussoirkit import timetools
from voussoirkit import vlogging

log = vlogging.getLogger(__name__, 'sessions')

import etiquette

RNG = random.SystemRandom()

SESSION_MAX_AGE = 86400
SAVE_STATE_INTERVAL = 60

def _generate_token() -> str:
    return str(RNG.getrandbits(128))

def _normalize_token(token):
    if isinstance(token, flasktools.REQUEST_TYPES):
        request = token
        token = request.cookies.get('etiquette_session', None)
        if token is None:
            # During normal usage, this does not occur because give_token is
            # applied *before* the request handler even sees the request.
            # Just a precaution.
            message = 'Cannot normalize token for request with no etiquette_session header.'
            raise TypeError(message, request)
    elif isinstance(token, str):
        pass
    else:
        raise TypeError('Unsupported token normalization', type(token))
    return token

class SessionManager:
    def __init__(self, maxlen=None, state_file=None):
        self.sessions = cacheclass.Cache(maxlen=maxlen)
        self.last_activity = timetools.now()
        self.last_save_state = timetools.now()

    def _before_request(self, request):
        # Inject new token so the function doesn't know the difference
        token = request.cookies.get('etiquette_session', None)
        if not token or token not in self.sessions:
            token = _generate_token()
            # cookies is currently an ImmutableMultiDict, but in order to
            # trick the wrapped function I'm gonna have to mutate it.
            # It is important to use a werkzeug MultiDict and not a plain
            # Python dict, because werkzeug puts cookies into lists like
            # {name: [value]} and then cookies.get pulls the first item out
            # of that list. A plain dict wouldn't have this .get behavior.
            request.cookies = werkzeug.datastructures.MultiDict(request.cookies)
            request.cookies['etiquette_session'] = token

        try:
            session = self.get(request)
        except KeyError:
            session = Session.from_request(session_manager=self, request=request, user=None)
        else:
            session.maintain()

        request.session = session
        return session

    def _after_request(self, response):
        # Send the token back to the client
        # but only if the endpoint didn't manually set the cookie.
        function_cookies = response.headers.get_all('Set-Cookie')

        if not hasattr(request, 'session') or not request.session:
            return response

        if not any('etiquette_session=' in cookie for cookie in function_cookies):
            response.set_cookie(
                'etiquette_session',
                value=request.session.token,
                max_age=SESSION_MAX_AGE,
                httponly=True,
            )

        return response

    def add(self, session):
        session.session_manager = self
        self.sessions[session.token] = session

    def clear(self):
        self.sessions.clear()

    def get(self, request):
        token = _normalize_token(request)
        session = self.sessions[token]
        if session.expired():
            self.remove(token)
            raise KeyError(token)
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
            self._before_request(request)
            response = function(*args, **kwargs)
            return self._after_request(response)

        return wrapped

    def maintain(self):
        now = timetools.now()
        self.last_activity = now
        state_age = now - self.last_save_state
        if state_age.seconds > SAVE_STATE_INTERVAL:
            self.save_state()

    def remove(self, token):
        token = _normalize_token(token)
        try:
            self.sessions.remove(token)
        except KeyError:
            pass

    def save_state(self):
        log.debug('Saving sessions state.')
        j = [session.jsonify() for session in self.sessions.values() if not session.expired()]
        j = json.dumps(j)
        self.state_file.write('w', j)
        self.last_save_state = timetools.now()

class Session:
    def __init__(
            self,
            *,
            session_manager,
            token,
            ip_address,
            user_agent,
            user,
            last_activity=None,
        ):
        self.session_manager = session_manager
        self.token = token
        self.user = user
        self.ip_address = ip_address
        self.user_agent = user_agent
        if last_activity is None:
            self.last_activity = timetools.now()
        else:
            self.last_activity = last_activity
        self.session_manager.add(self)
        self.session_manager.maintain()

    @classmethod
    def from_request(cls, *, session_manager, request, user):
        return cls(
            session_manager=session_manager,
            token=_normalize_token(request),
            user=user,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
        )

    def __repr__(self):
        if self.user:
            return f'Session {self.token} for user {self.user}'
        else:
            return f'Session {self.token} for anonymous'

    def expired(self):
        now = timetools.now()
        age = now - self.last_activity
        return age.seconds > SESSION_MAX_AGE

    def jsonify(self):
        return {
            'userid': (self.user.id) if self.user else None,
            'token': self.token,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'last_activity': self.last_activity.timestamp(),
        }

    def maintain(self):
        self.last_activity = timetools.now()
        self.session_manager.maintain()
