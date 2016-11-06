from flask import request
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