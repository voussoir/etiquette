import flask; from flask import request
import os
import urllib.parse
import zipstream

import etiquette

from .. import decorators
from .. import jsonify
from .. import common

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
    album['sub_albums'] = [common.P_album(x) for x in album['sub_albums']]
    album['sub_albums'].sort(key=lambda x: (x.title or x.id).lower())
    album['sub_albums'] = [etiquette.jsonify.album(x, minimal=True) for x in album['sub_albums']]
    return jsonify.make_json_response(album)

@site.route('/album/<album_id>.zip')
def get_album_zip(album_id):
    album = common.P_album(album_id)

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

    download_as = etiquette.helpers.remove_path_badchars(download_as)
    download_as = urllib.parse.quote(download_as)
    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename*=UTF-8\'\'%s' % download_as,

    }
    return flask.Response(streamed_zip, headers=outgoing_headers)

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
    photos = [common.P_photo(photo_id) for photo_id in photo_ids]
    for photo in photos:
        album.add_photo(photo, commit=False)
    common.P.commit()
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
    photos = [common.P_photo(photo_id) for photo_id in photo_ids]
    for photo in photos:
        album.remove_photo(photo, commit=False)
    common.P.commit()
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
    return flask.render_template('albums.html', albums=albums, session=session)

@site.route('/albums.json')
@session_manager.give_token
def get_albums_json():
    albums = get_albums_core()
    albums = [etiquette.jsonify.album(album, minimal=True) for album in albums]
    return jsonify.make_json_response(albums)

# Album create and delete ##########################################################################

@site.route('/albums/create_album', methods=['POST'])
@decorators.catch_etiquette_exception
def post_albums_create():
    title = request.form.get('title', None)
    description = request.form.get('description', None)
    parent = request.form.get('parent', None)
    if parent is not None:
        parent = common.P_album(parent)

    album = common.P.new_album(title=title, description=description)
    if parent is not None:
        parent.add_child(album)
    response = etiquette.jsonify.album(album, minimal=False)
    return jsonify.make_json_response(response)
