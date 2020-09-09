import flask; from flask import request
import traceback
import urllib.parse

from voussoirkit import cacheclass

import etiquette

from .. import common
from .. import decorators
from .. import helpers
from .. import jsonify

site = common.site
session_manager = common.session_manager
photo_download_zip_tokens = cacheclass.Cache(maxlen=100)


# Individual photos ################################################################################

@site.route('/photo/<photo_id>')
@session_manager.give_token
def get_photo_html(photo_id):
    photo = common.P_photo(photo_id, response_type='html')
    return common.render_template(request, 'photo.html', photo=photo)

@site.route('/photo/<photo_id>.json')
@session_manager.give_token
def get_photo_json(photo_id):
    photo = common.P_photo(photo_id, response_type='json')
    photo = etiquette.jsonify.photo(photo)
    photo = jsonify.make_json_response(photo)
    return photo

@site.route('/file/<photo_id>')
@site.route('/file/<photo_id>/<basename>')
def get_file(photo_id, basename=None):
    photo_id = photo_id.split('.')[0]
    photo = common.P.get_photo(photo_id)

    do_download = request.args.get('download', False)
    do_download = etiquette.helpers.truthystring(do_download)

    use_original_filename = request.args.get('original_filename', False)
    use_original_filename = etiquette.helpers.truthystring(use_original_filename)

    if do_download:
        if use_original_filename:
            download_as = photo.basename
        else:
            download_as = photo.id + photo.dot_extension

        download_as = etiquette.helpers.remove_path_badchars(download_as)
        download_as = urllib.parse.quote(download_as)
        response = flask.make_response(common.send_file(photo.real_path.absolute_path))
        response.headers['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' % download_as
        return response
    else:
        return common.send_file(photo.real_path.absolute_path, override_mimetype=photo.mimetype)

@site.route('/thumbnail/<photo_id>')
def get_thumbnail(photo_id):
    photo_id = photo_id.split('.')[0]
    photo = common.P_photo(photo_id, response_type='html')
    if photo.thumbnail:
        path = photo.thumbnail
    else:
        flask.abort(404, 'That file doesnt have a thumbnail')
    return common.send_file(path)

# Photo create and delete ##########################################################################

@site.route('/photo/<photo_id>/delete', methods=['POST'])
@decorators.catch_etiquette_exception
@session_manager.give_token
def post_photo_delete(photo_id):
    print(photo_id)
    photo = common.P_photo(photo_id, response_type='json')
    delete_file = request.form.get('delete_file', False)
    delete_file = etiquette.helpers.truthystring(delete_file)
    photo.delete(delete_file=delete_file, commit=True)
    return jsonify.make_json_response({})

# Photo tag operations #############################################################################

@decorators.catch_etiquette_exception
def post_photo_add_remove_tag_core(photo_ids, tagname, add_or_remove):
    if isinstance(photo_ids, str):
        photo_ids = etiquette.helpers.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))
    tag = common.P_tag(tagname, response_type='json')

    for photo in photos:
        if add_or_remove == 'add':
            photo.add_tag(tag)
        elif add_or_remove == 'remove':
            photo.remove_tag(tag)
    common.P.commit('photo add remove tag core')

    response = {'action': add_or_remove, 'tagname': tag.name}
    return jsonify.make_json_response(response)

@site.route('/photo/<photo_id>/add_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_add_tag(photo_id):
    '''
    Add a tag to this photo.
    '''
    response = post_photo_add_remove_tag_core(
        photo_ids=photo_id,
        tagname=request.form['tagname'],
        add_or_remove='add',
    )
    return response

@site.route('/photo/<photo_id>/remove_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_remove_tag(photo_id):
    '''
    Remove a tag from this photo.
    '''
    response = post_photo_add_remove_tag_core(
        photo_ids=photo_id,
        tagname=request.form['tagname'],
        add_or_remove='remove',
    )
    return response

@site.route('/batch/photos/add_tag', methods=['POST'])
@decorators.required_fields(['photo_ids', 'tagname'], forbid_whitespace=True)
def post_batch_photos_add_tag():
    response = post_photo_add_remove_tag_core(
        photo_ids=request.form['photo_ids'],
        tagname=request.form['tagname'],
        add_or_remove='add',
    )
    return response

@site.route('/batch/photos/remove_tag', methods=['POST'])
@decorators.required_fields(['photo_ids', 'tagname'], forbid_whitespace=True)
def post_batch_photos_remove_tag():
    response = post_photo_add_remove_tag_core(
        photo_ids=request.form['photo_ids'],
        tagname=request.form['tagname'],
        add_or_remove='remove',
    )
    return response

# Photo metadata operations ########################################################################

@decorators.catch_etiquette_exception
@site.route('/photo/<photo_id>/generate_thumbnail', methods=['POST'])
def post_photo_generate_thumbnail(photo_id):
    special = request.form.to_dict()
    special.pop('commit', None)

    photo = common.P_photo(photo_id, response_type='json')
    photo.generate_thumbnail(commit=True, **special)

    response = jsonify.make_json_response({})
    return response

@decorators.catch_etiquette_exception
def post_photo_refresh_metadata_core(photo_ids):
    if isinstance(photo_ids, str):
        photo_ids = etiquette.helpers.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))

    for photo in photos:
        common.P.caches['photo'].remove(photo.id)
        photo = common.P_photo(photo.id, response_type='json')
        photo.reload_metadata()
        if photo.thumbnail is None:
            try:
                photo.generate_thumbnail()
            except Exception:
                traceback.print_exc()

    common.P.commit('photo refresh metadata core')

    return jsonify.make_json_response({})

