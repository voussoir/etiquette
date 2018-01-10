import flask
from flask import request
import functools

import etiquette

from . import jsonify


def catch_etiquette_exception(function):
    '''
    If an EtiquetteException is raised, automatically catch it and convert it
    into a response so that the user isn't receiving error 500.
    '''
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except etiquette.exceptions.EtiquetteException as e:
            if isinstance(e, etiquette.exceptions.NoSuch):
                status = 404
            else:
                status = 400
            response = etiquette.jsonify.exception(e)
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
