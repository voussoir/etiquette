import flask; from flask import request
import functools
import werkzeug.datastructures

from voussoirkit import flasktools

import etiquette

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
            response = flasktools.json_response(exc.jsonify(), status=status)
            flask.abort(response)
    return wrapped
