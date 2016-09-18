import distutils.util
import flask
from flask import request
import json
import mimetypes
import os
import random
import re
import requests
import warnings

site = flask.Flask(__name__)
site.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=180,
    TEMPLATES_AUTO_RELOAD=True,
)

print(os.getcwd())
import phototagger
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

def edit_params(original, modifications):
    new_params = original.to_dict()
    new_params.update(modifications)
    if not new_params:
        return ''
    keep_params = {}
    new_params = ['%s=%s' % (k, v) for (k, v) in new_params.items() if v]
    new_params = '&'.join(new_params)
    new_params = '?' + new_params
    return new_params

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

def truthystring(s):
    if isinstance(s, (bool, int)) or s is None:
        return s
    s = s.lower()
    if s in {'1', 'true', 't', 'yes', 'y', 'on'}:
        return True
    if s in {'null', 'none'}:
        return None
    return False

def read_filebytes(filepath, range_min, range_max):
    range_span = range_max - range_min

    #print('read span', range_min, range_max, range_span)
    f = open(filepath, 'rb')
    f.seek(range_min)
    sent_amount = 0
    with f:
        while sent_amount < range_span:
            chunk = f.read(FILE_READ_CHUNK)
            if len(chunk) == 0:
                break

            yield chunk
            sent_amount += len(chunk)

def send_file(filepath):
    '''
    Range-enabled file sending.
    '''
    outgoing_headers = {}
    mimetype = mimetypes.guess_type(filepath)[0]
    if mimetype is not None:
        if 'text/' in mimetype:
            mimetype += '; charset=utf-8'
        outgoing_headers['Content-Type'] = mimetype

    if 'range' not in request.headers:
        response = flask.make_response(flask.send_file(filepath))
        for (k, v) in outgoing_headers.items():
            response.headers[k] = v
        return response

    try:
        file_size = os.path.getsize(filepath)
    except FileNotFoundError:
        flask.abort(404)

    desired_range = request.headers['range'].lower()
    desired_range = desired_range.split('bytes=')[-1]

    inthelper = lambda x: int(x) if x.isdigit() else None
    if '-' in desired_range:
        (desired_min, desired_max) = desired_range.split('-')
        range_min = inthelper(desired_min)
        range_max = inthelper(desired_max)
    else:
        range_min = inthelper(desired_range)

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
    outgoing_headers['Accept-Ranges'] = 'bytes'
    outgoing_headers['Content-Length'] = (range_max - range_min) + 1

    outgoing_data = read_filebytes(filepath, range_min=range_min, range_max=range_max)
    response = flask.Response(
        outgoing_data,
        status=206,
        headers=outgoing_headers,
    )
    return response


@site.route('/')
def root():
    motd = random.choice(MOTD_STRINGS)
    return flask.render_template('root.html', motd=motd)

@site.route('/album/<albumid>')
def get_album(albumid):
    album = P_album(albumid)
    response = flask.render_template(
        'album.html',
        album=album,
        child_albums=album.children(),
        photos=album.photos()
    )
    return response

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

        # Sorry, but otherwise the attachment filename gets terminated
        #download_as = download_as.replace(';', '-')
        download_as = download_as.replace('"', '\\"')
        response = flask.make_response(send_file(photo.real_filepath))
        response.headers['Content-Disposition'] = 'attachment; filename="%s"' % download_as
        return response
    else:
        return send_file(photo.real_filepath)

@site.route('/albums')
def get_albums():
    albums = P.get_albums()
    albums = [a for a in albums if a.parent() is None]
    return flask.render_template('albums.html', albums=albums)

@site.route('/photo/<photoid>', methods=['GET'])
def get_photo(photoid):
    photo = P_photo(photoid)
    tags = photo.tags()
    tags.sort(key=lambda x: x.qualified_name())
    return flask.render_template('photo.html', photo=photo, tags=tags)

@site.route('/tags')
@site.route('/tags/<specific_tag>')
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

@site.route('/photo/<photoid>', methods=['POST'])
def edit_photo(photoid):
    print(request.form)
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
        return flask.Response('{"error": "That tag doesnt exist", "tagname":"%s"}'%tag, status=404)

    method(tag)
    response['action'] = action
    response['tagid'] = tag.id
    response['tagname'] = tag.name
    return json.dumps(response)

@site.route('/tags', methods=['POST'])
def edit_tags():
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
        response = {'error': ERROR_INVALID_ACTION}

    if status == 200:
        status = 400
        tag = request.form[action].strip()
        if tag == '':
            response = {'error': ERROR_NO_TAG_GIVEN}
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

def create_tag(easybake_string):
    notes = P.easybake(easybake_string)
    notes = [{'action': action, 'tagname': tagname} for (action, tagname) in notes]
    return notes

def delete_tag(tag):
    tag = tag.split('.')[-1].split('+')[0]
    tag = P.get_tag(tag)

    tag.delete()
    return {'action': 'delete_tag', 'tagname': tag.name, 'tagid': tag.id}

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


@site.route('/search')
def search():
    print(request.args)

    def comma_split_helper(s):
        s = s.replace(' ', ',')
        s = [x.strip() for x in s.split(',')]
        s = [x for x in s if x]
        return s
    # EXTENSION
    extension_string = request.args.get('extension', '')
    extension_not_string = request.args.get('extension_not', '')
    mimetype_string = request.args.get('mimetype', '')

    extension_list = comma_split_helper(extension_string)
    extension_not_list = comma_split_helper(extension_not_string)
    mimetype_list = comma_split_helper(mimetype_string)

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
    length = request.args.get('length', None)
    created = request.args.get('created', None)

    # These are in a dictionary so I can pass them to the page template.
    search_kwargs = {
        'area': area,
        'width': width,
        'height': height,
        'ratio': ratio,
        'bytes': bytes,
        'length': length,

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
        warns = [str(warning.message) for warning in catcher]
    print(warns)
    total_tags = set()
    for photo in photos:
        total_tags.update(photo.tags())
    for tag in total_tags:
        tag._cached_qualname = qualname_map[tag.name]
    total_tags = sorted(total_tags, key=lambda x: x._cached_qualname)

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
    response = flask.render_template(
        'search.html',
        photos=photos,
        search_kwargs=search_kwargs,
        total_tags=total_tags,
        prev_page_url=prev_page_url,
        next_page_url=next_page_url,
        qualname_map=json.dumps(qualname_map),
        warns=warns,
    )
    return response

@site.route('/static/<filename>')
def get_resource(filename):
    print(filename)
    return flask.send_file('.\\static\\%s' % filename)


if __name__ == '__main__':
    site.run(threaded=True)