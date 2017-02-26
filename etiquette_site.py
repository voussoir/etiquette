import flask
from flask import request
import json
import mimetypes
import os
import random
import urllib.parse
import warnings
import zipstream

from etiquette import constants
from etiquette import decorators
from etiquette import exceptions
from etiquette import helpers
from etiquette import jsonify
from etiquette import objects
from etiquette import photodb
from etiquette import searchhelpers
from etiquette import sessions


TEMPLATE_DIR = 'C:\\git\\Etiquette\\templates'
STATIC_DIR = 'C:\\git\\Etiquette\\static'

site = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')
site.jinja_env.trim_blocks = True
site.jinja_env.lstrip_blocks = True
site.debug = True

P = photodb.PhotoDB()

session_manager = sessions.SessionManager()

####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################


def back_url():
    return request.args.get('goto') or request.referrer or '/'

def create_tag(easybake_string):
    notes = P.easybake(easybake_string)
    notes = [{'action': action, 'tagname': tagname} for (action, tagname) in notes]
    return notes

def delete_tag(tag):
    tag = tag.split('.')[-1].split('+')[0]
    tag = P.get_tag(tag)

    tag.delete()
    return {'action': 'delete_tag', 'tagname': tag.name}

def delete_synonym(synonym):
    synonym = synonym.split('+')[-1].split('.')[-1]
    synonym = P.normalize_tagname(synonym)

    master_tag = P.get_tag(synonym)
    master_tag.remove_synonym(synonym)

    return {'action':'delete_synonym', 'synonym': synonym}

def P_wrapper(function):
    def P_wrapped(thingid, response_type='html'):
        ret = function(thingid)
        if not isinstance(ret, str):
            return ret

        if response_type == 'html':
            flask.abort(404, ret)
        else:
            response = jsonify.make_json_response({'error': ret})
            flask.abort(response)

    return P_wrapped

@P_wrapper
def P_album(albumid):
    try:
        return P.get_album(albumid)
    except exceptions.NoSuchAlbum:
        return 'That album doesnt exist'

@P_wrapper
def P_photo(photoid):
    try:
        return P.get_photo(photoid)
    except exceptions.NoSuchPhoto:
        return 'That photo doesnt exist'

@P_wrapper
def P_tag(tagname):
    try:
        return P.get_tag(tagname)
    except exceptions.NoSuchTag as e:
        return 'That tag doesnt exist: %s' % e

@P_wrapper
def P_user(username):
    try:
        return P.get_user(username=username)
    except exceptions.NoSuchUser as e:
        return 'That user doesnt exist: %s' % e

def send_file(filepath):
    '''
    Range-enabled file sending.
    '''
    try:
        file_size = os.path.getsize(filepath)
    except FileNotFoundError:
        flask.abort(404)

    outgoing_headers = {}
    mimetype = mimetypes.guess_type(filepath)[0]
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

    if request.method == 'HEAD':
        outgoing_data = bytes()
    else:
        outgoing_data = helpers.read_filebytes(
            filepath,
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
####################################################################################################
####################################################################################################
####################################################################################################


@site.route('/')
@session_manager.give_token
def root():
    motd = random.choice(P.config['motd_strings'])
    session = session_manager.get(request)
    return flask.render_template('root.html', motd=motd, session=session)

@site.route('/login', methods=['GET'])
@session_manager.give_token
def get_login():
    session = session_manager.get(request)
    return flask.render_template('login.html', session=session)

@site.route('/register', methods=['GET'])
def get_register():
    return flask.redirect('/login')

@site.route('/login', methods=['POST'])
@session_manager.give_token
@decorators.required_fields(['username', 'password'])
def post_login():
    if session_manager.get(request):
        return jsonify.make_json_response({'error': 'You\'re already signed in'}, status=403)

    username = request.form['username']
    password = request.form['password']
    try:
        user = P.get_user(username=username)
        user = P.login(user.id, password)
    except (exceptions.NoSuchUser, exceptions.WrongLogin):
        return jsonify.make_json_response({'error': 'Wrong login'}, status=422)
    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})

