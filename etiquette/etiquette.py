import flask
from flask import request
import json
import mimetypes
import os
import random
import re
import requests
import sys
import time
import warnings

import constants
import decorators
import helpers
import jsonify
import phototagger

try:
    sys.path.append('C:\\git\\else\\Bytestring')
    sys.path.append('C:\\git\\else\\WebstreamZip')
    import bytestring
    import webstreamzip
except ImportError:
    # pip install
    # https://raw.githubusercontent.com/voussoir/else/master/_voussoirkit/voussoirkit.zip
    from vousoirkit import bytestring
    from vousoirkit import webstreamzip

site = flask.Flask(__name__)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')
site.debug = True

P = phototagger.PhotoDB()


####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################


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
    synonym = phototagger.normalize_tagname(synonym)
    try:
        master_tag = P.get_tag(synonym)
    except phototagger.NoSuchTag:
        flask.abort(404, 'That synonym doesnt exist')

    if synonym not in master_tag.synonyms():
        flask.abort(400, 'That name is not a synonym')

    master_tag.remove_synonym(synonym)
    return {'action':'delete_synonym', 'synonym': synonym}

def make_json_response(j, *args, **kwargs):
    dumped = json.dumps(j)
    response = flask.Response(dumped, *args, **kwargs)
    response.headers['Content-Type'] = 'application/json;charset=utf-8'
    return response

def P_album(albumid):
    try:
        return P.get_album(albumid)
    except phototagger.NoSuchAlbum:
        flask.abort(404, 'That album doesnt exist')

def P_photo(photoid):
    try:
        return P.get_photo(photoid)
    except phototagger.NoSuchPhoto:
        flask.abort(404, 'That photo doesnt exist')

def P_tag(tagname):
    try:
        return P.get_tag(tagname)
    except phototagger.NoSuchTag as e:
        flask.abort(404, 'That tag doesnt exist: %s' % e)

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
        outgoing_data = helpers.read_filebytes(filepath, range_min=range_min, range_max=range_max)

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
@decorators.give_session_token
def root():
    motd = random.choice(constants.MOTD_STRINGS)
    return flask.render_template('root.html', motd=motd)


@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    filename = os.path.join('static', 'favicon.png')
    return flask.send_file(filename)


def get_album_core(albumid):
    album = P_album(albumid)
    album = jsonify.album(album)
    album['sub_albums'] = [P_album(x) for x in album['sub_albums']]
    album['sub_albums'].sort(key=lambda x: (x.title or x.id).lower())
    album['sub_albums'] = [jsonify.album(x, minimal=True) for x in album['sub_albums']]
    return album

@site.route('/album/<albumid>')
@decorators.give_session_token
def get_album_html(albumid):
    album = get_album_core(albumid)
    response = flask.render_template(
        'album.html',
        album=album,
        photos=album['photos'],
    )
    return response

@site.route('/album/<albumid>.json')
@decorators.give_session_token
def get_album_json(albumid):
    album = get_album_core(albumid)
    return make_json_response(album)


@site.route('/album/<albumid>.tar')
def get_album_tar(albumid):
    album = P_album(albumid)
    photos = list(album.walk_photos())
    zipname_map = {p.real_filepath: '%s - %s' % (p.id, p.basename) for p in photos}
    streamed_zip = webstreamzip.stream_tar(zipname_map)
    content_length = sum(p.bytes for p in photos)
    outgoing_headers = {'Content-Type': 'application/octet-stream'}
    return flask.Response(streamed_zip, headers=outgoing_headers)


def get_albums_core():
    albums = P.get_albums()
    albums = [a for a in albums if a.parent() is None]
    albums = [jsonify.album(album, minimal=True) for album in albums]
    return albums

@site.route('/albums')
@decorators.give_session_token
def get_albums_html():
    albums = get_albums_core()
    return flask.render_template('albums.html', albums=albums)

@site.route('/albums.json')
@decorators.give_session_token
def get_albums_json():
    albums = get_albums_core()
    return make_json_response(albums)


@site.route('/file/<photoid>')
def get_file(photoid):
    requested_photoid = photoid
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
            download_as = photo.id + '.' + photo.extension

        ## Sorry, but otherwise the attachment filename gets terminated
        #download_as = download_as.replace(';', '-')
        download_as = download_as.replace('"', '\\"')
        response = flask.make_response(send_file(photo.real_filepath))
        response.headers['Content-Disposition'] = 'attachment; filename="%s"' % download_as
        return response
    else:
        return send_file(photo.real_filepath)


def get_photo_core(photoid):
    photo = P_photo(photoid)
    photo = jsonify.photo(photo)
    return photo

@site.route('/photo/<photoid>', methods=['GET'])
@decorators.give_session_token
def get_photo_html(photoid):
    photo = get_photo_core(photoid)
    photo['tags'].sort(key=lambda x: x['qualified_name'])
    return flask.render_template('photo.html', photo=photo)

