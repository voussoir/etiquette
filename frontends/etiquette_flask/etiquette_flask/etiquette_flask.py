import flask
from flask import request
import json
import mimetypes
import os
import random
import traceback
import urllib.parse
import warnings
import zipstream

import etiquette

from . import decorators
from . import jsonify
from . import sessions

from voussoirkit import pathclass


root_dir = pathclass.Path(__file__).parent.parent

TEMPLATE_DIR = root_dir.with_child('templates')
STATIC_DIR = root_dir.with_child('static')
FAVICON_PATH = STATIC_DIR.with_child('favicon.png')

site = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR.absolute_path,
    static_folder=STATIC_DIR.absolute_path,
)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')
site.jinja_env.trim_blocks = True
site.jinja_env.lstrip_blocks = True
site.debug = True

P = etiquette.photodb.PhotoDB()

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

    try:
        master_tag = P.get_tag(synonym)
    except etiquette.exceptions.NoSuchTag as e:
        raise etiquette.exceptions.NoSuchSynonym(*e.given_args, **e.given_kwargs)
    else:
        master_tag.remove_synonym(synonym)

    return {'action':'delete_synonym', 'synonym': synonym}

def P_wrapper(function):
    def P_wrapped(thingid, response_type='html'):
        try:
            return function(thingid)

        except etiquette.exceptions.EtiquetteException as e:
            if isinstance(e, etiquette.exceptions.NoSuch):
                status = 404
            else:
                status = 400

            if response_type == 'html':
                flask.abort(status, e.error_message)
            else:
                response = etiquette.jsonify.exception(e)
                response = jsonify.make_json_response(response, status=status)
                flask.abort(response)

        except Exception as e:
            traceback.print_exc()
            if response_type == 'html':
                flask.abort(500)
            else:
                flask.abort(etiquette.jsonify.make_json_response({}, status=500))

    return P_wrapped

@P_wrapper
def P_album(albumid):
    return P.get_album(albumid)

@P_wrapper
def P_photo(photoid):
    return P.get_photo(photoid)

@P_wrapper
def P_tag(tagname):
    return P.get_tag(tagname)

@P_wrapper
def P_user(username):
    return P.get_user(username=username)

