import flask; from flask import request
import os
import urllib.parse

from voussoirkit import flasktools
from voussoirkit import gentools
from voussoirkit import stringtools

import etiquette

from .. import common

site = common.site
session_manager = common.session_manager

# Individual albums ################################################################################

@site.route('/album/<album_id>')
def get_album_html(album_id):
    common.permission_manager.basic()
    album = common.P_album(album_id, response_type='html')
    response = common.render_template(
        request,
        'album.html',
        album=album,
        view=request.args.get('view', 'grid'),
    )
    return response

@site.route('/album/<album_id>.json')
def get_album_json(album_id):
    common.permission_manager.basic()
    album = common.P_album(album_id, response_type='json')
    album = album.jsonify()
    return flasktools.json_response(album)

@site.route('/album/<album_id>.zip')
def get_album_zip(album_id):
    common.permission_manager.basic()
    album = common.P_album(album_id, response_type='html')

    recursive = request.args.get('recursive', True)
    recursive = stringtools.truthystring(recursive)

    streamed_zip = etiquette.helpers.zip_album(album, recursive=recursive)

    if album.title:
        download_as = f'album {album.id} - {album.title}.zip'
    else:
        download_as = f'album {album.id}.zip'

    download_as = etiquette.helpers.remove_path_badchars(download_as)
    download_as = urllib.parse.quote(download_as)
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{download_as}',
    }

    return flask.Response(streamed_zip, headers=outgoing_headers)

@site.route('/album/<album_id>/add_child', methods=['POST'])
@flasktools.required_fields(['child_id'], forbid_whitespace=True)
def post_album_add_child(album_id):
    common.permission_manager.basic()
    child_ids = stringtools.comma_space_split(request.form['child_id'])
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        children = list(common.P_albums(child_ids, response_type='json'))
        print(children)
        album.add_children(children)

    response = album.jsonify()
    return flasktools.json_response(response)

@site.route('/album/<album_id>/remove_child', methods=['POST'])
@flasktools.required_fields(['child_id'], forbid_whitespace=True)
def post_album_remove_child(album_id):
    common.permission_manager.basic()
    child_ids = stringtools.comma_space_split(request.form['child_id'])
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        children = list(common.P_albums(child_ids, response_type='json'))
        album.remove_children(children)
    response = album.jsonify()
    return flasktools.json_response(response)

@site.route('/album/<album_id>/remove_thumbnail_photo', methods=['POST'])
def post_album_remove_thumbnail_photo(album_id):
    common.permission_manager.basic()
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        album.set_thumbnail_photo(None)
    return flasktools.json_response(album.jsonify())

@site.route('/album/<album_id>/refresh_directories', methods=['POST'])
def post_album_refresh_directories(album_id):
    common.permission_manager.basic()
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        for directory in album.get_associated_directories():
            if not directory.is_dir:
                continue
            digest = common.P.digest_directory(directory, new_photo_ratelimit=0.1)
            gentools.run(digest)
    return flasktools.json_response({})

@site.route('/album/<album_id>/set_thumbnail_photo', methods=['POST'])
@flasktools.required_fields(['photo_id'], forbid_whitespace=True)
def post_album_set_thumbnail_photo(album_id):
    common.permission_manager.basic()
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        photo = common.P_photo(request.form['photo_id'], response_type='json')
        album.set_thumbnail_photo(photo)
    return flasktools.json_response(album.jsonify())

# Album photo operations ###########################################################################

@site.route('/album/<album_id>/add_photo', methods=['POST'])
@flasktools.required_fields(['photo_id'], forbid_whitespace=True)
def post_album_add_photo(album_id):
    '''
    Add a photo or photos to this album.
    '''
    common.permission_manager.basic()
    photo_ids = stringtools.comma_space_split(request.form['photo_id'])
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        photos = list(common.P_photos(photo_ids, response_type='json'))
        album.add_photos(photos)
    response = album.jsonify()
    return flasktools.json_response(response)

