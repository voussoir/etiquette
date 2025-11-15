import flask; from flask import request
import json

from voussoirkit import dotdict
from voussoirkit import flasktools
from voussoirkit import timetools

import etiquette

from .. import common

site = common.site
session_manager = common.session_manager

####################################################################################################

@site.route('/admin')
def get_admin():
    common.permission_manager.admin_only()

    counts = dotdict.DotDict({
        'albums': common.P.get_album_count(),
        'bookmarks': common.P.get_bookmark_count(),
        'photos': common.P.get_photo_count(),
        'tags': common.P.get_tag_count(),
        'users': common.P.get_user_count(),
    })
    cached = dotdict.DotDict({
        'albums': len(common.P.caches[etiquette.objects.Album]),
        'bookmarks': len(common.P.caches[etiquette.objects.Bookmark]),
        'photos': len(common.P.caches[etiquette.objects.Photo]),
        'tags': len(common.P.caches[etiquette.objects.Tag]),
        'users': len(common.P.caches[etiquette.objects.User]),
    })
    return common.render_template(
        request,
        'admin.html',
        etq_config=json.dumps(common.P.config, indent=4, sort_keys=True),
        server_config=json.dumps(common.site.server_config, indent=4, sort_keys=True),
        cached=cached,
        counts=counts,
        users=list(common.P.get_users()),
        sessions=list(session_manager.sessions.items()),
    )

@site.route('/admin/dbdownload')
def get_dbdump():
    common.permission_manager.admin_only()

    with common.P.transaction:
        binary = common.P.database_filepath.read('rb')

    now = timetools.now().strftime('%Y-%m-%d_%H-%M-%S')
    download_as = f'etiquette {now}.db'
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{download_as}',
    }
    return flask.Response(binary, headers=outgoing_headers)

@site.route('/admin/clear_sessions', methods=['POST'])
def post_clear_sessions():
    common.permission_manager.admin_only()

    session_manager.clear()
    session_manager.save_state()
    return flasktools.json_response({})

@site.route('/admin/remove_session', methods=['POST'])
@flasktools.required_fields(['token'], forbid_whitespace=True)
def post_remove_session():
    common.permission_manager.admin_only()

    token = request.form['token']
    session_manager.remove(token)
    return flasktools.json_response({})

@site.route('/admin/reload_config', methods=['POST'])
def post_reload_config():
    common.permission_manager.admin_only()

    common.P.load_config()
    common.load_config()

    return flasktools.json_response({})

@site.route('/admin/uncache', methods=['POST'])
def post_uncache():
    common.permission_manager.admin_only()

    with common.P.transaction:
        for cache in common.P.caches.values():
            print(cache)
            cache.clear()

    return flasktools.json_response({})