@site.route('/register', methods=['POST'])
@session_manager.give_token
@decorators.required_fields(['username', 'password_1', 'password_2'])
def post_register():
    if session_manager.get(request):
        return jsonify.make_json_response({'error': 'You\'re already signed in'}, status=403)

    username = request.form['username']
    password_1 = request.form['password_1']
    password_2 = request.form['password_2']

    if password_1 != password_2:
        return jsonify.make_json_response({'error': 'Passwords do not match'}, status=422)

    try:
        user = P.register_user(username, password_1)
    except exceptions.UsernameTooShort as e:
        error = 'Username shorter than minimum of %d' % P.config['min_username_length']
    except exceptions.UsernameTooLong as e:
        error = 'Username longer than maximum of %d' % P.config['max_username_length']
    except exceptions.InvalidUsernameChars as e:
        error = 'Username contains invalid characters %s' % e.args[0]
    except exceptions.PasswordTooShort as e:
        error = 'Password is shorter than minimum of %d' % P.config['min_password_length']
    except exceptions.UserExists as e:
        error = 'User %s already exists' % e.args[0]
    else:
        error = None

    if error is not None:
        return jsonify.make_json_response({'error': error}, status=422)

    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})

@site.route('/logout', methods=['GET', 'POST'])
@session_manager.give_token
def logout():
    session_manager.remove(request)
    response = flask.Response('redirect', status=302, headers={'Location': back_url()})
    return response


@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    filename = os.path.join(STATIC_DIR, 'favicon.png')
    return flask.send_file(filename)


def get_album_core(albumid):
    album = P_album(albumid)
    return album

@site.route('/album/<albumid>')
@session_manager.give_token
def get_album_html(albumid):
    album = get_album_core(albumid)
    session = session_manager.get(request)
    response = flask.render_template(
        'album.html',
        album=album,
        session=session,
        view=request.args.get('view', 'grid'),
    )
    return response

@site.route('/album/<albumid>.json')
@session_manager.give_token
def get_album_json(albumid):
    album = get_album_core(albumid)
    album = jsonify.album(album)
    album['sub_albums'] = [P_album(x) for x in album['sub_albums']]
    album['sub_albums'].sort(key=lambda x: (x.title or x.id).lower())
    album['sub_albums'] = [jsonify.album(x, minimal=True) for x in album['sub_albums']]
    return jsonify.make_json_response(album)


@site.route('/album/<albumid>.zip')
def get_album_zip(albumid):
    album = P_album(albumid)

    recursive = request.args.get('recursive', True)
    recursive = helpers.truthystring(recursive)

    arcnames = helpers.album_zip_filenames(album, recursive=recursive)

    streamed_zip = zipstream.ZipFile()
    for (real_filepath, arcname) in arcnames.items():
        streamed_zip.write(real_filepath, arcname=arcname)

    # Add the album metadata as an {id}.txt file within each directory.
    directories = helpers.album_zip_directories(album, recursive=recursive)
    for (inner_album, directory) in directories.items():
        text = []
        if inner_album.title:
            text.append(inner_album.title)
        if inner_album.description:
            text.append(inner_album.description)
        if not text:
            continue
        text = '\r\n\r\n'.join(text)
        streamed_zip.writestr(
            arcname=os.path.join(directory, '%s.txt' % inner_album.id),
            data=text.encode('utf-8'),
        )

    if album.title:
        download_as = '%s - %s.zip' % (album.id, album.title)
    else:
        download_as = '%s.zip' % album.id
    download_as = urllib.parse.quote(download_as)
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename*=UTF-8\'\'%s' % download_as,

    }
    return flask.Response(streamed_zip, headers=outgoing_headers)


def get_albums_core():
    albums = P.get_albums()
    albums = [a for a in albums if a.parent() is None]
    return albums

@site.route('/albums')
@session_manager.give_token
def get_albums_html():
    albums = get_albums_core()
    session = session_manager.get(request)
    return flask.render_template('albums.html', albums=albums, session=session)

