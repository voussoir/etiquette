import flask; from flask import request

from voussoirkit import flasktools

from .. import common

site = common.site
session_manager = common.session_manager

####################################################################################################

@site.route('/admin')
def get_admin():
    if not request.is_localhost:
        flask.abort(403)

    return common.render_template(request, 'admin.html')

@site.route('/admin/reload_config', methods=['POST'])
def post_reload_config():
    if not request.is_localhost:
        return flasktools.make_json_response({}, status=403)

    common.P.load_config()
    return flasktools.make_json_response({})
