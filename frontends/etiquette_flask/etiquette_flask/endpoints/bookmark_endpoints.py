import flask; from flask import request

import etiquette

from .. import decorators
from .. import jsonify
from .. import common

site = common.site
session_manager = common.session_manager


# Individual bookmarks #############################################################################

@site.route('/bookmark/<bookmarkid>.json')
@session_manager.give_token
def get_bookmark_json(bookmarkid):
    bookmark = common.P_bookmark(bookmarkid)
    response = etiquette.jsonify.bookmark(bookmark)
    return jsonify.make_json_response(response)

# Bookmark metadata operations #####################################################################

@site.route('/bookmark/<bookmarkid>/edit', methods=['POST'])
@session_manager.give_token
@decorators.catch_etiquette_exception
def post_bookmark_edit(bookmarkid):
    bookmark = common.P_bookmark(bookmarkid)
    # Emptystring is okay for titles, but not for URL.
    title = request.form.get('title', None)
    url = request.form.get('url', None) or None
    bookmark.edit(title=title, url=url)

    response = etiquette.jsonify.bookmark(bookmark)
    response = jsonify.make_json_response(response)
    return response

# Bookmark listings ################################################################################

@site.route('/bookmarks')
@session_manager.give_token
def get_bookmarks_html():
    session = session_manager.get(request)
    bookmarks = list(common.P.get_bookmarks())
    return flask.render_template('bookmarks.html', bookmarks=bookmarks, session=session)

@site.route('/bookmarks.json')
@session_manager.give_token
def get_bookmarks_json():
    bookmarks = [etiquette.jsonify.bookmark(b) for b in common.P.get_bookmarks()]
    return jsonify.make_json_response(bookmarks)

# Bookmark create and delete #######################################################################

@site.route('/bookmarks/create_bookmark', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['url'], forbid_whitespace=True)
def post_bookmarks_create():
    url = request.form['url']
    title = request.form.get('title', None)
    user = session_manager.get(request).user
    bookmark = common.P.new_bookmark(url=url, title=title, author=user)
    response = etiquette.jsonify.bookmark(bookmark)
    response = jsonify.make_json_response(response)
    return response
