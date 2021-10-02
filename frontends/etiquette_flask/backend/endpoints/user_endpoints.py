import flask; from flask import request

from voussoirkit import flasktools

import etiquette

from .. import common
from .. import sessions

site = common.site
session_manager = common.session_manager

# Individual users #################################################################################

@site.route('/user/<username>')
def get_user_html(username):
    user = common.P_user(username, response_type='html')
    return common.render_template(request, 'user.html', user=user)

@site.route('/user/<username>.json')
def get_user_json(username):
    user = common.P_user(username, response_type='json')
    user = user.jsonify()
    return flasktools.json_response(user)

@site.route('/userid/<user_id>')
@site.route('/userid/<user_id>.json')
def get_user_id_redirect(user_id):
    if request.path.endswith('.json'):
        user = common.P_user_id(user_id, response_type='json')
    else:
        user = common.P_user_id(user_id, response_type='html')
    url_from = '/userid/' + user_id
    url_to = '/user/' + user.username
    url = request.url.replace(url_from, url_to)
    return flask.redirect(url)

@site.route('/user/<username>/edit', methods=['POST'])
def post_user_edit(username):
    session = session_manager.get(request)

    if not session:
        return flasktools.json_response(etiquette.exceptions.Unauthorized().jsonify(), status=403)
    user = common.P_user(username, response_type='json')
    if session.user != user:
        return flasktools.json_response(etiquette.exceptions.Unauthorized().jsonify(), status=403)

    display_name = request.form.get('display_name')
    if display_name is not None:
        user.set_display_name(display_name)

    common.P.commit()

    return flasktools.json_response(user.jsonify())

# Login and logout #################################################################################

@site.route('/login', methods=['GET'])
def get_login():
    response = common.render_template(
        request,
        'login.html',
        min_username_length=common.P.config['user']['min_username_length'],
        min_password_length=common.P.config['user']['min_password_length'],
    )
    return response

@site.route('/login', methods=['POST'])
@flasktools.required_fields(['username', 'password'])
def post_login():
    session = session_manager.get(request)
    if session.user:
        exc = etiquette.exceptions.AlreadySignedIn()
        response = exc.jsonify()
        return flasktools.json_response(response, status=403)

    username = request.form['username']
    password = request.form['password']
    try:
        # Consideration: Should the server hash the password to discourage
        # information (user exists) leak via response time?
        # Currently I think not, because they can check if the account
        # page 404s anyway.
        user = common.P.login(username=username, password=password)
    except (etiquette.exceptions.NoSuchUser, etiquette.exceptions.WrongLogin):
        exc = etiquette.exceptions.WrongLogin()
        response = exc.jsonify()
        return flasktools.json_response(response, status=422)
    except etiquette.exceptions.FeatureDisabled as exc:
        response = exc.jsonify()
        return flasktools.json_response(response, status=400)
    session = sessions.Session(request, user)
    session_manager.add(session)
    return flasktools.json_response({})

@site.route('/logout', methods=['POST'])
def logout():
    session_manager.remove(request)
    response = flasktools.json_response({})
    return response

# User registration ################################################################################

@site.route('/register', methods=['GET'])
def get_register():
    return flask.redirect('/login')

@site.route('/register', methods=['POST'])
@flasktools.required_fields(['username', 'password_1', 'password_2'])
def post_register():
    session = session_manager.get(request)
    if session.user:
        exc = etiquette.exceptions.AlreadySignedIn()
        response = exc.jsonify()
        return flasktools.json_response(response, status=403)

    username = request.form['username']
    display_name = request.form.get('display_name', None)
    password_1 = request.form['password_1']
    password_2 = request.form['password_2']

    if password_1 != password_2:
        response = {
            'error_type': 'PASSWORDS_DONT_MATCH',
            'error_message': 'Passwords do not match.',
        }
        return flasktools.json_response(response, status=422)

    user = common.P.new_user(username, password_1, display_name=display_name, commit=True)

    session = sessions.Session(request, user)
    session_manager.add(session)
    return flasktools.json_response({})
