import flask; from flask import request
import os
import mimetypes
import traceback

import etiquette

from voussoirkit import pathclass

from . import jsonify
from . import sessions


root_dir = pathclass.Path(__file__).parent.parent

TEMPLATE_DIR = root_dir.with_child('templates')
STATIC_DIR = root_dir.with_child('static')
FAVICON_PATH = STATIC_DIR.with_child('favicon.png')

site = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR.absolute_path,
    static_folder=STATIC_DIR.absolute_path,
)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')
site.jinja_env.trim_blocks = True
site.jinja_env.lstrip_blocks = True
site.debug = True

P = etiquette.photodb.PhotoDB()

session_manager = sessions.SessionManager(maxlen=10000)


def P_wrapper(function):
    def P_wrapped(thingid, response_type='html'):
        try:
            return function(thingid)

        except etiquette.exceptions.EtiquetteException as exc:
            if isinstance(exc, etiquette.exceptions.NoSuch):
                status = 404
            else:
                status = 400

            if response_type == 'html':
                flask.abort(status, exc.error_message)
            else:
                response = etiquette.jsonify.exception(exc)
                response = jsonify.make_json_response(response, status=status)
                flask.abort(response)

        except Exception as exc:
            traceback.print_exc()
            if response_type == 'html':
                flask.abort(500)
            else:
                flask.abort(jsonify.make_json_response({}, status=500))

    return P_wrapped

@P_wrapper
def P_album(album_id):
    return P.get_album(album_id)

@P_wrapper
def P_bookmark(bookmarkid):
    return P.get_bookmark(bookmarkid)

@P_wrapper
def P_photo(photo_id):
    return P.get_photo(photo_id)

@P_wrapper
def P_tag(tagname):
    return P.get_tag(name=tagname)

@P_wrapper
def P_user(username):
    return P.get_user(username=username)

@P_wrapper
def P_user_id(user_id):
    return P.get_user(id=user_id)


def back_url():
    return request.args.get('goto') or request.referrer or '/'

def send_file(filepath, override_mimetype=None):
    '''
    Range-enabled file sending.
    '''
    filepath = pathclass.Path(filepath)

    if not filepath.is_file:
        flask.abort(404)

    outgoing_headers = {}
    if override_mimetype is not None:
        mimetype = override_mimetype
    else:
        mimetype = mimetypes.guess_type(filepath.absolute_path)[0]

    if mimetype is not None:
        if 'text/' in mimetype:
            mimetype += '; charset=utf-8'
        outgoing_headers['Content-Type'] = mimetype

    if 'range' in request.headers:
        desired_range = request.headers['range'].lower()
        desired_range = desired_range.split('bytes=')[-1]

        int_helper = lambda x: int(x) if x.isdigit() else None
        if '-' in desired_range:
            (desired_min, desired_max) = desired_range.split('-')
            range_min = int_helper(desired_min)
            range_max = int_helper(desired_max)
        else:
            range_min = int_helper(desired_range)
            range_max = None

        if range_min is None:
            range_min = 0
        if range_max is None:
            range_max = filepath.size

        # because ranges are 0-indexed
        range_max = min(range_max, filepath.size - 1)
        range_min = max(range_min, 0)

        range_header = 'bytes {min}-{max}/{outof}'.format(
            min=range_min,
            max=range_max,
            outof=filepath.size,
        )
        outgoing_headers['Content-Range'] = range_header
        status = 206
    else:
        range_max = filepath.size - 1
        range_min = 0
        status = 200

    outgoing_headers['Accept-Ranges'] = 'bytes'
    outgoing_headers['Content-Length'] = (range_max - range_min) + 1

    if request.method == 'HEAD':
        outgoing_data = bytes()
    else:
        outgoing_data = etiquette.helpers.read_filebytes(
            filepath.absolute_path,
            range_min=range_min,
            range_max=range_max,
            chunk_size=P.config['file_read_chunk'],
        )

    response = flask.Response(
        outgoing_data,
        status=status,
        headers=outgoing_headers,
    )
    return response
