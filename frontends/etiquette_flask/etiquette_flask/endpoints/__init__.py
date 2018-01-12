import flask; from flask import request
import random

from . import album_endpoints
from . import bookmark_endpoints
from . import common
from . import photo_endpoints
from . import tag_endpoints
from . import user_endpoints

site = common.site
session_manager = common.session_manager


@site.route('/')
@session_manager.give_token
def root():
    motd = random.choice(common.P.config['motd_strings'])
    session = session_manager.get(request)
    return flask.render_template('root.html', motd=motd, session=session)

@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    return flask.send_file(common.FAVICON_PATH.absolute_path)

@site.route('/apitest')
@session_manager.give_token
def apitest():
    response = flask.Response('testing')
    return response

if __name__ == '__main__':
    #site.run(threaded=True)
    pass
