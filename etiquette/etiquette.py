import distutils.util
import flask
from flask import request
import functools
import json
import math
import mimetypes
import os
import random
import re
import requests
import sys
import time
import uuid
import warnings

import phototagger
sys.path.append('C:\\git\\else\\Bytestring'); import bytestring

site = flask.Flask(__name__)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)
site.jinja_env.add_extension('jinja2.ext.do')

P = phototagger.PhotoDB()

FILE_READ_CHUNK = 2 ** 20

MOTD_STRINGS = [
'Good morning, Paul. What will your first sequence of the day be?',
#'Buckle up, it\'s time to:',
]

ERROR_INVALID_ACTION = 'Invalid action'
ERROR_NO_TAG_GIVEN = 'No tag name supplied'
ERROR_TAG_TOO_SHORT = 'Not enough valid chars'
ERROR_SYNONYM_ITSELF = 'Cant apply synonym to itself'
ERROR_NO_SUCH_TAG = 'Doesn\'t exist'

####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################

def give_session_token(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        # Inject new token so the function doesn't know the difference
        token = request.cookies.get('etiquette_session', None)
        if not token:
            token = generate_session_token()
            request.cookies = dict(request.cookies)
            request.cookies['etiquette_session'] = token

        ret = function(*args, **kwargs)

        # Send the token back to the client
        if not isinstance(ret, flask.Response):
            ret = flask.Response(ret)
        ret.set_cookie('etiquette_session', value=token, max_age=60)

        return ret
    return wrapped

def _helper_comma_split(s):
    if s is None:
        return s
    s = s.replace(' ', ',')
    s = [x.strip() for x in s.split(',')]
    s = [x for x in s if x]
    return s

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

def edit_params(original, modifications):
    new_params = original.to_dict()
    new_params.update(modifications)
    if not new_params:
        return ''
    new_params = ['%s=%s' % (k, v) for (k, v) in new_params.items() if v]
    new_params = '&'.join(new_params)
    new_params = '?' + new_params
    return new_params

def generate_session_token():
    token = str(uuid.uuid4())
    #print('MAKE SESSION', token)
    return token

def make_json_response(j, *args, **kwargs):
    dumped = json.dumps(j)
    response = flask.Response(dumped, *args, **kwargs)
    response.headers['Content-Type'] = 'application/json;charset=utf-8'
    return response

def P_album(albumid):
    try:
        return P.get_album(albumid)
    except phototagger.NoSuchAlbum:
        flask.abort(404, 'That tag doesnt exist')

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

def read_filebytes(filepath, range_min, range_max):
    range_span = range_max - range_min

    #print('read span', range_min, range_max, range_span)
    f = open(filepath, 'rb')
    f.seek(range_min)
    sent_amount = 0
    with f:
        while sent_amount < range_span:
            #print(sent_amount)
            chunk = f.read(FILE_READ_CHUNK)
            if len(chunk) == 0:
                break

            yield chunk
            sent_amount += len(chunk)

def seconds_to_hms(seconds):
    seconds = math.ceil(seconds)
    (minutes, seconds) = divmod(seconds, 60)
    (hours, minutes) = divmod(minutes, 60)
    parts = []
    if hours: parts.append(hours)
    if minutes: parts.append(minutes)
    parts.append(seconds)
    hms = ':'.join('%02d' % part for part in parts)
    return hms

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
        outgoing_data = read_filebytes(filepath, range_min=range_min, range_max=range_max)

    response = flask.Response(
        outgoing_data,
        status=status,
        headers=outgoing_headers,
    )
    return response

def truthystring(s):
    if isinstance(s, (bool, int)) or s is None:
        return s
    s = s.lower()
    if s in {'1', 'true', 't', 'yes', 'y', 'on'}:
        return True
    if s in {'null', 'none'}:
        return None
    return False

####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################

def jsonify_album(album, minimal=False):
    j = {
        'id': album.id,
        'description': album.description,
        'title': album.title,
    }
    if minimal is False:
        j['photos'] = [jsonify_photo(photo) for photo in album.photos()]
        j['parent'] = album.parent()
        j['sub_albums'] = [child.id for child in album.children()]

    return j

def jsonify_photo(photo):
    tags = photo.tags()
    tags.sort(key=lambda x: x.name)
    j = {
        'id': photo.id,
        'extension': photo.extension,
        'width': photo.width,
        'height': photo.height,
        'ratio': photo.ratio,
        'area': photo.area,
        'bytes': photo.bytes,
        'duration': seconds_to_hms(photo.duration) if photo.duration is not None else None,
        'duration_int': photo.duration,
        'bytestring': photo.bytestring(),
        'has_thumbnail': bool(photo.thumbnail),
        'created': photo.created,
        'filename': photo.basename,
        'mimetype': photo.mimetype(),
        'albums': [jsonify_album(album, minimal=True) for album in photo.albums()],
        'tags': [jsonify_tag(tag) for tag in tags],
    }
    return j

def jsonify_tag(tag):
    j = {
        'id': tag.id,
        'name': tag.name,
        'qualified_name': tag.qualified_name(),
    }
    return j

####################################################################################################
####################################################################################################
####################################################################################################
####################################################################################################

@site.route('/')
@give_session_token
def root():
    motd = random.choice(MOTD_STRINGS)
    return flask.render_template('root.html', motd=motd)

@site.route('/favicon.ico')
@site.route('/favicon.png')
def favicon():
    filename = os.path.join('static', 'favicon.png')
    return flask.send_file(filename)

def get_album_core(albumid):
    album = P_album(albumid)
    album = jsonify_album(album)
    return album

@site.route('/album/<albumid>')
@give_session_token
def get_album_html(albumid):
    album = get_album_core(albumid)
    response = flask.render_template(
        'album.html',
        album=album,
        child_albums=album['sub_albums'],
        photos=album['photos'],
    )
    return response

@site.route('/album/<albumid>')
@give_session_token
def get_album_json(albumid):
    album = get_album_core(albumid)
    return make_json_response(album)

@site.route('/albums')
@give_session_token
def get_albums():
    albums = P.get_albums()
    albums = [a for a in albums if a.parent() is None]
    return flask.render_template('albums.html', albums=albums)

@site.route('/file/<photoid>')
def get_file(photoid):
    requested_photoid = photoid
    photoid = photoid.split('.')[0]
    photo = P.get_photo(photoid)

    do_download = request.args.get('download', False)
    do_download = truthystring(do_download)

    use_original_filename = request.args.get('original_filename', False)
    use_original_filename = truthystring(use_original_filename)

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
    photo = jsonify_photo(photo)
    return photo

@site.route('/photo/<photoid>', methods=['GET'])
@give_session_token
def get_photo_html(photoid):
    photo = get_photo_core(photoid)
    photo['tags'].sort(key=lambda x: x['qualified_name'])
    return flask.render_template('photo.html', photo=photo)

@site.route('/photo/<photoid>.json', methods=['GET'])
@give_session_token
def get_photo_json(photoid):
    photo = get_photo_core(photoid)
    photo = make_json_response(photo)
    return photo

def get_search_core():
    print(request.args)

    # EXTENSION
    extension_string = request.args.get('extension', None)
    extension_not_string = request.args.get('extension_not', None)
    mimetype_string = request.args.get('mimetype', None)

    extension_list = _helper_comma_split(extension_string)
    extension_not_list = _helper_comma_split(extension_not_string)
    mimetype_list = _helper_comma_split(mimetype_string)

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
        has_tags = truthystring(has_tags)

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
    print(search_kwargs)
    with warnings.catch_warnings(record=True) as catcher:
        photos = list(P.search(**search_kwargs))
        photos = [jsonify_photo(photo) for photo in photos]
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
    if len(photos) == limit:
        next_params = edit_params(request.args, {'offset': offset + limit})
        next_page_url = '/search' + next_params
    else:
        next_page_url = None
    if offset > 0:
        prev_params = edit_params(request.args, {'offset': max(0, offset - limit)})
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
@give_session_token
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
@give_session_token
def get_search_json():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = search_results['qualname_map']
    include_qualname_map = request.args.get('include_map', False)
    include_qualname_map = truthystring(include_qualname_map)
    if not include_qualname_map:
        search_results.pop('qualname_map')
    return make_json_response(j)

@site.route('/static/<filename>')
def get_static(filename):
    filename = filename.replace('\\', os.sep)
    filename = filename.replace('/', os.sep)
    filename = os.path.join('static', filename)
    return flask.send_file(filename)

@site.route('/tags')
@site.route('/tags/<specific_tag>')
@give_session_token
def get_tags(specific_tag=None):
    try:
        tags = P.export_tags(phototagger.tag_export_easybake, specific_tag=specific_tag)
    except phototagger.NoSuchTag:
        flask.abort(404, 'That tag doesnt exist')

    tags = tags.split('\n')
    tags = [t for t in tags if t != '']
    tags = [(t, t.split('.')[-1].split('+')[0]) for t in tags]
    return flask.render_template('tags.html', tags=tags)

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
@give_session_token
def post_edit_album(albumid):
    '''
    Edit the album's title and description.
    Apply a tag to every photo in the album.
    '''

@site.route('/photo/<photoid>', methods=['POST'])
@give_session_token
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
@give_session_token
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
        response = {'error': ERROR_INVALID_ACTION}

    if status == 200:
        tag = request.form[action].strip()
        if tag == '':
            response = {'error': ERROR_NO_TAG_GIVEN}
            status = 400

    if status == 200:
        # expect the worst
        status = 400
        try:
            response = method(tag)
        except phototagger.TagTooShort:
            response = {'error': ERROR_TAG_TOO_SHORT, 'tagname': tag}
        except phototagger.CantSynonymSelf:
            response = {'error': ERROR_SYNONYM_ITSELF, 'tagname': tag}
        except phototagger.NoSuchTag as e:
            response = {'error': ERROR_NO_SUCH_TAG, 'tagname': tag}
        except ValueError as e:
            response = {'error': e.args[0], 'tagname': tag}
        else:
            status = 200

    response = json.dumps(response)
    response = flask.Response(response, status=status)
    return response


if __name__ == '__main__':
    site.run(threaded=True)
