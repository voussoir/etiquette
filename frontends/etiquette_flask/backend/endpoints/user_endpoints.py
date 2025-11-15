import flask; from flask import request

from voussoirkit import flasktools
from voussoirkit import stringtools

import etiquette

from .. import common
from .. import sessions

site = common.site
session_manager = common.session_manager

# Individual users #################################################################################

@site.route('/user/<username>')
def get_user_html(username):
    common.permission_manager.read()
    user = common.P_user(username, response_type='html')
    return common.render_template(
        request,
        'user.html',
        user=user,
        user_permissions=user.get_permissions(),
        constants_all_permissions=etiquette.constants.ALL_PERMISSIONS,
    )

@site.route('/user/<username>.json')
def get_user_json(username):
    common.permission_manager.read()
    user = common.P_user(username, response_type='json')
    user = user.jsonify()
    return flasktools.json_response(user)

@site.route('/userid/<user_id>')
@site.route('/userid/<user_id>.json')
def get_user_id_redirect(user_id):
    common.permission_manager.read()
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
    user = common.P_user(username, response_type='json')
    common.permission_manager.logged_in(user)

    display_name = request.form.get('display_name')
    if display_name is not None:
        with common.P.transaction:
            user.set_display_name(display_name)

    return flasktools.json_response(user.jsonify())

@site.route('/user/<username>/set_password', methods=['POST'])
@flasktools.required_fields(['current_password', 'password_1', 'password_2'])
def post_user_set_password(username):
    user = common.P_user(username, response_type='json')
    common.permission_manager.logged_in(user)

    current_password = request.form.get('current_password')
    try:
        user.check_password(current_password)
    except (etiquette.exceptions.WrongLogin):
        exc = etiquette.exceptions.WrongLogin()
        response = exc.jsonify()
        return flasktools.json_response(response, status=422)
    except etiquette.exceptions.FeatureDisabled as exc:
        response = exc.jsonify()
        return flasktools.json_response(response, status=400)

    password_1 = request.form.get('password_1')
    password_2 = request.form.get('password_2')
    if password_1 != password_2:
        response = {
            'error_type': 'PASSWORDS_DONT_MATCH',
            'error_message': 'Passwords do not match.',
        }
        return flasktools.json_response(response, status=422)

    with common.P.transaction:
        user.set_password(password_1)

    sessions = list(session_manager.sessions.items())
    for (token, session) in sessions:
        if session.user == user and token != request.session.token:
            session_manager.remove(token)

@site.route('/user/<username>/set_permission', methods=['POST'])
@flasktools.required_fields(['permission', 'value'])
def post_user_set_permission(username):
    common.permission_manager.admin_only()
    permission_string = request.form['permission']
    permission_value = stringtools.truthystring(request.form['value'])
    user = common.P_user(username, response_type='json')
    with common.P.transaction:
        if permission_value:
            user.add_permission(permission_string)
        else:
            user.remove_permission(permission_string)
    return flasktools.json_response(user.jsonify())

# Login and logout #################################################################################

@site.route('/login', methods=['GET'])
def get_login():
    common.permission_manager.global_public()
    response = common.render_template(
        request,
        'login.html',
        min_username_length=common.P.config['user']['min_username_length'],
        min_password_length=common.P.config['user']['min_password_length'],
        registration_enabled=common.site.server_config['registration_enabled'],
    )
    return response

@site.route('/login', methods=['POST'])
@flasktools.required_fields(['username', 'password'])
def post_login():
    common.permission_manager.global_public()
    if request.session.user:
        exc = etiquette.exceptions.AlreadySignedIn()
        response = exc.jsonify()
        return flasktools.json_response(response, status=403)

    username = request.form['username']
    password = request.form['password']
    try:
        user = common.P_user(username, 'json')
    except (etiquette.exceptions.NoSuchUser):
        exc = etiquette.exceptions.WrongLogin()
        response = exc.jsonify()
        return flasktools.json_response(response, status=404)

    try:
        user.check_password(password)
    except (etiquette.exceptions.WrongLogin):
        exc = etiquette.exceptions.WrongLogin()
        response = exc.jsonify()
        return flasktools.json_response(response, status=422)
    except etiquette.exceptions.FeatureDisabled as exc:
        response = exc.jsonify()
        return flasktools.json_response(response, status=400)

    request.session = sessions.Session.from_request(session_manager=session_manager, request=request, user=user)
    session_manager.save_state()
    return flasktools.json_response({})

@site.route('/logout', methods=['POST'])
def post_logout():
    common.permission_manager.logged_in()
    session_manager.remove(request)
    response = flasktools.json_response({})
    return response

# User registration ################################################################################

@site.route('/register', methods=['GET'])
def get_register():
    common.permission_manager.global_public()
    return flask.redirect('/login')

@site.route('/register', methods=['POST'])
@flasktools.required_fields(['username', 'password_1', 'password_2'])
def post_register():
    common.permission_manager.global_public()
    if request.session.user:
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

    with common.P.transaction:
        user = common.P.new_user(username, password_1, display_name=display_name)

    request.session = sessions.Session.from_request(session_manager=session_manager, request=request, user=user)
    return flasktools.json_response({})