def send_file(filepath, override_mimetype=None):
    '''
    Range-enabled file sending.
    '''
    try:
        file_size = os.path.getsize(filepath)
    except FileNotFoundError:
        flask.abort(404)

    outgoing_headers = {}
    if override_mimetype is not None:
        mimetype = override_mimetype
    else:
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
        outgoing_data = etiquette.helpers.read_filebytes(
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


def get_album_core(albumid):
    album = P_album(albumid)
    return album

def get_albums_core():
    albums = list(P.get_root_albums())
    albums.sort(key=lambda x: x.display_name.lower())
    return albums

def get_search_core():
    warning_bag = etiquette.objects.WarningBag()

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
    limit = etiquette.searchhelpers.normalize_limit(limit, warning_bag=warning_bag)

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
    search_kwargs['extension'] = join_helper(search_kwargs['extension'])
    search_kwargs['extension_not'] = join_helper(search_kwargs['extension_not'])
    search_kwargs['mimetype'] = join_helper(search_kwargs['mimetype'])

    tagname_helper = lambda tags: [tag.qualified_name() for tag in tags] if tags else None
    search_kwargs['tag_musts'] = tagname_helper(search_kwargs['tag_musts'])
    search_kwargs['tag_mays'] = tagname_helper(search_kwargs['tag_mays'])
    search_kwargs['tag_forbids'] = tagname_helper(search_kwargs['tag_forbids'])

    search_results = list(search_generator)
    warnings = set()
    photos = []
    for item in search_results:
        if isinstance(item, etiquette.objects.WarningBag):
            warnings.update(item.warnings)
        else:
            photos.append(item)

    # TAGS ON THIS PAGE
    total_tags = set()
    for photo in photos:
        for tag in photo.tags():
            total_tags.add(tag)
    total_tags = sorted(total_tags, key=lambda t: t.qualified_name())

    # PREV-NEXT PAGE URLS
    offset = search_kwargs['offset'] or 0
    original_params = request.args.to_dict()
    original_params['limit'] = limit
    if len(photos) == limit:
        next_params = original_params.copy()
        next_params['offset'] = offset + limit
        next_params = etiquette.helpers.dict_to_params(next_params)
        next_page_url = '/search' + next_params
    else:
        next_page_url = None

    if offset > 0:
        prev_params = original_params.copy()
        prev_params['offset'] = max(0, offset - limit)
        prev_params = etiquette.helpers.dict_to_params(prev_params)
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

def get_tags_core(specific_tag=None):
    if specific_tag is None:
        tags = P.get_tags()
    else:
        tags = specific_tag.walk_children()
    tags = list(tags)
    tags.sort(key=lambda x: x.qualified_name())
    return tags

def get_user_core(username):
    user = P_user(username)
    return user

def post_photo_add_remove_tag_core(photoid, tagname, add_or_remove):
    photo = P_photo(photoid, response_type='json')
    tag = P_tag(tagname, response_type='json')

    try:
        if add_or_remove == 'add':
            photo.add_tag(tag)
        elif add_or_remove == 'remove':
            photo.remove_tag(tag)
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        response = jsonify.make_json_response(response, status=400)
        flask.abort(response)

    response = {'tagname': tag.name}
    return jsonify.make_json_response(response)

def post_tag_create_delete_core(tagname, function):
    try:
        response = function(tagname)
        status = 200
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        status = 400
    #print(response)

    return jsonify.make_json_response(response, status=status)


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
    album = etiquette.jsonify.album(album)
    album['sub_albums'] = [P_album(x) for x in album['sub_albums']]
    album['sub_albums'].sort(key=lambda x: (x.title or x.id).lower())
    album['sub_albums'] = [etiquette.jsonify.album(x, minimal=True) for x in album['sub_albums']]
    return jsonify.make_json_response(album)

@site.route('/album/<albumid>.zip')
def get_album_zip(albumid):
    album = P_album(albumid)

    recursive = request.args.get('recursive', True)
    recursive = etiquette.helpers.truthystring(recursive)

    arcnames = etiquette.helpers.album_zip_filenames(album, recursive=recursive)

    streamed_zip = zipstream.ZipFile()
    for (real_filepath, arcname) in arcnames.items():
        streamed_zip.write(real_filepath, arcname=arcname)

    # Add the album metadata as an {id}.txt file within each directory.
    directories = etiquette.helpers.album_zip_directories(album, recursive=recursive)
    for (inner_album, directory) in directories.items():
        text = []
        if inner_album.title:
            text.append('Title: ' + inner_album.title)
        if inner_album.description:
            text.append('Description: ' + inner_album.description)
        if not text:
            continue
        text = '\r\n\r\n'.join(text)
        streamed_zip.writestr(
            arcname=os.path.join(directory, 'album %s.txt' % inner_album.id),
            data=text.encode('utf-8'),
        )

    if album.title:
        download_as = 'album %s - %s.zip' % (album.id, album.title)
    else:
        download_as = 'album %s.zip' % album.id

    download_as = etiquette.helpers.normalize_filepath(download_as)
    download_as = urllib.parse.quote(download_as)
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename*=UTF-8\'\'%s' % download_as,

    }
    return flask.Response(streamed_zip, headers=outgoing_headers)

@site.route('/album/<albumid>/add_tag', methods=['POST'])
@session_manager.give_token
def post_album_add_tag(albumid):
    '''
    Apply a tag to every photo in the album.
    '''
    response = {}
    album = P_album(albumid)

    tag = request.form['tagname'].strip()
    try:
        tag = P_tag(tag)
    except etiquette.exceptions.NoSuchTag as e:
        response = etiquette.jsonify.exception(e)
        return jsonify.make_json_response(response, status=404)
    recursive = request.form.get('recursive', False)
    recursive = etiquette.helpers.truthystring(recursive)
    album.add_tag_to_all(tag, nested_children=recursive)
    response['action'] = 'add_tag'
    response['tagname'] = tag.name
    return jsonify.make_json_response(response)

@site.route('/album/<albumid>/edit', methods=['POST'])
@session_manager.give_token
def post_album_edit(albumid):
    '''
    Edit the title / description.
    '''
    album = P_album(albumid)

    title = request.form.get('title', None)
    description = request.form.get('description', None)
    try:
        album.edit(title=title, description=description)
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        response = jsonify.make_json_response(response, status=400)
        flask.abort(response)
    response = etiquette.jsonify.album(album, minimal=True)
    return jsonify.make_json_response(response)


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
    albums = [etiquette.jsonify.album(album, minimal=True) for album in albums]
    return jsonify.make_json_response(albums)

