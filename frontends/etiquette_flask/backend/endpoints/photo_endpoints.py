import flask; from flask import request
import os
import subprocess
import traceback
import urllib.parse

from voussoirkit import cacheclass
from voussoirkit import flasktools
from voussoirkit import pathclass
from voussoirkit import stringtools
from voussoirkit import vlogging

log = vlogging.get_logger(__name__)

import etiquette

from .. import common
from .. import helpers

site = common.site
session_manager = common.session_manager
photo_download_zip_tokens = cacheclass.Cache(maxlen=100)

# Individual photos ################################################################################

@site.route('/photo/<photo_id>')
def get_photo_html(photo_id):
    common.permission_manager.basic()
    photo = common.P_photo(photo_id, response_type='html')
    return common.render_template(request, 'photo.html', photo=photo)

@site.route('/photo/<photo_id>.json')
def get_photo_json(photo_id):
    common.permission_manager.basic()
    photo = common.P_photo(photo_id, response_type='json')
    photo = photo.jsonify()
    photo = flasktools.json_response(photo)
    return photo

@site.route('/photo/<photo_id>/download')
@site.route('/photo/<photo_id>/download/<basename>')
def get_file(photo_id, basename=None):
    common.permission_manager.basic()
    photo_id = photo_id.split('.')[0]
    photo = common.P.get_photo(photo_id)

    do_download = request.args.get('download', False)
    do_download = stringtools.truthystring(do_download)

    use_original_filename = request.args.get('original_filename', False)
    use_original_filename = stringtools.truthystring(use_original_filename)

    if do_download:
        if use_original_filename:
            download_as = photo.basename
        else:
            download_as = f'{photo.id}{photo.dot_extension}'

        download_as = etiquette.helpers.remove_path_badchars(download_as)
        download_as = urllib.parse.quote(download_as)
        response = flask.make_response(common.send_file(photo.real_path.absolute_path))
        response.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % download_as
        return response
    else:
        return common.send_file(photo.real_path.absolute_path, override_mimetype=photo.mimetype)

@site.route('/photo/<photo_id>/thumbnail')
@site.route('/photo/<photo_id>/thumbnail/<basename>')
@common.permission_manager.basic_decorator
@flasktools.cached_endpoint(max_age=common.BROWSER_CACHE_DURATION, etag_function=lambda: common.P.last_commit_id)
def get_thumbnail(photo_id, basename=None):
    photo_id = photo_id.split('.')[0]
    photo = common.P_photo(photo_id, response_type='html')
    blob = photo.get_thumbnail()
    if blob is None:
        return flask.abort(404)

    outgoing_headers = {
        'Content-Type': 'image/jpeg',
    }
    response = flask.Response(
        blob,
        status=200,
        headers=outgoing_headers,
    )
    return response
    # if photo.thumbnail:
    #     path = photo.thumbnail
    # else:
    #     flask.abort(404, 'That file doesnt have a thumbnail')
    # return common.send_file(path)

# Photo create and delete ##########################################################################

@site.route('/photo/<photo_id>/delete', methods=['POST'])
def post_photo_delete(photo_id):
    common.permission_manager.basic()
    delete_file = request.form.get('delete_file', False)
    delete_file = stringtools.truthystring(delete_file)
    with common.P.transaction:
        photo = common.P_photo(photo_id, response_type='json')
        photo.delete(delete_file=delete_file)
    return flasktools.json_response({})

# Photo tag operations #############################################################################

def post_photo_add_remove_tag_core(photo_ids, tagname, add_or_remove):
    if isinstance(photo_ids, str):
        photo_ids = stringtools.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))
    tag = common.P_tag(tagname, response_type='json')

    with common.P.transaction:
        for photo in photos:
            if add_or_remove == 'add':
                photo.add_tag(tag)
            elif add_or_remove == 'remove':
                photo.remove_tag(tag)

    response = {'action': add_or_remove, 'tagname': tag.name}
    return flasktools.json_response(response)

@site.route('/photo/<photo_id>/add_tag', methods=['POST'])
@flasktools.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_add_tag(photo_id):
    '''
    Add a tag to this photo.
    '''
    common.permission_manager.basic()
    response = post_photo_add_remove_tag_core(
        photo_ids=photo_id,
        tagname=request.form['tagname'],
        add_or_remove='add',
    )
    return response

