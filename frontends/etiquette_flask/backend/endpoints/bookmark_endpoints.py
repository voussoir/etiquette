import flask; from flask import request

from voussoirkit import flasktools

import etiquette

from .. import common

site = common.site
session_manager = common.session_manager

# Individual bookmarks #############################################################################

@site.route('/bookmark/<bookmark_id>.json')
def get_bookmark_json(bookmark_id):
    common.permission_manager.basic()
    bookmark = common.P_bookmark(bookmark_id, response_type='json')
    response = bookmark.jsonify()
    return flasktools.json_response(response)

@site.route('/bookmark/<bookmark_id>/edit', methods=['POST'])
def post_bookmark_edit(bookmark_id):
    common.permission_manager.basic()
    with common.P.transaction:
        bookmark = common.P_bookmark(bookmark_id, response_type='json')
        # Emptystring is okay for titles, but not for URL.
        title = request.form.get('title', None)
        url = request.form.get('url', None) or None
        bookmark.edit(title=title, url=url)

    response = bookmark.jsonify()
    response = flasktools.json_response(response)
    return response

# Bookmark listings ################################################################################

@site.route('/bookmarks.atom')
def get_bookmarks_atom():
    common.permission_manager.basic()
    bookmarks = common.P.get_bookmarks()
    response = etiquette.helpers.make_atom_feed(
        bookmarks,
        feed_id='/bookmarks' + request.query_string.decode('utf-8'),
        feed_title='bookmarks',
        feed_link=request.url.replace('/bookmarks.atom', '/bookmarks'),
    )
    return flasktools.atom_response(response)

@site.route('/bookmarks')
def get_bookmarks_html():
    common.permission_manager.basic()
    bookmarks = list(common.P.get_bookmarks())
    return common.render_template(request, 'bookmarks.html', bookmarks=bookmarks)

@site.route('/bookmarks.json')
def get_bookmarks_json():
    common.permission_manager.basic()
    bookmarks = [b.jsonify() for b in common.P.get_bookmarks()]
    return flasktools.json_response(bookmarks)

# Bookmark create and delete #######################################################################

@site.route('/bookmarks/create_bookmark', methods=['POST'])
@flasktools.required_fields(['url'], forbid_whitespace=True)
def post_bookmark_create():
    common.permission_manager.basic()
    url = request.form['url']
    title = request.form.get('title', None)
    user = session_manager.get(request).user
    with common.P.transaction:
        bookmark = common.P.new_bookmark(url=url, title=title, author=user)
    response = bookmark.jsonify()
    response = flasktools.json_response(response)
    return response

@site.route('/bookmark/<bookmark_id>/delete', methods=['POST'])
def post_bookmark_delete(bookmark_id):
    common.permission_manager.basic()
    with common.P.transaction:
        bookmark = common.P_bookmark(bookmark_id, response_type='json')
        bookmark.delete()
    return flasktools.json_response({})