@site.route('/albums/create_album', methods=['POST'])
def post_albums_create():
    print(dict(request.form))
    title = request.form.get('title', None)
    description = request.form.get('description', None)
    parent = request.form.get('parent', None)
    if parent is not None:
        parent = P_album(parent)

    album = P.new_album(title=title, description=description)
    if parent is not None:
        parent.add(album)
    response = etiquette.jsonify.album(album, minimal=False)
    return jsonify.make_json_response(response)


@site.route('/bookmarks')
@session_manager.give_token
def get_bookmarks_html():
    session = session_manager.get(request)
    bookmarks = list(P.get_bookmarks())
    return flask.render_template('bookmarks.html', bookmarks=bookmarks, session=session)

@site.route('/bookmarks.json')
@session_manager.give_token
def get_bookmarks_json():
    bookmarks = [etiquette.jsonify.bookmark(b) for b in P.get_bookmarks()]
    return jsonify.make_json_response(bookmarks)

@site.route('/bookmarks/create_bookmark', methods=['POST'])
@decorators.required_fields(['url'], forbid_whitespace=True)
def post_bookmarks_create():
    url = request.form['url']
    title = request.form.get('title', None)
    try:
        bookmark = P.new_bookmark(url=url, title=title)
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        response = jsonify.make_json_response(response, status=400)
        flask.abort(response)
    response = etiquette.jsonify.bookmark(bookmark)
    response = jsonify.make_json_response(response)
    return response


@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    return flask.send_file(FAVICON_PATH.absolute_path)


@site.route('/file/<photoid>')
def get_file(photoid):
    photoid = photoid.split('.')[0]
    photo = P.get_photo(photoid)

    do_download = request.args.get('download', False)
    do_download = etiquette.helpers.truthystring(do_download)

    use_original_filename = request.args.get('original_filename', False)
    use_original_filename = etiquette.helpers.truthystring(use_original_filename)

    if do_download:
        if use_original_filename:
            download_as = photo.basename
        else:
            download_as = photo.id + photo.dot_extension

        download_as = etiquette.helpers.normalize_filepath(download_as)
        download_as =  urllib.parse.quote(download_as)
        response = flask.make_response(send_file(photo.real_filepath))
        response.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % download_as
        return response
    else:
        return send_file(photo.real_filepath, override_mimetype=photo.mimetype)


@site.route('/login', methods=['GET'])
@session_manager.give_token
def get_login():
    session = session_manager.get(request)
    return flask.render_template('login.html', session=session)

@site.route('/login', methods=['POST'])
@session_manager.give_token
@decorators.required_fields(['username', 'password'])
def post_login():
    if session_manager.get(request):
        e = etiquette.exceptions.AlreadySignedIn()
        response = etiquette.jsonify.exception(e)
        return jsonify.make_json_response(response, status=403)

    username = request.form['username']
    password = request.form['password']
    try:
        # Consideration: Should the server hash the password to discourage
        # information (user exists) leak via response time?
        # Currently I think not, because they can check if the account
        # page 404s anyway.
        user = P.get_user(username=username)
        user = P.login(user.id, password)
    except (etiquette.exceptions.NoSuchUser, etiquette.exceptions.WrongLogin):
        e = etiquette.exceptions.WrongLogin()
        response = etiquette.jsonify.exception(e)
        return jsonify.make_json_response(response, status=422)
    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})

@site.route('/logout', methods=['GET', 'POST'])
@session_manager.give_token
def logout():
    session_manager.remove(request)
    response = flask.Response('redirect', status=302, headers={'Location': back_url()})
    return response


@site.route('/photo/<photoid>', methods=['GET'])
@session_manager.give_token
def get_photo_html(photoid):
    photo = P_photo(photoid, response_type='html')
    session = session_manager.get(request)
    return flask.render_template('photo.html', photo=photo, session=session)

@site.route('/photo/<photoid>.json', methods=['GET'])
@session_manager.give_token
def get_photo_json(photoid):
    photo = P_photo(photoid, response_type='json')
    photo = etiquette.jsonify.photo(photo)
    photo = jsonify.make_json_response(photo)
    return photo