@site.route('/photo/<photo_id>/copy_tags', methods=['POST'])
@flasktools.required_fields(['other_photo'], forbid_whitespace=True)
def post_photo_copy_tags(photo_id):
    '''
    Copy the tags from another photo.
    '''
    common.permission_manager.basic()
    with common.P.transaction:
        photo = common.P_photo(photo_id, response_type='json')
        other = common.P_photo(request.form['other_photo'], response_type='json')
        photo.copy_tags(other)
    return flasktools.json_response([tag.jsonify(minimal=True) for tag in photo.get_tags()])

@site.route('/photo/<photo_id>/remove_tag', methods=['POST'])
@flasktools.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_remove_tag(photo_id):
    '''
    Remove a tag from this photo.
    '''
    common.permission_manager.basic()
    response = post_photo_add_remove_tag_core(
        photo_ids=photo_id,
        tagname=request.form['tagname'],
        add_or_remove='remove',
    )
    return response

@site.route('/batch/photos/add_tag', methods=['POST'])
@flasktools.required_fields(['photo_ids', 'tagname'], forbid_whitespace=True)
def post_batch_photos_add_tag():
    common.permission_manager.basic()
    response = post_photo_add_remove_tag_core(
        photo_ids=request.form['photo_ids'],
        tagname=request.form['tagname'],
        add_or_remove='add',
    )
    return response

@site.route('/batch/photos/remove_tag', methods=['POST'])
@flasktools.required_fields(['photo_ids', 'tagname'], forbid_whitespace=True)
def post_batch_photos_remove_tag():
    common.permission_manager.basic()
    response = post_photo_add_remove_tag_core(
        photo_ids=request.form['photo_ids'],
        tagname=request.form['tagname'],
        add_or_remove='remove',
    )
    return response

# Photo metadata operations ########################################################################

def post_photo_generate_thumbnail_core(photo_ids, special={}):
    if isinstance(photo_ids, str):
        photo_ids = stringtools.comma_space_split(photo_ids)

    with common.P.transaction:
        photos = list(common.P_photos(photo_ids, response_type='json'))

        for photo in photos:
            photo._uncache()
            photo = common.P_photo(photo.id, response_type='json')
            try:
                photo.generate_thumbnail()
            except Exception:
                log.warning(traceback.format_exc())

    return flasktools.json_response({})

@site.route('/photo/<photo_id>/generate_thumbnail', methods=['POST'])
def post_photo_generate_thumbnail(photo_id):
    common.permission_manager.basic()
    special = request.form.to_dict()
    response = post_photo_generate_thumbnail_core(photo_ids=photo_id, special=special)
    return response

@site.route('/batch/photos/generate_thumbnail', methods=['POST'])
def post_batch_photos_generate_thumbnail():
    common.permission_manager.basic()
    special = request.form.to_dict()
    response = post_photo_generate_thumbnail_core(photo_ids=request.form['photo_ids'], special=special)
    return response

def post_photo_refresh_metadata_core(photo_ids):
    if isinstance(photo_ids, str):
        photo_ids = stringtools.comma_space_split(photo_ids)

    with common.P.transaction:
        photos = list(common.P_photos(photo_ids, response_type='json'))

        for photo in photos:
            photo._uncache()
            photo = common.P_photo(photo.id, response_type='json')
            try:
                photo.reload_metadata()
            except pathclass.NotFile:
                flask.abort(404)

            if not photo.has_thumbnail() or photo.simple_mimetype == 'image':
                try:
                    photo.generate_thumbnail()
                except Exception:
                    log.warning(traceback.format_exc())

    return flasktools.json_response({})

@site.route('/photo/<photo_id>/refresh_metadata', methods=['POST'])
def post_photo_refresh_metadata(photo_id):
    common.permission_manager.basic()
    response = post_photo_refresh_metadata_core(photo_ids=photo_id)
    return response

