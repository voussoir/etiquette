import flask; from flask import request

import etiquette

from .. import common
from .. import decorators
from .. import jsonify

site = common.site
session_manager = common.session_manager


# Individual bookmarks #############################################################################

@site.route('/bookmark/<bookmark_id>.json')
@session_manager.give_token
def get_bookmark_json(bookmark_id):
    bookmark = common.P_bookmark(bookmark_id, response_type='json')
    response = etiquette.jsonify.bookmark(bookmark)
    return jsonify.make_json_response(response)

@site.route('/bookmark/<bookmark_id>/edit', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
def post_bookmark_edit(bookmark_id):
    bookmark = common.P_bookmark(bookmark_id, response_type='json')
    # Emptystring is okay for titles, but not for URL.
    title = request.form.get('title', None)
    url = request.form.get('url', None) or None
    bookmark.edit(title=title, url=url, commit=True)

    response = etiquette.jsonify.bookmark(bookmark)
    response = jsonify.make_json_response(response)
    return response

# Bookmark listings ################################################################################

@site.route('/bookmarks')
@session_manager.give_token
def get_bookmarks_html():
    bookmarks = list(common.P.get_bookmarks())
    return common.render_template(request, 'bookmarks.html', bookmarks=bookmarks)

@site.route('/bookmarks.json')
@session_manager.give_token
def get_bookmarks_json():
    bookmarks = [etiquette.jsonify.bookmark(b) for b in common.P.get_bookmarks()]
    return jsonify.make_json_response(bookmarks)

# Bookmark create and delete #######################################################################

@site.route('/bookmarks/create_bookmark', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['url'], forbid_whitespace=True)
def post_bookmark_create():
    url = request.form['url']
    title = request.form.get('title', None)
    user = session_manager.get(request).user
    bookmark = common.P.new_bookmark(url=url, title=title, author=user, commit=True)
    response = etiquette.jsonify.bookmark(bookmark)
    response = jsonify.make_json_response(response)
    return response

@site.route('/bookmark/<bookmark_id>/delete', methods=['POST'])
@decorators.catch_etiquette_exception
def post_bookmark_delete(bookmark_id):
    bookmark = common.P_bookmark(bookmark_id, response_type='json')
    bookmark.delete(commit=True)
    return jsonify.make_json_response({})
