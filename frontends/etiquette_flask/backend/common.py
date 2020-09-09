import flask; from flask import request
import mimetypes
import traceback

from voussoirkit import bytestring
from voussoirkit import pathclass

import etiquette

from . import caching
from . import jinja_filters
from . import jsonify
from . import sessions


root_dir = pathclass.Path(__file__).parent.parent

TEMPLATE_DIR = root_dir.with_child('templates')
STATIC_DIR = root_dir.with_child('static')
FAVICON_PATH = STATIC_DIR.with_child('favicon.png')
BROWSER_CACHE_DURATION = 180

site = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR.absolute_path,
    static_folder=STATIC_DIR.absolute_path,
)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=BROWSER_CACHE_DURATION,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')
site.jinja_env.trim_blocks = True
site.jinja_env.lstrip_blocks = True
site.jinja_env.filters['bytestring'] = jinja_filters.bytestring
site.jinja_env.filters['comma_join'] = jinja_filters.comma_join
site.jinja_env.filters['file_link'] = jinja_filters.file_link
site.jinja_env.filters['sort_tags'] = jinja_filters.sort_tags
site.jinja_env.filters['timestamp_to_8601'] = jinja_filters.timestamp_to_8601
site.jinja_env.filters['timestamp_to_naturaldate'] = jinja_filters.timestamp_to_naturaldate
site.jinja_env.filters['users_to_usernames'] = jinja_filters.users_to_usernames
site.jinja_env.globals['make_attributes'] = jinja_filters.make_attributes
site.debug = True

P = etiquette.photodb.PhotoDB()

session_manager = sessions.SessionManager(maxlen=10000)
file_cache_manager = caching.FileCacheManager(
    maxlen=10000,
    max_filesize=5 * bytestring.MIBIBYTE,
    max_age=BROWSER_CACHE_DURATION,
)

def P_wrapper(function):
    def P_wrapped(thingid, response_type):
        if response_type not in {'html', 'json'}:
            raise TypeError(f'response_type should be html or json, not {response_type}.')

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
def P_bookmark(bookmark_id):
    return P.get_bookmark(bookmark_id)

@P_wrapper
def P_photo(photo_id):
    return P.get_photo(photo_id)

@P_wrapper
def P_photos(photo_ids):
    return P.get_photos_by_id(photo_ids)

@P_wrapper
def P_tag(tagname):
    return P.get_tag(name=tagname)

@P_wrapper
def P_tag_id(tag_id):
    return P.get_tag(id=tag_id)

@P_wrapper
def P_user(username):
    return P.get_user(username=username)

@P_wrapper
def P_user_id(user_id):
    return P.get_user(id=user_id)

def render_template(request, *args, **kwargs):
    session = session_manager.get(request)
    ret = flask.render_template(
        session=session,
        theme=request.args.get('theme'),
        *args,
        **kwargs,
    )
    return ret

def back_url():
    return request.args.get('goto') or request.referrer or '/'

def send_file(filepath, override_mimetype=None):
    '''
    Range-enabled file sending.
    '''
    filepath = pathclass.Path(filepath)

    if not filepath.is_file:
        flask.abort(404)

    headers = file_cache_manager.matches(request=request, filepath=filepath)
    if headers:
        response = flask.Response(status=304, headers=headers)
        return response

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
    cache_file = file_cache_manager.get(filepath)
    if cache_file is not None:
        outgoing_headers.update(cache_file.get_headers())

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