@site.route('/batch/photos/refresh_metadata', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_refresh_metadata():
    common.permission_manager.basic()
    response = post_photo_refresh_metadata_core(photo_ids=request.form['photo_ids'])
    return response

@site.route('/photo/<photo_id>/set_searchhidden', methods=['POST'])
def post_photo_set_searchhidden(photo_id):
    common.permission_manager.basic()
    with common.P.transaction:
        photo = common.P_photo(photo_id, response_type='json')
        photo.set_searchhidden(True)
    return flasktools.json_response({})

@site.route('/photo/<photo_id>/unset_searchhidden', methods=['POST'])
def post_photo_unset_searchhidden(photo_id):
    common.permission_manager.basic()
    with common.P.transaction:
        photo = common.P_photo(photo_id, response_type='json')
        photo.set_searchhidden(False)
    return flasktools.json_response({})

def post_batch_photos_searchhidden_core(photo_ids, searchhidden):
    if isinstance(photo_ids, str):
        photo_ids = stringtools.comma_space_split(photo_ids)

    with common.P.transaction:
        photos = list(common.P_photos(photo_ids, response_type='json'))

        for photo in photos:
            photo.set_searchhidden(searchhidden)

    return flasktools.json_response({})

@site.route('/photo/<photo_id>/show_in_folder', methods=['POST'])
def post_photo_show_in_folder(photo_id):
    common.permission_manager.basic()
    if not request.is_localhost:
        flask.abort(403)

    photo = common.P_photo(photo_id, response_type='json')
    if os.name == 'nt':
        command = f'explorer.exe /select,"{photo.real_path.absolute_path}"'
        subprocess.Popen(command, shell=True)
        return flasktools.json_response({})
    else:
        command = ['xdg-open', photo.real_path.parent.absolute_path]
        subprocess.Popen(command, shell=True)
        return flasktools.json_response({})

    flask.abort(501)

@site.route('/batch/photos/set_searchhidden', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_set_searchhidden():
    common.permission_manager.basic()
    photo_ids = request.form['photo_ids']
    response = post_batch_photos_searchhidden_core(photo_ids=photo_ids, searchhidden=True)
    return response

@site.route('/batch/photos/unset_searchhidden', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_unset_searchhidden():
    common.permission_manager.basic()
    photo_ids = request.form['photo_ids']
    response = post_batch_photos_searchhidden_core(photo_ids=photo_ids, searchhidden=False)
    return response

# Clipboard ########################################################################################

@site.route('/clipboard')
def get_clipboard_page():
    common.permission_manager.basic()
    return common.render_template(request, 'clipboard.html')

@site.route('/batch/photos', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos():
    '''
    Return a list of photo.jsonify() for each requested photo id.
    '''
    common.permission_manager.basic()
    photo_ids = request.form['photo_ids']

    photo_ids = stringtools.comma_space_split(photo_ids)
    photos = list(common.P_photos(photo_ids, response_type='json'))

    photos = [photo.jsonify() for photo in photos]
    response = flasktools.json_response(photos)
    return response

@site.route('/batch/photos/photo_card', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_photo_cards():
    common.permission_manager.basic()
    photo_ids = request.form['photo_ids']

    photo_ids = stringtools.comma_space_split(photo_ids)
    photos = list(common.P_photos(photo_ids, response_type='json'))

    # Photo filenames are prevented from having colons, so using it as a split
    # delimiter should be safe.
    template = '''
    {% import "cards.html" as cards %}
    {% for photo in photos %}
        {{photo.id}}:
        {{cards.create_photo_card(photo)}}
        :SPLITME:
    {% endfor %}
    '''
    html = flask.render_template_string(template, photos=photos)
    divs = [div.strip() for div in html.split(':SPLITME:')]
    divs = [div for div in divs if div]
    divs = [div.split(':', 1) for div in divs]
    divs = {photo_id.strip(): photo_card.strip() for (photo_id, photo_card) in divs}
    response = flasktools.json_response(divs)
    return response

# Zipping ##########################################################################################

@site.route('/batch/photos/download_zip/<zip_token>', methods=['GET'])
def get_batch_photos_download_zip(zip_token):
    '''
    After the user has generated their zip token, they can retrieve
    that zip file.
    '''
    common.permission_manager.basic()
    zip_token = zip_token.split('.')[0]
    try:
        photo_ids = photo_download_zip_tokens[zip_token]
    except KeyError:
        flask.abort(404)

    # Let's re-validate those IDs just in case anything has changed.
    photos = list(common.P_photos(photo_ids, response_type='json'))
    if not photos:
        flask.abort(400)

    streamed_zip = etiquette.helpers.zip_photos(photos)
    download_as = zip_token + '.zip'
    download_as = urllib.parse.quote(download_as)

    outgoing_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{download_as}',
    }
    return flask.Response(streamed_zip, headers=outgoing_headers)

@site.route('/batch/photos/download_zip', methods=['POST'])
@flasktools.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_download_zip():
    '''
    Initiating file downloads via POST requests is a bit clunky and unreliable,
    so the way this works is we generate a token representing the photoset
    that they want, and then they can retrieve the zip itself via GET.
    '''
    common.permission_manager.basic()
    photo_ids = request.form['photo_ids']
    photo_ids = stringtools.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))
    if not photos:
        flask.abort(400)

    photo_ids = [p.id for p in photos]

    zip_token = 'etiquette_' + etiquette.helpers.hash_photoset(photos)
    photo_download_zip_tokens[zip_token] = photo_ids

    response = {'zip_token': zip_token}
    response = flasktools.json_response(response)
    return response

# Search ###########################################################################################

def get_search_core():
    search = common.P.search(
        area=request.args.get('area'),
        width=request.args.get('width'),
        height=request.args.get('height'),
        aspectratio=request.args.get('aspectratio'),
        bytes=request.args.get('bytes'),
        duration=request.args.get('duration'),
        bitrate=request.args.get('bitrate'),

        filename=request.args.get('filename'),
        extension_not=request.args.get('extension_not'),
        extension=request.args.get('extension'),
        mimetype=request.args.get('mimetype'),
        sha256=request.args.get('sha256'),

        author=request.args.get('author'),
        created=request.args.get('created'),
        has_albums=request.args.get('has_albums'),
        has_thumbnail=request.args.get('has_thumbnail'),
        is_searchhidden=request.args.get('is_searchhidden', False),

        has_tags=request.args.get('has_tags'),
        tag_musts=request.args.get('tag_musts'),
        tag_mays=request.args.get('tag_mays'),
        tag_forbids=request.args.get('tag_forbids'),
        tag_expression=request.args.get('tag_expression'),

        limit=request.args.get('limit'),
        offset=request.args.get('offset'),
        orderby=request.args.get('orderby'),

        yield_albums=request.args.get('yield_albums', False),
        yield_photos=request.args.get('yield_photos', True),
    )

    # The site enforces a maximum value which the PhotoDB does not.
    search.kwargs.limit = etiquette.searchhelpers.normalize_limit(search.kwargs.limit)
    if search.kwargs.limit is None:
        search.kwargs.limit = 50
    else:
        search.kwargs.limit = min(search.kwargs.limit, 1000)

    search.results = list(search.results)
    warnings = [
        w.error_message if hasattr(w, 'error_message') else str(w)
        for w in search.warning_bag.warnings
    ]

    # Web UI users aren't allowed to use within_directory anyway, so don't
    # show it to them.
    del search.kwargs.within_directory
    return search

@site.route('/search_embed')
def get_search_embed():
    common.permission_manager.basic()
    search = get_search_core()
    response = common.render_template(
        request,
        'search_embed.html',
        results=search.results,
        search_kwargs=search.kwargs,
    )
    return response

@site.route('/search')
def get_search_html():
    common.permission_manager.basic()

    search = get_search_core()
    search.kwargs.view = request.args.get('view', 'grid')

    # TAGS ON THIS PAGE
    total_tags = set()
    for result in search.results:
        if isinstance(result, etiquette.objects.Photo):
            total_tags.update(result.get_tags())
    total_tags = sorted(total_tags, key=lambda t: t.name)

    # PREV-NEXT PAGE URLS
    offset = search.kwargs.offset or 0
    original_params = request.args.to_dict()
    original_params['limit'] = search.kwargs.limit

    if search.more_after_limit:
        next_params = original_params.copy()
        next_params['offset'] = offset + search.kwargs.limit
        next_params = helpers.dict_to_params(next_params)
        next_page_url = '/search' + next_params
    else:
        next_page_url = None

    if search.kwargs.limit and offset > 0:
        prev_params = original_params.copy()
        prev_offset = max(0, offset - search.kwargs.limit)
        if prev_offset > 0:
            prev_params['offset'] = prev_offset
        else:
            prev_params.pop('offset', None)
        prev_params = helpers.dict_to_params(prev_params)
        prev_page_url = '/search' + prev_params
    else:
        prev_page_url = None

    response = common.render_template(
        request,
        'search.html',
        next_page_url=next_page_url,
        prev_page_url=prev_page_url,
        results=search.results,
        search_kwargs=search.kwargs,
        total_tags=total_tags,
        warnings=search.warning_bag.jsonify(),
    )
    return response

@site.route('/search.atom')
def get_search_atom():
    common.permission_manager.basic()
    search = get_search_core()
    soup = etiquette.helpers.make_atom_feed(
        search.results,
        feed_id='/search' + request.query_string.decode('utf-8'),
        feed_title='etiquette search',
        feed_link=request.url.replace('/search.atom', '/search'),
    )
    response = flasktools.atom_response(soup)
    return response

@site.route('/search.json')
def get_search_json():
    common.permission_manager.basic()
    search = get_search_core()
    response = search.jsonify()
    return flasktools.json_response(response)

# Swipe ############################################################################################

@site.route('/swipe')
def get_swipe():
    common.permission_manager.basic()
    response = common.render_template(request, 'swipe.html')
    return response
