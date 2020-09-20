import flask; from flask import request

import etiquette

from .. import caching
from .. import common
from .. import decorators
from .. import jsonify

site = common.site
session_manager = common.session_manager

# Individual tags ##################################################################################

@site.route('/tags/<specific_tag>')
@site.route('/tags/<specific_tag>.json')
def get_tags_specific_redirect(specific_tag):
    return flask.redirect(request.url.replace('/tags/', '/tag/'))

@site.route('/tagid/<tag_id>')
@site.route('/tagid/<tag_id>.json')
def get_tag_id_redirect(tag_id):
    if request.url.endswith('.json'):
        tag = common.P_tag_id(tag_id, response_type='json')
    else:
        tag = common.P_tag_id(tag_id, response_type='html')
    url_from = '/tagid/' + tag_id
    url_to = '/tag/' + tag.name
    url = request.url.replace(url_from, url_to)
    return flask.redirect(url)

@site.route('/tag/<tagname>/edit', methods=['POST'])
def post_tag_edit(tagname):
    tag = common.P_tag(tagname, response_type='json')
    name = request.form.get('name', '').strip()
    if name:
        tag.rename(name)

    description = request.form.get('description', None)
    tag.edit(description=description, commit=True)

    response = etiquette.jsonify.tag(tag)
    response = jsonify.make_json_response(response)
    return response

@site.route('/tag/<tagname>/add_child', methods=['POST'])
@decorators.required_fields(['child_name'], forbid_whitespace=True)
def post_tag_add_child(tagname):
    parent = common.P_tag(tagname, response_type='json')
    child = common.P_tag(request.form['child_name'], response_type='json')
    parent.add_child(child, commit=True)
    response = {'action': 'add_child', 'tagname': f'{parent.name}.{child.name}'}
    return jsonify.make_json_response(response)

@site.route('/tag/<tagname>/remove_child', methods=['POST'])
@decorators.required_fields(['child_name'], forbid_whitespace=True)
def post_tag_remove_child(tagname):
    parent = common.P_tag(tagname, response_type='json')
    child = common.P_tag(request.form['child_name'], response_type='json')
    parent.remove_child(child, commit=True)
    response = {'action': 'remove_child', 'tagname': f'{parent.name}.{child.name}'}
    return jsonify.make_json_response(response)

# Tag listings #####################################################################################

@site.route('/all_tags.json')
@caching.cached_endpoint(max_age=0)
def get_all_tag_names():
    all_tags = list(common.P.get_all_tag_names())
    all_synonyms = common.P.get_all_synonyms()
    response = {'tags': all_tags, 'synonyms': all_synonyms}
    return jsonify.make_json_response(response)

@site.route('/tag/<specific_tag_name>')
@site.route('/tags')
def get_tags_html(specific_tag_name=None):
    if specific_tag_name is None:
        specific_tag = None
    else:
        specific_tag = common.P_tag(specific_tag_name, response_type='html')
        if specific_tag.name != specific_tag_name:
            new_url = request.url.replace('/tag/' + specific_tag_name, '/tag/' + specific_tag.name)
            return flask.redirect(new_url)

    include_synonyms = request.args.get('include_synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)

    if specific_tag is None:
        tags = common.P.get_root_tags()
        tag_count = common.P.get_tag_count()
    else:
        tags = [specific_tag]
        tag_count = sum(1 for child in specific_tag.walk_children())

    tags = list(common.P.get_cached_tag_export(
        'easybake',
        tags=tags,
        include_synonyms=False,
        with_objects=True,
    ))

    response = common.render_template(
        request,
        'tags.html',
        include_synonyms=include_synonyms,
        specific_tag=specific_tag,
        tags=tags,
        tag_count=tag_count,
    )
    return response

@site.route('/tag/<specific_tag_name>.json')
@site.route('/tags.json')
def get_tags_json(specific_tag_name=None):
    if specific_tag_name is None:
        specific_tag = None
    else:
        specific_tag = common.P_tag(specific_tag_name, response_type='json')
        if specific_tag.name != specific_tag_name:
            new_url = request.url.replace('/tag/' + specific_tag_name, '/tag/' + specific_tag.name)
            return flask.redirect(new_url)

    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)

    if specific_tag is None:
        tags = list(common.P.get_tags())
    else:
        tags = list(specific_tag.walk_children())

    tags = [etiquette.jsonify.tag(tag, include_synonyms=include_synonyms) for tag in tags]
    return jsonify.make_json_response(tags)

# Tag create and delete ############################################################################

@site.route('/tags/create_tag', methods=['POST'])
@decorators.required_fields(['name'], forbid_whitespace=True)
def post_tag_create():
    name = request.form['name']
    description = request.form.get('description', None)

    tag = common.P.new_tag(name, description, author=session_manager.get(request).user, commit=True)
    response = etiquette.jsonify.tag(tag)
    return jsonify.make_json_response(response)

@site.route('/tags/easybake', methods=['POST'])
@decorators.required_fields(['easybake_string'], forbid_whitespace=True)
def post_tag_easybake():
    easybake_string = request.form['easybake_string']

    notes = common.P.easybake(easybake_string, author=session_manager.get(request).user, commit=True)
    notes = [{'action': action, 'tagname': tagname} for (action, tagname) in notes]
    return jsonify.make_json_response(notes)

@site.route('/tag/<tagname>/delete', methods=['POST'])
def post_tag_delete(tagname):
    tag = common.P_tag(tagname, response_type='json')
    tag.delete(commit=True)
    response = {'action': 'delete_tag', 'tagname': tag.name}
    return jsonify.make_json_response(response)

@site.route('/tag/<tagname>/remove_synonym', methods=['POST'])
@decorators.required_fields(['syn_name'], forbid_whitespace=True)
def post_tag_remove_synonym(tagname):
    syn_name = request.form['syn_name']

    master_tag = common.P_tag(tagname, response_type='json')
    master_tag.remove_synonym(syn_name, commit=True)

    response = {'action': 'delete_synonym', 'synonym': syn_name}
    return jsonify.make_json_response(response)