@site.route('/photo/<photoid>.json', methods=['GET'])
@decorators.give_session_token
def get_photo_json(photoid):
    photo = get_photo_core(photoid)
    photo = make_json_response(photo)
    return photo


def get_search_core():
    #print(request.args)

    # FILENAME & EXTENSION
    filename_terms = request.args.get('filename', None)
    extension_string = request.args.get('extension', None)
    extension_not_string = request.args.get('extension_not', None)
    mimetype_string = request.args.get('mimetype', None)

    extension_list = helpers.comma_split(extension_string)
    extension_not_list = helpers.comma_split(extension_not_string)
    mimetype_list = helpers.comma_split(mimetype_string)

    # LIMIT
    limit = request.args.get('limit', '')
    if limit.isdigit():
        limit = int(limit)
        limit = min(100, limit)
    else:
        limit = 50

    # OFFSET
    offset = request.args.get('offset', None)
    if offset:
        offset = int(offset)
    else:
        offset = None

    # MUSTS, MAYS, FORBIDS
    qualname_map = P.export_tags(exporter=phototagger.tag_export_qualname_map)
    tag_musts = request.args.get('tag_musts', '').split(',')
    tag_mays = request.args.get('tag_mays', '').split(',')
    tag_forbids = request.args.get('tag_forbids', '').split(',')
    tag_expression = request.args.get('tag_expression', None)

    tag_musts = [qualname_map.get(tag, tag) for tag in tag_musts if tag != '']
    tag_mays = [qualname_map.get(tag, tag) for tag in tag_mays if tag != '']
    tag_forbids = [qualname_map.get(tag, tag) for tag in tag_forbids if tag != '']

    # ORDERBY
    orderby = request.args.get('orderby', None)
    if orderby:
        orderby = orderby.replace('-', ' ')
        orderby = orderby.replace('_', ' ')
        orderby = orderby.split(',')
    else:
        orderby = None

    # HAS_TAGS
    has_tags = request.args.get('has_tags', '')
    if has_tags == '':
        has_tags = None
    else:
        has_tags = helpers.truthystring(has_tags)

    # MINMAXERS
    area = request.args.get('area', None)
    width = request.args.get('width', None)
    height = request.args.get('height', None)
    ratio = request.args.get('ratio', None)
    bytes = request.args.get('bytes', None)
    duration = request.args.get('duration', None)
    created = request.args.get('created', None)

    # These are in a dictionary so I can pass them to the page template.
    search_kwargs = {
        'area': area,
        'width': width,
        'height': height,
        'ratio': ratio,
        'bytes': bytes,
        'duration': duration,

        'created': created,
        'extension': extension_list,
        'extension_not': extension_not_list,
        'filename': filename_terms,
        'has_tags': has_tags,
        'mimetype': mimetype_list,
        'tag_musts': tag_musts,
        'tag_mays': tag_mays,
        'tag_forbids': tag_forbids,
        'tag_expression': tag_expression,

        'limit': limit,
        'offset': offset,
        'orderby': orderby,

        'warn_bad_tags': True,
    }
    #print(search_kwargs)
    with warnings.catch_warnings(record=True) as catcher:
        photos = list(P.search(**search_kwargs))
        photos = [jsonify.photo(photo, include_albums=False) for photo in photos]
        warns = [str(warning.message) for warning in catcher]
    #print(warns)

    # TAGS ON THIS PAGE
    total_tags = set()
    for photo in photos:
        for tag in photo['tags']:
            total_tags.add(tag['qualified_name'])
    total_tags = sorted(total_tags)

    # PREV-NEXT PAGE URLS
    offset = offset or 0
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

    search_kwargs['extension'] = extension_string
    search_kwargs['extension_not'] = extension_not_string
    search_kwargs['mimetype'] = mimetype_string

    final_results = {
        'next_page_url': next_page_url,
        'prev_page_url': prev_page_url,
        'photos': photos,
        'total_tags': total_tags,
        'warns': warns,
        'search_kwargs': search_kwargs,
        'qualname_map': qualname_map,
    }
    return final_results

@site.route('/search')
@decorators.give_session_token
def get_search_html():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = search_results['qualname_map']
    response = flask.render_template(
        'search.html',
        next_page_url=search_results['next_page_url'],
        prev_page_url=search_results['prev_page_url'],
        photos=search_results['photos'],
        qualname_map=json.dumps(qualname_map),
        search_kwargs=search_kwargs,
        total_tags=search_results['total_tags'],
        warns=search_results['warns'],
    )
    return response

@site.route('/search.json')
@decorators.give_session_token
def get_search_json():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = search_results['qualname_map']
    include_qualname_map = request.args.get('include_map', False)
    include_qualname_map = helpers.truthystring(include_qualname_map)
    if not include_qualname_map:
        search_results.pop('qualname_map')
    return make_json_response(search_results)