@site.route('/photo/<photo_id>/refresh_metadata', methods=['POST'])
def post_photo_refresh_metadata(photo_id):
    response = post_photo_refresh_metadata_core(photo_ids=photo_id)
    return response

@site.route('/batch/photos/refresh_metadata', methods=['POST'])
@decorators.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_refresh_metadata():
    response = post_photo_refresh_metadata_core(photo_ids=request.form['photo_ids'])
    return response

@decorators.catch_etiquette_exception
def post_photo_searchhidden_core(photo_ids, searchhidden):
    if isinstance(photo_ids, str):
        photo_ids = etiquette.helpers.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))

    for photo in photos:
        photo.set_searchhidden(searchhidden)

    common.P.commit('photo set searchhidden core')

    return jsonify.make_json_response({})

@site.route('/batch/photos/set_searchhidden', methods=['POST'])
@decorators.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_set_searchhidden():
    response = post_photo_searchhidden_core(photo_ids=request.form['photo_ids'], searchhidden=True)
    return response

@site.route('/batch/photos/unset_searchhidden', methods=['POST'])
@decorators.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_unset_searchhidden():
    response = post_photo_searchhidden_core(photo_ids=request.form['photo_ids'], searchhidden=False)
    return response

# Clipboard ########################################################################################

@site.route('/clipboard')
@session_manager.give_token
def get_clipboard_page():
    return common.render_template(request, 'clipboard.html')

@site.route('/batch/photos/photo_card', methods=['POST'])
@decorators.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_photo_cards():
    photo_ids = request.form['photo_ids']

    photo_ids = etiquette.helpers.comma_space_split(photo_ids)
    photos = list(common.P_photos(photo_ids, response_type='json'))

    # Photo filenames are prevented from having colons, so using it as a split
    # delimiter should be safe.
    template = '''
    {% import "photo_card.html" as photo_card %}
    {% for photo in photos %}
        {{photo.id}}:
        {{photo_card.create_photo_card(photo)}}
        :SPLITME:
    {% endfor %}
    '''
    html = flask.render_template_string(template, photos=photos)
    divs = [div.strip() for div in html.split(':SPLITME:')]
    divs = [div for div in divs if div]
    divs = [div.split(':', 1) for div in divs]
    divs = {photo_id.strip(): photo_card.strip() for (photo_id, photo_card) in divs}
    response = jsonify.make_json_response(divs)
    return response

# Zipping ##########################################################################################

@site.route('/batch/photos/download_zip/<zip_token>', methods=['GET'])
def get_batch_photos_download_zip(zip_token):
    '''
    After the user has generated their zip token, they can retrieve
    that zip file.
    '''
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
@decorators.required_fields(['photo_ids'], forbid_whitespace=True)
def post_batch_photos_download_zip():
    '''
    Initiating file downloads via POST requests is a bit clunky and unreliable,
    so the way this works is we generate a token representing the photoset
    that they want, and then they can retrieve the zip itself via GET.
    '''
    photo_ids = request.form['photo_ids']
    photo_ids = etiquette.helpers.comma_space_split(photo_ids)

    photos = list(common.P_photos(photo_ids, response_type='json'))
    if not photos:
        flask.abort(400)

    photo_ids = [p.id for p in photos]

    zip_token = 'etiquette_' + etiquette.helpers.hash_photoset(photos)
    photo_download_zip_tokens[zip_token] = photo_ids

    response = {'zip_token': zip_token}
    response = jsonify.make_json_response(response)
    return response

