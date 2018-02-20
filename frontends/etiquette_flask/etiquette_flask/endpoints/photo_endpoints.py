import flask; from flask import request
import json
import traceback
import urllib.parse

import etiquette

from .. import decorators
from .. import jsonify
from .. import common

site = common.site
session_manager = common.session_manager


# Individual photos ################################################################################

@site.route('/photo/<photo_id>')
@session_manager.give_token
def get_photo_html(photo_id):
    photo = common.P_photo(photo_id, response_type='html')
    session = session_manager.get(request)
    return flask.render_template('photo.html', photo=photo, session=session)

@site.route('/photo/<photo_id>.json')
@session_manager.give_token
def get_photo_json(photo_id):
    photo = common.P_photo(photo_id, response_type='json')
    photo = etiquette.jsonify.photo(photo)
    photo = jsonify.make_json_response(photo)
    return photo

@site.route('/file/<photo_id>')
def get_file(photo_id):
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
    photo = common.P_photo(photo_id)
    if photo.thumbnail:
        path = photo.thumbnail
    else:
        flask.abort(404, 'That file doesnt have a thumbnail')
    return common.send_file(path)

# Photo tag operations #############################################################################

@decorators.catch_etiquette_exception
def post_photo_add_remove_tag_core(photo_id, tagname, add_or_remove):
    photo = common.P_photo(photo_id, response_type='json')
    tag = common.P_tag(tagname, response_type='json')

    if add_or_remove == 'add':
        photo.add_tag(tag)
    elif add_or_remove == 'remove':
        photo.remove_tag(tag)

    response = {'tagname': tag.name}
    return jsonify.make_json_response(response)

@site.route('/photo/<photo_id>/add_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_add_tag(photo_id):
    '''
    Add a tag to this photo.
    '''
    return post_photo_add_remove_tag_core(photo_id, request.form['tagname'], 'add')

@site.route('/photo/<photo_id>/remove_tag', methods=['POST'])
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_photo_remove_tag(photo_id):
    '''
    Remove a tag from this photo.
    '''
    return post_photo_add_remove_tag_core(photo_id, request.form['tagname'], 'remove')

# Photo metadata operations ########################################################################

@site.route('/photo/<photo_id>/refresh_metadata', methods=['POST'])
@decorators.catch_etiquette_exception
def post_photo_refresh_metadata(photo_id):
    '''
    Refresh the file metadata.
    '''
    common.P.caches['photo'].remove(photo_id)
    photo = common.P_photo(photo_id, response_type='json')
    photo.reload_metadata()
    if photo.thumbnail is None:
        try:
            photo.generate_thumbnail()
        except Exception:
            traceback.print_exc()

    return jsonify.make_json_response({})

# Clipboard ########################################################################################

@site.route('/clipboard')
@session_manager.give_token
def get_clipboard_page():
    return flask.render_template('clipboard.html')

@site.route('/batch/photos/photo_card', methods=['POST'])
def post_batch_photos_photo_cards():
    photo_ids = request.form.get('photo_ids', None)
    if photo_ids is None:
        return jsonify.make_json_response({})

    photo_ids = etiquette.helpers.comma_space_split(photo_ids)
    photos = [common.P_photo(photo_id, response_type='html') for photo_id in photo_ids]

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
    search_generator = common.P.search(**search_kwargs)
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
        for tag in photo.get_tags():
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

@site.route('/search')
@session_manager.give_token
def get_search_html():
    search_results = get_search_core()
    search_kwargs = search_results['search_kwargs']
    qualname_map = etiquette.tag_export.qualified_names(common.P.get_tags())
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