@site.route('/albums.json')
@session_manager.give_token
def get_albums_json():
    albums = get_albums_core()
    albums = [jsonify.album(album, minimal=True) for album in albums]
    return jsonify.make_json_response(albums)


@site.route('/bookmarks')
@session_manager.give_token
def get_bookmarks():
    session = session_manager.get(request)
    bookmarks = list(P.get_bookmarks())
    return flask.render_template('bookmarks.html', bookmarks=bookmarks, session=session)


@site.route('/file/<photoid>')
def get_file(photoid):
    photoid = photoid.split('.')[0]
    photo = P.get_photo(photoid)

    do_download = request.args.get('download', False)
    do_download = helpers.truthystring(do_download)

    use_original_filename = request.args.get('original_filename', False)
    use_original_filename = helpers.truthystring(use_original_filename)

    if do_download:
        if use_original_filename:
            download_as = photo.basename
        else:
            download_as = photo.id + photo.dot_extension

        download_as =  urllib.parse.quote(download_as)
        response = flask.make_response(send_file(photo.real_filepath))
        response.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % download_as
        return response
    else:
        return send_file(photo.real_filepath)


def get_photo_core(photoid):
    photo = P_photo(photoid)
    return photo

@site.route('/photo/<photoid>', methods=['GET'])
@session_manager.give_token
def get_photo_html(photoid):
    photo = get_photo_core(photoid)
    session = session_manager.get(request)
    return flask.render_template('photo.html', photo=photo, session=session)

@site.route('/photo/<photoid>.json', methods=['GET'])
@session_manager.give_token
def get_photo_json(photoid):
    photo = get_photo_core(photoid)
    photo = jsonify.photo(photo)
    photo = jsonify.make_json_response(photo)
    return photo

def get_search_core():
    warning_bag = objects.WarningBag()

    has_tags = request.args.get('has_tags')
    tag_musts = request.args.get('tag_musts')
    tag_mays = request.args.get('tag_mays')
    tag_forbids = request.args.get('tag_forbids')
    tag_expression = request.args.get('tag_expression')

    filename_terms = request.args.get('filename')
    extension = request.args.get('extension')
    extension_not = request.args.get('extension_not')
    mimetype = request.args.get('mimetype')

    limit = request.args.get('limit')
    # This is being pre-processed because the site enforces a maximum value
    # which the PhotoDB api does not.
    limit = searchhelpers.normalize_limit(limit, warning_bag=warning_bag)

    if limit is None:
        limit = 50
    else:
        limit = min(limit, 100)

    offset = request.args.get('offset')

    authors = request.args.get('author')

    orderby = request.args.get('orderby')
    area = request.args.get('area')
    width = request.args.get('width')
    height = request.args.get('height')
    ratio = request.args.get('ratio')
    bytes = request.args.get('bytes')
    duration = request.args.get('duration')
    created = request.args.get('created')

    # These are in a dictionary so I can pass them to the page template.
    search_kwargs = {
        'area': area,
        'width': width,
        'height': height,
        'ratio': ratio,
        'bytes': bytes,
        'duration': duration,

        'authors': authors,
        'created': created,
        'extension': extension,
        'extension_not': extension_not,
        'filename': filename_terms,
        'has_tags': has_tags,
        'mimetype': mimetype,
        'tag_musts': tag_musts,
        'tag_mays': tag_mays,
        'tag_forbids': tag_forbids,
        'tag_expression': tag_expression,

        'limit': limit,
        'offset': offset,
        'orderby': orderby,

        'warning_bag': warning_bag,
        'give_back_parameters': True
    }
    #print(search_kwargs)
    search_generator = P.search(**search_kwargs)
    # Because of the giveback, first element is cleaned up kwargs
    search_kwargs = next(search_generator)

    # The search has converted many arguments into sets or other types.
    # Convert them back into something that will display nicely on the search form.
    join_helper = lambda x: ', '.join(x) if x else None
    tagname_helper = lambda tags: [tag.qualified_name() for tag in tags] if tags else None
    filename_helper = lambda fn: ' '.join('"%s"' % part if ' ' in part else part for part in fn) if fn else None
    search_kwargs['extension'] = join_helper(search_kwargs['extension'])
    search_kwargs['extension_not'] = join_helper(search_kwargs['extension_not'])
    search_kwargs['mimetype'] = join_helper(search_kwargs['mimetype'])
    search_kwargs['filename'] = filename_helper(search_kwargs['filename'])
    search_kwargs['tag_musts'] = tagname_helper(search_kwargs['tag_musts'])
    search_kwargs['tag_mays'] = tagname_helper(search_kwargs['tag_mays'])
    search_kwargs['tag_forbids'] = tagname_helper(search_kwargs['tag_forbids'])

    search_results = list(search_generator)
    warnings = set()
    photos = []
    for item in search_results:
        if isinstance(item, objects.WarningBag):
            warnings.update(item.warnings)
        else:
            photos.append(item)

    # TAGS ON THIS PAGE
    total_tags = set()
    for photo in photos:
        for tag in photo.tags():
            total_tags.add(tag.qualified_name())
    total_tags = sorted(total_tags)

    # PREV-NEXT PAGE URLS
    offset = search_kwargs['offset'] or 0
    original_params = request.args.to_dict()
    if len(photos) == limit:
        next_params = helpers.edit_params(original_params, {'offset': offset + limit})
        next_page_url = '/search' + next_params
    else:
        next_page_url = None
    if offset > 0:
        prev_params = helpers.edit_params(original_params, {'offset': max(0, offset - limit)})
        prev_page_url = '/search' + prev_params
    else:
        prev_page_url = None

    view = request.args.get('view', 'grid')
    search_kwargs['view'] = view

    final_results = {
        'next_page_url': next_page_url,
        'prev_page_url': prev_page_url,
        'photos': photos,
        'total_tags': total_tags,
        'warnings': list(warnings),
        'search_kwargs': search_kwargs,
    }
    return final_results

