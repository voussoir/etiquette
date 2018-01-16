import flask; from flask import request

import etiquette

from .. import decorators
from .. import jsonify
from .. import sessions
from . import common

site = common.site
session_manager = common.session_manager


# Individual users #################################################################################

@site.route('/user/<username>', methods=['GET'])
@session_manager.give_token
def get_user_html(username):
    user = common.P_user(username, response_type='html')
    session = session_manager.get(request)
    return flask.render_template('user.html', user=user, session=session)

@site.route('/user/<username>.json', methods=['GET'])
@session_manager.give_token
def get_user_json(username):
    user = common.P_user(username, response_type='json')
    user = etiquette.jsonify.user(user)
    return jsonify.make_json_response(user)

@site.route('/userid/<user_id>')
@site.route('/userid/<user_id>.json')
def get_user_id_redirect(user_id):
    if request.url.endswith('.json'):
        user = common.P_user_id(user_id, response_type='json')
    else:
        user = common.P_user_id(user_id, response_type='html')
    url_from = '/userid/' + user_id
    url_to = '/user/' + user.username
    url = request.url.replace(url_from, url_to)
    return flask.redirect(url)

# Login and logout #################################################################################

@site.route('/login', methods=['GET'])
@session_manager.give_token
def get_login():
    session = session_manager.get(request)
    return flask.render_template('login.html', session=session)

@site.route('/login', methods=['POST'])
@session_manager.give_token
@decorators.required_fields(['username', 'password'])
def post_login():
    session = session_manager.get(request)
    if session.user:
        exc = etiquette.exceptions.AlreadySignedIn()
        response = etiquette.jsonify.exception(exc)
        return jsonify.make_json_response(response, status=403)

    username = request.form['username']
    password = request.form['password']
    try:
        # Consideration: Should the server hash the password to discourage
        # information (user exists) leak via response time?
        # Currently I think not, because they can check if the account
        # page 404s anyway.
        user = common.P.get_user(username=username)
        user = common.P.login(user.id, password)
    except (etiquette.exceptions.NoSuchUser, etiquette.exceptions.WrongLogin):
        exc = etiquette.exceptions.WrongLogin()
        response = etiquette.jsonify.exception(exc)
        return jsonify.make_json_response(response, status=422)
    except etiquette.exceptions.FeatureDisabled as exc:
        response = etiquette.jsonify.exception(exc)
        return jsonify.make_json_response(response, status=400)
    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})

@site.route('/logout', methods=['GET', 'POST'])
@session_manager.give_token
def logout():
    session_manager.remove(request)
    response = flask.Response('redirect', status=302, headers={'Location': common.back_url()})
    return response

# User registration ################################################################################

@site.route('/register', methods=['GET'])
def get_register():
    return flask.redirect('/login')

@site.route('/register', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
@decorators.required_fields(['username', 'password_1', 'password_2'])
def post_register():
    session = session_manager.get(request)
    if session.user:
        exc = etiquette.exceptions.AlreadySignedIn()
        response = etiquette.jsonify.exception(exc)
        return jsonify.make_json_response(response, status=403)

    username = request.form['username']
    password_1 = request.form['password_1']
    password_2 = request.form['password_2']

    if password_1 != password_2:
        response = {
            'error_type': 'PASSWORDS_DONT_MATCH',
            'error_message': 'Passwords do not match.',
        }
        return jsonify.make_json_response(response, status=422)

    user = common.P.register_user(username, password_1)

    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})

