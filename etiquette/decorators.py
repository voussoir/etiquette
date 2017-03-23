import flask
from flask import request
import functools
import time
import warnings

from . import jsonify


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

def not_implemented(function):
    '''
    Decorator to remember what needs doing.
    '''
    warnings.warn('%s is not implemented' % function.__name__)
    return function

def time_me(function):
    '''
    After the function is run, print the elapsed time.
    '''
    @functools.wraps(function)
    def timed_function(*args, **kwargs):
        start = time.time()
        result = function(*args, **kwargs)
        end = time.time()
        print('%s: %0.8f' % (function.__name__, end-start))
        return result
    return timed_function