@site.route('/search')
@session_manager.give_token
def get_search_html():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = P.export_tags(exporter=photodb.tag_export_qualname_map)
    session = session_manager.get(request)
    response = flask.render_template(
        'search.html',
        next_page_url=search_results['next_page_url'],
        prev_page_url=search_results['prev_page_url'],
        photos=search_results['photos'],
        qualname_map=json.dumps(qualname_map),
        search_kwargs=search_kwargs,
        session=session,
        total_tags=search_results['total_tags'],
        warnings=search_results['warnings'],
    )
    return response

@site.route('/search.json')
@session_manager.give_token
def get_search_json():
    search_results = get_search_core()
    search_results['photos'] = [jsonify.photo(photo, include_albums=False) for photo in search_results['photos']]
    return jsonify.make_json_response(search_results)


def get_tags_core(specific_tag=None):
    try:
        tags = P.export_tags(photodb.tag_export_easybake, specific_tag=specific_tag)
    except exceptions.NoSuchTag:
        flask.abort(404, 'That tag doesnt exist')
    tags = tags.split('\n')
    tags = [t for t in tags if t != '']
    tags = [(t, t.split('.')[-1].split('+')[0]) for t in tags]
    return tags

@site.route('/tags')
@site.route('/tags/<specific_tag>')
@session_manager.give_token
def get_tags_html(specific_tag=None):
    tags = get_tags_core(specific_tag)
    session = session_manager.get(request)
    return flask.render_template('tags.html', tags=tags, session=session)

@site.route('/tags.json')
@site.route('/tags/<specific_tag>.json')
@session_manager.give_token
def get_tags_json(specific_tag=None):
    tags = get_tags_core(specific_tag)
    tags = [t[0] for t in tags]
    return jsonify.make_json_response(tags)


@site.route('/thumbnail/<photoid>')
def get_thumbnail(photoid):
    photoid = photoid.split('.')[0]
    photo = P_photo(photoid)
    if photo.thumbnail:
        path = photo.thumbnail
    else:
        flask.abort(404, 'That file doesnt have a thumbnail')
    return send_file(path)


