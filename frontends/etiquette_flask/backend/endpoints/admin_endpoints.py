import flask; from flask import request

from voussoirkit import flasktools

import etiquette

from .. import common

site = common.site
session_manager = common.session_manager

####################################################################################################

@site.route('/admin')
def get_admin():
    if not request.is_localhost:
        flask.abort(403)

    return common.render_template(request, 'admin.html')

@site.route('/admin/dbdownload')
def get_dbdump():
    if not request.is_localhost:
        flask.abort(403)

    with common.P.transaction:
        binary = common.P.database_filepath.read('rb')

    now = etiquette.helpers.now().strftime('%Y-%m-%d_%H-%M-%S')
    download_as = f'etiquette {now}.db'
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{download_as}',
    }
    return flask.Response(binary, headers=outgoing_headers)

@site.route('/admin/reload_config', methods=['POST'])
def post_reload_config():
    if not request.is_localhost:
        return flasktools.json_response({}, status=403)

    common.P.load_config()
    return flasktools.json_response({})