@site.route('/photo/<photoid>/add_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_add_tag(photoid):
    '''
    Add a tag to this photo.
    '''
    return post_photo_add_remove_tag_core(photoid, request.form['tagname'], 'add')

@site.route('/photo/<photoid>/refresh_metadata', methods=['POST'])
def post_photo_refresh_metadata(photoid):
    '''
    Refresh the file metadata.
    '''
    P.caches['photo'].remove(photoid)
    photo = P_photo(photoid, response_type='json')
    try:
        photo.reload_metadata()
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        response = jsonify.make_json_response(response, status=400)
        flask.abort(response)
    return jsonify.make_json_response({})

@site.route('/photo/<photoid>/remove_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_remove_tag(photoid):
    '''
    Remove a tag from this photo.
    '''
    return post_photo_add_remove_tag_core(photoid, request.form['tagname'], 'remove')


@site.route('/register', methods=['GET'])
def get_register():
    return flask.redirect('/login')

@site.route('/register', methods=['POST'])
@session_manager.give_token
@decorators.required_fields(['username', 'password_1', 'password_2'])
def post_register():
    if session_manager.get(request):
        e = etiquette.exceptions.AlreadySignedIn()
        response = etiquette.jsonify.exception(e)
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

    try:
        user = P.register_user(username, password_1)
    except etiquette.exceptions.EtiquetteException as e:
        response = etiquette.jsonify.exception(e)
        return jsonify.make_json_response(response, status=400)

    session = sessions.Session(request, user)
    session_manager.add(session)
    return jsonify.make_json_response({})


@site.route('/search')
@session_manager.give_token
def get_search_html():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = etiquette.tag_export.qualified_names(P.get_tags())
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
    search_results['photos'] = [
        etiquette.jsonify.photo(photo, include_albums=False) for photo in search_results['photos']
    ]
    return jsonify.make_json_response(search_results)


@site.route('/tag/<specific_tag>')
@site.route('/tags')
@session_manager.give_token
def get_tags_html(specific_tag=None):
    if specific_tag is not None:
        specific_tag = P_tag(specific_tag, response_type='html')
    tags = get_tags_core(specific_tag)
    session = session_manager.get(request)
    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)
    response = flask.render_template(
        'tags.html',
        include_synonyms=include_synonyms,
        session=session,
        specific_tag=specific_tag,
        tags=tags,
    )
    return response

@site.route('/tag/<specific_tag>.json')
@site.route('/tags.json')
@session_manager.give_token
def get_tags_json(specific_tag=None):
    if specific_tag is not None:
        specific_tag = P_tag(specific_tag, response_type='json')
    tags = get_tags_core(specific_tag=specific_tag)
    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)
    tags = [etiquette.jsonify.tag(tag, include_synonyms=include_synonyms) for tag in tags]
    return jsonify.make_json_response(tags)

@site.route('/tag/<specific_tag>/edit', methods=['POST'])
def post_tag_edit(specific_tag):
    tag = P_tag(specific_tag)
    description = request.form.get('description', None)
    tag.edit(description=description)

    response = etiquette.jsonify.tag(tag)
    response = jsonify.make_json_response(response)
    return response

@site.route('/tags/<specific_tag>')
@site.route('/tags/<specific_tag>.json')
def get_tags_specific_redirect(specific_tag=None):
    return flask.redirect(request.url.replace('/tags/', '/tag/'))

@site.route('/tags/create_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_create():
    '''
    Create a tag.
    '''
    return post_tag_create_delete_core(request.form['tagname'], create_tag)

@site.route('/tags/delete_synonym', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete_synonym():
    '''
    Delete a synonym.
    '''
    return post_tag_create_delete_core(request.form['tagname'], delete_synonym)

@site.route('/tags/delete_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete():
    '''
    Delete a tag.
    '''
    return post_tag_create_delete_core(request.form['tagname'], delete_tag)


@site.route('/thumbnail/<photoid>')
def get_thumbnail(photoid):
    photoid = photoid.split('.')[0]
    photo = P_photo(photoid)
    if photo.thumbnail:
        path = photo.thumbnail
    else:
        flask.abort(404, 'That file doesnt have a thumbnail')
    return send_file(path)


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
    user = etiquette.jsonify.user(user)
    return jsonify.make_json_response(user)


@site.route('/apitest')
@session_manager.give_token
def apitest():
    response = flask.Response('testing')
    response.set_cookie('etiquette_session', 'don\'t overwrite me')
    return response

if __name__ == '__main__':
    #site.run(threaded=True)
    pass