def get_user_core(username):
    user = P_user(username)
    return user

@site.route('/user/<username>', methods=['GET'])
@session_manager.give_token
def get_user_html(username):
    user = get_user_core(username)
    session = session_manager.get(request)
    return flask.render_template('user.html', user=user, session=session)

@site.route('/user/<username>.json', methods=['GET'])
@session_manager.give_token
def get_user_json(username):
    user = get_user_core(username)
    user = jsonify.user(user)
    user = jsonify.make_json_response(user)
    return user


@site.route('/album/<albumid>/add_tag', methods=['POST'])
@session_manager.give_token
def post_album_add_tag(albumid):
    '''
    Edit the album's title and description.
    Apply a tag to every photo in the album.
    '''
    response = {}
    album = P_album(albumid)

    tag = request.form['tagname'].strip()
    try:
        tag = P_tag(tag)
    except exceptions.NoSuchTag:
        response = {'error': 'That tag doesnt exist', 'tagname': tag}
        return jsonify.make_json_response(response, status=404)
    recursive = request.form.get('recursive', False)
    recursive = helpers.truthystring(recursive)
    album.add_tag_to_all(tag, nested_children=recursive)
    response['action'] = 'add_tag'
    response['tagname'] = tag.name
    return jsonify.make_json_response(response)


def post_photo_add_remove_tag_core(photoid, tagname, add_or_remove):
    photo = P_photo(photoid, response_type='json')
    tag = P_tag(tagname, response_type='json')

    if add_or_remove == 'add':
        photo.add_tag(tag)
    elif add_or_remove == 'remove':
        photo.remove_tag(tag)

    response = {'tagname': tagname}
    return jsonify.make_json_response(response)    

@site.route('/photo/<photoid>/add_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_add_tag(photoid):
    '''
    Add a tag to this photo.
    '''
    return post_photo_add_remove_tag_core(photoid, request.form['tagname'], 'add')

@site.route('/photo/<photoid>/remove_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_remove_tag(photoid):
    '''
    Remove a tag from this photo.
    '''
    return post_photo_add_remove_tag_core(photoid, request.form['tagname'], 'remove')


def post_tag_create_delete_core(tagname, function):
    try:
        response = function(tagname)
    except exceptions.TagTooLong:
        error_type = 'TAG_TOO_LONG'
        error_message = constants.ERROR_TAG_TOO_LONG.format(tag=tagname)
    except exceptions.TagTooShort:
        error_type = 'TAG_TOO_SHORT'
        error_message = constants.ERROR_TAG_TOO_SHORT.format(tag=tagname)
    except exceptions.CantSynonymSelf:
        error_type = 'TAG_SYNONYM_ITSELF'
        error_message = constants.ERROR_SYNONYM_ITSELF
    except exceptions.RecursiveGrouping as e:
        error_type = 'RECURSIVE_GROUPING'
        error_message = constants.ERROR_RECURSIVE_GROUPING
    except exceptions.NoSuchTag as e:
        error_type = 'NO_SUCH_TAG'
        error_message = constants.ERROR_NO_SUCH_TAG.format(tag=tagname)
    else:
        error_type = None
    
    if error_type is not None:
        status = 400
        response = {'error_type': error_type, 'error_message': error_message}
    else:
        status = 200

    return jsonify.make_json_response(response, status=status)

@site.route('/tags/create_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_create():
    '''
    Create a tag.
    '''
    return post_tag_create_delete_core(request.form['tagname'], create_tag)

@site.route('/tags/delete_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete():
    '''
    Delete a tag.
    '''
    return post_tag_create_delete_core(request.form['tagname'], delete_tag)

@site.route('/tags/delete_synonym', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete_synonym():
    '''
    Delete a synonym.
    '''
    return post_tag_create_delete_core(request.form['tagname'], delete_synonym)


@site.route('/apitest')
@session_manager.give_token
def apitest():
    response = flask.Response('testing')
    response.set_cookie('etiquette_session', 'don\'t overwrite me')
    return response

if __name__ == '__main__':
    #site.run(threaded=True)
    pass
