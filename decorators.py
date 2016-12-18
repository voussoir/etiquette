import flask
from flask import request
import functools
import time
import warnings

import jsonify


def required_fields(fields):
    '''
    Declare that the endpoint requires certain POST body fields. Without them,
    we respond with 400 and a message.
    '''
    def with_required_fields(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if not all(field in request.form for field in fields):
                response = {'error': 'Required fields: %s' % ', '.join(fields)}
                response = jsonify.make_json_response(response, status=400)
                return response
            return function(*args, **kwargs)
        return wrapped
    return with_required_fields

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