# Search ###########################################################################################

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
    is_searchhidden = request.args.get('is_searchhidden', False)

    limit = request.args.get('limit')
    # This is being pre-processed because the site enforces a maximum value
    # which the PhotoDB api does not.
    limit = etiquette.searchhelpers.normalize_limit(limit, warning_bag=warning_bag)

    if limit is None:
        limit = 50
    else:
        limit = min(limit, 200)

    offset = request.args.get('offset')

    author = request.args.get('author')

    orderby = request.args.get('orderby')
    area = request.args.get('area')
    width = request.args.get('width')
    height = request.args.get('height')
    ratio = request.args.get('ratio')
    bytes = request.args.get('bytes')
    has_thumbnail = request.args.get('has_thumbnail')
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

        'author': author,
        'created': created,
        'extension': extension,
        'extension_not': extension_not,
        'filename': filename_terms,
        'has_tags': has_tags,
        'has_thumbnail': has_thumbnail,
        'is_searchhidden': is_searchhidden,
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
    search_generator = common.P.search(**search_kwargs)
    # Because of the giveback, first element is cleaned up kwargs
    search_kwargs = next(search_generator)

    # The search has converted many arguments into sets or other types.
    # Convert them back into something that will display nicely on the search form.
    join_helper = lambda x: ', '.join(x) if x else None
    search_kwargs['extension'] = join_helper(search_kwargs['extension'])
    search_kwargs['extension_not'] = join_helper(search_kwargs['extension_not'])
    search_kwargs['mimetype'] = join_helper(search_kwargs['mimetype'])

    author_helper = lambda users: ', '.join(user.username for user in users) if users else None
    search_kwargs['author'] = author_helper(search_kwargs['author'])

    tagname_helper = lambda tags: [tag.name for tag in tags] if tags else None
    search_kwargs['tag_musts'] = tagname_helper(search_kwargs['tag_musts'])
    search_kwargs['tag_mays'] = tagname_helper(search_kwargs['tag_mays'])
    search_kwargs['tag_forbids'] = tagname_helper(search_kwargs['tag_forbids'])

    warnings = set()
    search_results = []
    for item in search_generator:
        if isinstance(item, etiquette.objects.WarningBag):
            warnings.update(item.warnings)
        else:
            search_results.append(item)

    # TAGS ON THIS PAGE
    total_tags = set()
    for result in search_results:
        if isinstance(result, etiquette.objects.Photo):
            total_tags.update(result.get_tags())
    total_tags = sorted(total_tags, key=lambda t: t.name)

    # PREV-NEXT PAGE URLS
    offset = search_kwargs['offset'] or 0
    original_params = request.args.to_dict()
    original_params['limit'] = limit

    if limit and len(search_results) >= limit:
        next_params = original_params.copy()
        next_params['offset'] = offset + limit
        next_params = helpers.dict_to_params(next_params)
        next_page_url = '/search' + next_params
    else:
        next_page_url = None

    if limit and offset > 0:
        prev_params = original_params.copy()
        prev_offset = max(0, offset - limit)
        if prev_offset > 0:
            prev_params['offset'] = prev_offset
        else:
            prev_params.pop('offset', None)
        prev_params = helpers.dict_to_params(prev_params)
        prev_page_url = '/search' + prev_params
    else:
        prev_page_url = None

    view = request.args.get('view', 'grid')
    search_kwargs['view'] = view

    final_results = {
        'next_page_url': next_page_url,
        'prev_page_url': prev_page_url,
        'results': search_results,
        'total_tags': total_tags,
        'warnings': list(warnings),
        'search_kwargs': search_kwargs,
    }
    return final_results

@site.route('/search')
@session_manager.give_token
def get_search_html():
    search_results = get_search_core()
    response = common.render_template(
        request,
        'search.html',
        next_page_url=search_results['next_page_url'],
        prev_page_url=search_results['prev_page_url'],
        results=search_results['results'],
        search_kwargs=search_results['search_kwargs'],
        total_tags=search_results['total_tags'],
        warnings=search_results['warnings'],
    )
    return response

@site.route('/search.json')
@session_manager.give_token
def get_search_json():
    search_results = get_search_core()
    search_results['results'] = [
        etiquette.jsonify.photo(result, include_albums=False)
        if isinstance(result, etiquette.objects.Photo) else
        etiquette.jsonify.album(result, minimal=True)
        for result in search_results['results']
    ]
    search_results['total_tags'] = [
        etiquette.jsonify.tag(tag, minimal=True) for tag in search_results['total_tags']
    ]
    return jsonify.make_json_response(search_results)
