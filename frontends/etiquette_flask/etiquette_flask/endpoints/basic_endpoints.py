import flask; from flask import request

from . import common

site = common.site
session_manager = common.session_manager


####################################################################################################

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
