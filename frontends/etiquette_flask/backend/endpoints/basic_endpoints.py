import flask; from flask import request
import random

from .. import common

site = common.site
session_manager = common.session_manager

####################################################################################################

@site.route('/')
def root():
    motd = random.choice(common.P.config['motd_strings'])
    return common.render_template(request, 'root.html', motd=motd)

@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    return flask.send_file(common.FAVICON_PATH.absolute_path)
