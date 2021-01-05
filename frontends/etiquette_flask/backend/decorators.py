import flask; from flask import request
import functools
import time

from voussoirkit import passwordy

import etiquette

from . import jsonify

def cached_endpoint(max_age):
    '''
    The cached_endpoint decorator can be used on slow endpoints that don't need
    to be constantly updated or endpoints that produce large, static responses.

    WARNING: The return value of the endpoint is shared with all users.
    You should never use this cache on an endpoint that provides private
    or personalized data, and you should not try to pass other headers through
    the response.

    When the function is run, its return value is stored and a random etag is
    generated so that subsequent runs can respond with 304. This way, large
    response bodies do not need to be transmitted often.

    Given a nonzero max_age, the endpoint will only be run once per max_age
    seconds on a global basis (not per-user). This way, you can prevent a slow
    function from being run very often. In-between requests will just receive
    the previous return value (still using 200 or 304 as appropriate for the
    client's provided etag).

    An example use case would be large-sized data dumps that don't need to be
    precisely up to date every time.
    '''
    state = {
        'max_age': max_age,
        'stored_value': None,
        'stored_etag': None,
        'headers': {'ETag': None, 'Cache-Control': f'max-age={max_age}'},
        'last_run': 0,
    }

    def wrapper(function):
        def get_value(*args, **kwargs):
            if state['max_age'] and (time.time() - state['last_run']) > state['max_age']:
                return state['stored_value']

            value = function(*args, **kwargs)
            if isinstance(value, flask.Response):
                if value.headers.get('Content-Type'):
                    state['headers']['Content-Type'] = value.headers.get('Content-Type')
                value = value.response

            if value != state['stored_value']:
                state['stored_value'] = value
                state['stored_etag'] = passwordy.random_hex(20)
                state['headers']['ETag'] = state['stored_etag']

            state['last_run'] = time.time()
            return value

        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            value = get_value(*args, **kwargs)

            client_etag = request.headers.get('If-None-Match', None)
            if client_etag == state['stored_etag']:
                response = flask.Response(status=304, headers=state['headers'])
            else:
                response = flask.Response(value, status=200, headers=state['headers'])

            return response
        return wrapped
    return wrapper

def catch_etiquette_exception(function):
    '''
    If an EtiquetteException is raised, automatically catch it and convert it
    into a json response so that the user isn't receiving error 500.
    '''
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except etiquette.exceptions.EtiquetteException as exc:
            if isinstance(exc, etiquette.exceptions.NoSuch):
                status = 404
            else:
                status = 400
            response = exc.jsonify()
            response = jsonify.make_json_response(response, status=status)
            flask.abort(response)
    return wrapped

def required_fields(fields, forbid_whitespace=False):
    '''
    Declare that the endpoint requires certain POST body fields. Without them,
    we respond with 400 and a message.

    forbid_whitespace:
        If True, then providing the field is not good enough. It must also
        contain at least some non-whitespace characters.
    '''
    def wrapper(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            for requirement in fields:
                missing = (
                    requirement not in request.form or
                    (forbid_whitespace and request.form[requirement].strip() == '')
                )
                if missing:
                    response = {
                        'error_type': 'MISSING_FIELDS',
                        'error_message': 'Required fields: %s' % ', '.join(fields),
                    }
                    response = jsonify.make_json_response(response, status=400)
                    return response

            return function(*args, **kwargs)
        return wrapped
    return wrapper
