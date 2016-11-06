import flask
from flask import request
import functools
import time
import uuid

def _generate_session_token():
    token = str(uuid.uuid4())
    #print('MAKE SESSION', token)
    return token

def give_session_token(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        # Inject new token so the function doesn't know the difference
        token = request.cookies.get('etiquette_session', None)
        if not token:
            token = _generate_session_token()
            request.cookies = dict(request.cookies)
            request.cookies['etiquette_session'] = token

        ret = function(*args, **kwargs)

        # Send the token back to the client
        if not isinstance(ret, flask.Response):
            ret = flask.Response(ret)
        ret.set_cookie('etiquette_session', value=token, max_age=60)

        return ret
    return wrapped

def not_implemented(function):
    '''
    Decorator to remember what needs doing.
    '''
    warnings.warn('%s is not implemented' % function.__name__)
    return function

def time_me(function):
    '''
    Decorator. After the function is run, print the elapsed time.
    '''
    @functools.wraps(function)
    def timed_function(*args, **kwargs):
        start = time.time()
        result = function(*args, **kwargs)
        end = time.time()
        print('%s: %0.8f' % (function.__name__, end-start))
        return result
    return timed_function
