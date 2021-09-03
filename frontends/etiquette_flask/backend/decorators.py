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
            response = exc.jsonify()
            response = flasktools.make_json_response(response, status=status)
            flask.abort(response)
    return wrapped

def give_theme_cookie(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        old_theme = request.cookies.get('etiquette_theme', None)
        new_theme = request.args.get('theme', None)
        theme = new_theme or old_theme or 'slate'

        request.cookies = werkzeug.datastructures.MultiDict(request.cookies)
        request.cookies['etiquette_theme'] = theme

        response = function(*args, **kwargs)

        if new_theme is None:
            pass
        elif new_theme == '':
            response.set_cookie('etiquette_theme', value='', expires=0)
        elif new_theme != old_theme:
            response.set_cookie('etiquette_theme', value=new_theme, expires=2147483647)

        return response
    return wrapped