@site.route('/static/<filename>')
def get_static(filename):
    filename = filename.replace('\\', os.sep)
    filename = filename.replace('/', os.sep)
    filename = os.path.join('static', filename)
    return flask.send_file(filename)


def get_tags_core(specific_tag=None):
    try:
        tags = P.export_tags(phototagger.tag_export_easybake, specific_tag=specific_tag)
    except phototagger.NoSuchTag:
        flask.abort(404, 'That tag doesnt exist')
    tags = tags.split('\n')
    tags = [t for t in tags if t != '']
    tags = [(t, t.split('.')[-1].split('+')[0]) for t in tags]
    return tags
    
@site.route('/tags')
@site.route('/tags/<specific_tag>')
@decorators.give_session_token
def get_tags_html(specific_tag=None):
    tags = get_tags_core(specific_tag)
    return flask.render_template('tags.html', tags=tags)

@site.route('/tags.json')
@site.route('/tags/<specific_tag>.json')
@decorators.give_session_token
def get_tags_json(specific_tag=None):
    tags = get_tags_core(specific_tag)
    tags = [t[0] for t in tags]
    return make_json_response(tags)


@site.route('/thumbnail/<photoid>')
def get_thumbnail(photoid):
    photoid = photoid.split('.')[0]
    photo = P_photo(photoid)
    if photo.thumbnail:
        path = photo.thumbnail
    else:
        flask.abort(404, 'That file doesnt have a thumbnail')
    return send_file(path)


@site.route('/album/<albumid>', methods=['POST'])
@site.route('/album/<albumid>.json', methods=['POST'])
@decorators.give_session_token
def post_edit_album(albumid):
    '''
    Edit the album's title and description.
    Apply a tag to every photo in the album.
    '''
    response = {}
    album = P_album(albumid)

    if 'add_tag' in request.form:
        action = 'add_tag'

        tag = request.form[action].strip()
        try:
            tag = P_tag(tag)
        except phototagger.NoSuchTag:
            response = {'error': 'That tag doesnt exist', 'tagname': tag}
            return make_json_response(response, status=404)
        recursive = request.form.get('recursive', False)
        recursive = helpers.truthystring(recursive)
        album.add_tag_to_all(tag, nested_children=recursive)
        response['action'] = action
        response['tagname'] = tag.name
        return make_json_response(response)


@site.route('/photo/<photoid>', methods=['POST'])
@site.route('/photo/<photoid>.json', methods=['POST'])
@decorators.give_session_token
def post_edit_photo(photoid):
    '''
    Add and remove tags from photos.
    '''
    response = {}
    photo = P_photo(photoid)

    if 'add_tag' in request.form:
        action = 'add_tag'
        method = photo.add_tag
    elif 'remove_tag' in request.form:
        action = 'remove_tag'
        method = photo.remove_tag
    else:
        flask.abort(400, 'Invalid action')

    tag = request.form[action].strip()
    if tag == '':
        flask.abort(400, 'No tag supplied')

    try:
        tag = P.get_tag(tag)
    except phototagger.NoSuchTag:
        response = {'error': 'That tag doesnt exist', 'tagname': tag}
        return make_json_response(response, status=404)

    method(tag)
    response['action'] = action
    #response['tagid'] = tag.id
    response['tagname'] = tag.name
    return make_json_response(response)


@site.route('/tags', methods=['POST'])
@decorators.give_session_token
def post_edit_tags():
    '''
    Create and delete tags and synonyms.
    '''
    print(request.form)
    status = 200
    if 'create_tag' in request.form:
        action = 'create_tag'
        method = create_tag
    elif 'delete_tag_synonym' in request.form:
        action = 'delete_tag_synonym'
        method = delete_synonym
    elif 'delete_tag' in request.form:
        action = 'delete_tag'
        method = delete_tag
    else:
        status = 400
        response = {'error': constants.ERROR_INVALID_ACTION}

    if status == 200:
        tag = request.form[action].strip()
        if tag == '':
            response = {'error': constants.ERROR_NO_TAG_GIVEN}
            status = 400

    if status == 200:
        # expect the worst
        status = 400
        try:
            response = method(tag)
        except phototagger.TagTooShort:
            response = {'error': constants.ERROR_TAG_TOO_SHORT, 'tagname': tag}
        except phototagger.CantSynonymSelf:
            response = {'error': constants.ERROR_SYNONYM_ITSELF, 'tagname': tag}
        except phototagger.NoSuchTag as e:
            response = {'error': constants.ERROR_NO_SUCH_TAG, 'tagname': tag}
        except ValueError as e:
            response = {'error': e.args[0], 'tagname': tag}
        else:
            status = 200

    response = json.dumps(response)
    response = flask.Response(response, status=status)
    return response


if __name__ == '__main__':
    site.run(threaded=True)