@site.route('/album/<album_id>/remove_photo', methods=['POST'])
@flasktools.required_fields(['photo_id'], forbid_whitespace=True)
def post_album_remove_photo(album_id):
    '''
    Remove a photo or photos from this album.
    '''
    common.permission_manager.basic()
    photo_ids = stringtools.comma_space_split(request.form['photo_id'])
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        photos = list(common.P_photos(photo_ids, response_type='json'))
        album.remove_photos(photos)
    response = album.jsonify()
    return flasktools.json_response(response)

# Album tag operations #############################################################################

@site.route('/album/<album_id>/add_tag', methods=['POST'])
def post_album_add_tag(album_id):
    '''
    Apply a tag to every photo in the album.
    '''
    common.permission_manager.basic()
    response = {}
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')

        tag = request.form['tagname'].strip()
        try:
            tag = common.P_tag(tag, response_type='json')
        except etiquette.exceptions.NoSuchTag as exc:
            response = exc.jsonify()
            return flasktools.json_response(response, status=404)
        recursive = request.form.get('recursive', False)
        recursive = stringtools.truthystring(recursive)
        album.add_tag_to_all(tag, nested_children=recursive)
    response['action'] = 'add_tag'
    response['tagname'] = tag.name
    return flasktools.json_response(response)

# Album metadata operations ########################################################################

@site.route('/album/<album_id>/edit', methods=['POST'])
def post_album_edit(album_id):
    '''
    Edit the title / description.
    '''
    common.permission_manager.basic()
    title = request.form.get('title', None)
    description = request.form.get('description', None)

    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        album.edit(title=title, description=description)

    response = album.jsonify(
        include_parents=False,
        include_children=False,
        include_photos=False,
    )
    return flasktools.json_response(response)

@site.route('/album/<album_id>/show_in_folder', methods=['POST'])
def post_album_show_in_folder(album_id):
    common.permission_manager.basic()
    if not request.is_localhost:
        flask.abort(403)

    album = common.P_album(album_id, response_type='json')
    directories = album.get_associated_directories()
    if len(directories) != 1:
        flask.abort(400)
    directory = directories.pop()

    if os.name == 'nt':
        command = f'start explorer.exe "{directory.absolute_path}"'
        os.system(command)
        return flasktools.json_response({})

    flask.abort(501)

# Album listings ###################################################################################

@site.route('/all_albums.json')
@common.permission_manager.basic_decorator
@flasktools.cached_endpoint(max_age=15)
def get_all_album_names():
    all_albums = {album.id: album.display_name for album in common.P.get_albums()}
    response = {'albums': all_albums}
    return flasktools.json_response(response)

@site.route('/albums')
def get_albums_html():
    common.permission_manager.basic()
    albums = list(common.P.get_root_albums())
    albums.sort(key=lambda x: x.display_name.lower())
    response = common.render_template(
        request,
        'album.html',
        albums=albums,
        view=request.args.get('view', 'grid'),
    )
    return response

@site.route('/albums.json')
def get_albums_json():
    common.permission_manager.basic()
    albums = list(common.P.get_albums())
    albums.sort(key=lambda x: x.display_name.lower())
    albums = [album.jsonify(include_photos=False) for album in albums]
    return flasktools.json_response(albums)

# Album create and delete ##########################################################################

@site.route('/albums/create_album', methods=['POST'])
def post_albums_create():
    common.permission_manager.basic()
    title = request.form.get('title', None)
    description = request.form.get('description', None)
    parent_id = request.form.get('parent_id', None)
    if parent_id is not None:
        parent = common.P_album(parent_id, response_type='json')

    user = session_manager.get(request).user

    with common.P.transaction:
        album = common.P.new_album(title=title, description=description, author=user)
        if parent_id is not None:
            parent.add_child(album)

    response = album.jsonify(
        include_parents=False,
        include_children=False,
        include_photos=False,
    )
    return flasktools.json_response(response)

@site.route('/album/<album_id>/delete', methods=['POST'])
def post_album_delete(album_id):
    common.permission_manager.basic()
    with common.P.transaction:
        album = common.P_album(album_id, response_type='json')
        album.delete()
    return flasktools.json_response({})
