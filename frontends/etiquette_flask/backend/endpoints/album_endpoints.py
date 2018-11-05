import flask; from flask import request
import os
import urllib.parse
import zipstream

import etiquette

from .. import common
from .. import decorators
from .. import jsonify

site = common.site
session_manager = common.session_manager


# Individual albums ################################################################################

@site.route('/album/<album_id>')
@session_manager.give_token
def get_album_html(album_id):
    album = common.P_album(album_id)
    session = session_manager.get(request)
    response = flask.render_template(
        'album.html',
        album=album,
        session=session,
        view=request.args.get('view', 'grid'),
    )
    return response

@site.route('/album/<album_id>.json')
@session_manager.give_token
def get_album_json(album_id):
    album = common.P_album(album_id)
    album = etiquette.jsonify.album(album)
    return jsonify.make_json_response(album)

@site.route('/album/<album_id>.zip')
def get_album_zip(album_id):
    album = common.P_album(album_id)

    recursive = request.args.get('recursive', True)
    recursive = etiquette.helpers.truthystring(recursive)

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
@decorators.catch_etiquette_exception
@decorators.required_fields(['child_id'], forbid_whitespace=True)
def post_album_add_child(album_id):
    album = common.P_album(album_id)
    child = common.P_album(request.form['child_id'])
    album.add_child(child)
    response = etiquette.jsonify.album(child)
    return jsonify.make_json_response(response)

@site.route('/album/<album_id>/remove_child', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['child_id'], forbid_whitespace=True)
def post_album_remove_child(album_id):
    album = common.P_album(album_id)
    child = common.P_album(request.form['child_id'])
    album.remove_child(child)
    response = etiquette.jsonify.album(child)
    return jsonify.make_json_response(response)

# Album photo operations ###########################################################################

@site.route('/album/<album_id>/add_photo', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
@decorators.required_fields(['photo_id'], forbid_whitespace=True)
def post_album_add_photo(album_id):
    '''
    Add a photo or photos to this album.
    '''
    response = {}
    album = common.P_album(album_id)

    photo_ids = etiquette.helpers.comma_space_split(request.form['photo_id'])
    photos = list(common.P_photos(photo_ids))
    album.add_photos(photos)
    return jsonify.make_json_response(response)

@site.route('/album/<album_id>/remove_photo', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
@decorators.required_fields(['photo_id'], forbid_whitespace=True)
def post_album_remove_photo(album_id):
    '''
    Remove a photo or photos from this album.
    '''
    response = {}
    album = common.P_album(album_id)

    photo_ids = etiquette.helpers.comma_space_split(request.form['photo_id'])
    photos = list(common.P_photos(photo_ids))
    album.remove_photos(photos)
    return jsonify.make_json_response(response)

# Album tag operations #############################################################################

@site.route('/album/<album_id>/add_tag', methods=['POST'])
@decorators.catch_etiquette_exception
@session_manager.give_token
def post_album_add_tag(album_id):
    '''
    Apply a tag to every photo in the album.
    '''
    response = {}
    album = common.P_album(album_id)

    tag = request.form['tagname'].strip()
    try:
        tag = common.P_tag(tag)
    except etiquette.exceptions.NoSuchTag as exc:
        response = etiquette.jsonify.exception(exc)
        return jsonify.make_json_response(response, status=404)
    recursive = request.form.get('recursive', False)
    recursive = etiquette.helpers.truthystring(recursive)
    album.add_tag_to_all(tag, nested_children=recursive)
    response['action'] = 'add_tag'
    response['tagname'] = tag.name
    return jsonify.make_json_response(response)

# Album metadata operations ########################################################################

@site.route('/album/<album_id>/edit', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
def post_album_edit(album_id):
    '''
    Edit the title / description.
    '''
    album = common.P_album(album_id)

    title = request.form.get('title', None)
    description = request.form.get('description', None)
    album.edit(title=title, description=description)
    response = etiquette.jsonify.album(album, minimal=True)
    return jsonify.make_json_response(response)

# Album listings ###################################################################################

def get_albums_core():
    albums = list(common.P.get_root_albums())
    albums.sort(key=lambda x: x.display_name.lower())
    return albums

@site.route('/albums')
@session_manager.give_token
def get_albums_html():
    albums = get_albums_core()
    session = session_manager.get(request)
    return flask.render_template('album.html', albums=albums, session=session)

@site.route('/albums.json')
@session_manager.give_token
def get_albums_json():
    albums = get_albums_core()
    albums = [etiquette.jsonify.album(album, minimal=True) for album in albums]
    return jsonify.make_json_response(albums)

# Album create and delete ##########################################################################

@site.route('/albums/create_album', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
def post_albums_create():
    title = request.form.get('title', None)
    description = request.form.get('description', None)
    parent_id = request.form.get('parent_id', None)
    if parent_id is not None:
        parent = common.P_album(parent_id)

    user = session_manager.get(request).user

    album = common.P.new_album(title=title, description=description, author=user)
    if parent_id is not None:
        parent.add_child(album)

    response = etiquette.jsonify.album(album, minimal=False)
    return jsonify.make_json_response(response)

@site.route('/album/<album_id>/delete', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
def post_album_delete(album_id):
    album = common.P_album(album_id, response_type='json')
    album.delete()
    return jsonify.make_json_response({})