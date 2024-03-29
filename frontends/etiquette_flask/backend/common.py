'''
Do not execute this file directly.
Use etiquette_flask_dev.py or etiquette_flask_prod.py.
'''
import flask; from flask import request
import functools
import json
import mimetypes
import traceback

from voussoirkit import bytestring
from voussoirkit import configlayers
from voussoirkit import flasktools
from voussoirkit import pathclass
from voussoirkit import vlogging

import etiquette

from . import client_caching
from . import jinja_filters
from . import permissions
from . import sessions

log = vlogging.getLogger(__name__)

# Constants ########################################################################################

DEFAULT_SERVER_CONFIG = {
    'anonymous_read': True,
    'anonymous_write': True,
}

BROWSER_CACHE_DURATION = 180

# Flask init #######################################################################################

# __file__ = .../etiquette_flask/backend/common.py
# root_dir = .../etiquette_flask
root_dir = pathclass.Path(__file__).parent.parent

P = None

TEMPLATE_DIR = root_dir.with_child('templates')
STATIC_DIR = root_dir.with_child('static')
FAVICON_PATH = STATIC_DIR.with_child('favicon.png')
SERVER_CONFIG_FILENAME = 'etiquette_flask_config.json'

site = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR.absolute_path,
    static_folder=STATIC_DIR.absolute_path,
)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=BROWSER_CACHE_DURATION,
    TEMPLATES_AUTO_RELOAD=True,
)
site.server_config = None
site.jinja_env.add_extension('jinja2.ext.do')
site.jinja_env.trim_blocks = True
site.jinja_env.lstrip_blocks = True
jinja_filters.register_all(site)
site.localhost_only = False

session_manager = sessions.SessionManager(maxlen=10000)
file_etag_manager = client_caching.FileEtagManager(
    maxlen=10000,
    max_filesize=5 * bytestring.MEBIBYTE,
    max_age=BROWSER_CACHE_DURATION,
)
permission_manager = permissions.PermissionManager(site)

# Response wrappers ################################################################################

def catch_etiquette_exception(endpoint):
    '''
    If an EtiquetteException is raised, automatically catch it and convert it
    into a json response so that the user doesn't receive error 500.
    '''
    @functools.wraps(endpoint)
    def wrapped(*args, **kwargs):
        try:
            return endpoint(*args, **kwargs)
        except etiquette.exceptions.EtiquetteException as exc:
            if isinstance(exc, etiquette.exceptions.NoSuch):
                status = 404
            else:
                status = 400
            response = flasktools.json_response(exc.jsonify(), status=status)
            flask.abort(response)
    return wrapped

@site.before_request
def before_request():
    # Note for prod: If you see that remote_addr is always 127.0.0.1 for all
    # visitors, make sure your reverse proxy is properly setting X-Forwarded-For
    # so that werkzeug's proxyfix can set that as the remote_addr.
    # In NGINX: proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    request.is_localhost = (request.remote_addr == '127.0.0.1')
    if site.localhost_only and not request.is_localhost:
        return flask.abort(403)

    if request.url_rule is None:
        return flask.abort(404)

    # Since we don't define this route (/static/ is a default from flask),
    # I can't just add this where it belongs. Sorry.
    if request.url_rule.rule == '/static/<path:filename>':
        permission_manager.global_public()

    session_manager._before_request(request)

@site.after_request
def after_request(response):
    if response.status_code < 400 and not hasattr(request, 'checked_permissions'):
        log.error('You forgot to set checked_permissions for ' + request.path)
        return flask.abort(500)
    response = flasktools.gzip_response(request, response)
    response = session_manager._after_request(response)
    return response

site.route = flasktools.decorate_and_route(
    flask_app=site,
    decorators=[
        flasktools.ensure_response_type,
        functools.partial(
            flasktools.give_theme_cookie,
            cookie_name='etiquette_theme',
            default_theme='slate',
        ),
        catch_etiquette_exception,
    ],
)

# P functions ######################################################################################

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
                response = exc.jsonify()
                response = flasktools.json_response(response, status=status)
                flask.abort(response)

        except Exception as exc:
            traceback.print_exc()
            if response_type == 'html':
                flask.abort(500)
            else:
                flask.abort(flasktools.json_response({}, status=500))

    return P_wrapped

@P_wrapper
def P_album(album_id):
    return P.get_album(album_id)

@P_wrapper
def P_albums(album_ids):
    return P.get_albums_by_id(album_ids)

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

# Other functions ##################################################################################

def back_url():
    return request.args.get('goto') or request.referrer or '/'

def render_template(request, template_name, **kwargs):
    theme = request.cookies.get('etiquette_theme', None)

    response = flask.render_template(
        template_name,
        request=request,
        theme=theme,
        **kwargs,
    )
    return response

def send_file(filepath, override_mimetype=None):
    '''
    Range-enabled file sending.
    '''
    filepath = pathclass.Path(filepath)

    if not filepath.is_file:
        flask.abort(404)

    file_size = filepath.size

    headers = file_etag_manager.get_304_headers(request=request, filepath=filepath)
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
            range_max = file_size

        # because ranges are 0-indexed
        range_max = min(range_max, file_size - 1)
        range_min = max(range_min, 0)

        range_header = 'bytes {min}-{max}/{outof}'.format(
            min=range_min,
            max=range_max,
            outof=file_size,
        )
        outgoing_headers['Content-Range'] = range_header
        status = 206
    else:
        range_max = file_size - 1
        range_min = 0
        status = 200

    outgoing_headers['Accept-Ranges'] = 'bytes'
    outgoing_headers['Content-Length'] = (range_max - range_min) + 1

    file_etag = file_etag_manager.get_file(filepath)
    if file_etag is not None:
        outgoing_headers.update(file_etag.get_headers())

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

####################################################################################################

# These functions will be called by the launcher, flask_dev, flask_prod.

def init_photodb(*args, **kwargs):
    global P
    P = etiquette.photodb.PhotoDB.closest_photodb(*args, **kwargs)
    load_config()

def load_config() -> None:
    log.debug('Loading server config file.')
    config_file = P.data_directory.with_child(SERVER_CONFIG_FILENAME)
    (config, needs_rewrite) = configlayers.load_file(
        filepath=config_file,
        default_config=DEFAULT_SERVER_CONFIG,
    )
    site.server_config = config

    if needs_rewrite:
        save_config()

def save_config() -> None:
    log.debug('Saving server config file.')
    config_file = P.data_directory.with_child(SERVER_CONFIG_FILENAME)
    with config_file.open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(site.server_config, indent=4, sort_keys=True))
