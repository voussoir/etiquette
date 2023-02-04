import flask; from flask import request

from voussoirkit import flasktools
from voussoirkit import stringtools

import etiquette

from .. import common

site = common.site
session_manager = common.session_manager

# Individual tags ##################################################################################

@site.route('/tags/<specific_tag>')
@site.route('/tags/<specific_tag>.json')
def get_tags_specific_redirect(specific_tag):
    common.permission_manager.basic()
    return flask.redirect(request.url.replace('/tags/', '/tag/'))

@site.route('/tagid/<tag_id>')
@site.route('/tagid/<tag_id>.json')
def get_tag_id_redirect(tag_id):
    common.permission_manager.basic()
    if request.path.endswith('.json'):
        tag = common.P_tag_id(tag_id, response_type='json')
    else:
        tag = common.P_tag_id(tag_id, response_type='html')
    url_from = '/tagid/' + tag_id
    url_to = '/tag/' + tag.name
    url = request.url.replace(url_from, url_to)
    return flask.redirect(url)

@site.route('/tag/<specific_tag_name>.json')
def get_tag_json(specific_tag_name):
    common.permission_manager.basic()
    specific_tag = common.P_tag(specific_tag_name, response_type='json')
    if specific_tag.name != specific_tag_name:
        new_url = f'/tag/{specific_tag.name}.json' + request.query_string.decode('utf-8')
        return flask.redirect(new_url)

    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or stringtools.truthystring(include_synonyms)

    response = specific_tag.jsonify(include_synonyms=include_synonyms)
    return flasktools.json_response(response)

@site.route('/tag/<tagname>/edit', methods=['POST'])
def post_tag_edit(tagname):
    common.permission_manager.basic()
    with common.P.transaction:
        tag = common.P_tag(tagname, response_type='json')
        name = request.form.get('name', '').strip()
        if name:
            tag.rename(name)

        description = request.form.get('description', None)
        tag.edit(description=description)

    response = flasktools.json_response(tag.jsonify())
    return response

@site.route('/tag/<tagname>/add_child', methods=['POST'])
@flasktools.required_fields(['child_name'], forbid_whitespace=True)
def post_tag_add_child(tagname):
    common.permission_manager.basic()
    with common.P.transaction:
        parent = common.P_tag(tagname, response_type='json')
        child = common.P_tag(request.form['child_name'], response_type='json')
        parent.add_child(child)
    response = {'action': 'add_child', 'tagname': f'{parent.name}.{child.name}'}
    return flasktools.json_response(response)

@site.route('/tag/<tagname>/add_synonym', methods=['POST'])
@flasktools.required_fields(['syn_name'], forbid_whitespace=True)
def post_tag_add_synonym(tagname):
    common.permission_manager.basic()
    syn_name = request.form['syn_name']

    with common.P.transaction:
        master_tag = common.P_tag(tagname, response_type='json')
        syn_name = master_tag.add_synonym(syn_name)

    response = {'action': 'add_synonym', 'synonym': syn_name}
    return flasktools.json_response(response)

@site.route('/tag/<tagname>/remove_child', methods=['POST'])
@flasktools.required_fields(['child_name'], forbid_whitespace=True)
def post_tag_remove_child(tagname):
    common.permission_manager.basic()
    with common.P.transaction:
        parent = common.P_tag(tagname, response_type='json')
        child = common.P_tag(request.form['child_name'], response_type='json')
        parent.remove_child(child)
    response = {'action': 'remove_child', 'tagname': f'{parent.name}.{child.name}'}
    return flasktools.json_response(response)

@site.route('/tag/<tagname>/remove_synonym', methods=['POST'])
@flasktools.required_fields(['syn_name'], forbid_whitespace=True)
def post_tag_remove_synonym(tagname):
    common.permission_manager.basic()
    syn_name = request.form['syn_name']

    with common.P.transaction:
        master_tag = common.P_tag(tagname, response_type='json')
        syn_name = master_tag.remove_synonym(syn_name)

    response = {'action': 'delete_synonym', 'synonym': syn_name}
    return flasktools.json_response(response)

# Tag listings #####################################################################################

@site.route('/all_tags.json')
@common.permission_manager.basic_decorator
@flasktools.cached_endpoint(max_age=15)
def get_all_tag_names():
    all_tags = list(common.P.get_all_tag_names())
    all_synonyms = common.P.get_all_synonyms()
    response = {'tags': all_tags, 'synonyms': all_synonyms}
    return flasktools.json_response(response)

@site.route('/tag/<specific_tag_name>')
@site.route('/tags')
def get_tags_html(specific_tag_name=None):
    common.permission_manager.basic()
    if specific_tag_name is None:
        specific_tag = None
    else:
        specific_tag = common.P_tag(specific_tag_name, response_type='html')
        if specific_tag.name != specific_tag_name:
            new_url = '/tag/' + specific_tag.name + request.query_string.decode('utf-8')
            return flask.redirect(new_url)

    include_synonyms = request.args.get('include_synonyms')
    include_synonyms = include_synonyms is None or stringtools.truthystring(include_synonyms)

    if specific_tag is None:
        tags = common.P.get_root_tags()
        tag_count = common.P.get_tag_count()
    else:
        tags = specific_tag.get_children()
        # Set because tags may have multiple lineages
        tag_count = len(set(specific_tag.walk_children()))

    tags = common.P.get_cached_tag_export(
        'easybake',
        tags=tags,
        include_synonyms=False,
        with_objects=True,
    )

    response = common.render_template(
        request,
        'tags.html',
        include_synonyms=include_synonyms,
        specific_tag=specific_tag,
        tags=tags,
        tag_count=tag_count,
    )
    return response

@site.route('/tags.json')
def get_tags_json():
    common.permission_manager.basic()
    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or stringtools.truthystring(include_synonyms)

    tags = list(common.P.get_tags())
    response = [tag.jsonify(include_synonyms=include_synonyms) for tag in tags]

    return flasktools.json_response(response)

# Tag create and delete ############################################################################

@site.route('/tags/create_tag', methods=['POST'])
@flasktools.required_fields(['name'], forbid_whitespace=True)
def post_tag_create():
    common.permission_manager.basic()
    name = request.form['name']
    description = request.form.get('description', None)

    with common.P.transaction:
        tag = common.P.new_tag(name, description, author=session_manager.get(request).user)
    response = tag.jsonify()
    return flasktools.json_response(response)

@site.route('/tags/easybake', methods=['POST'])
@flasktools.required_fields(['easybake_string'], forbid_whitespace=True)
def post_tag_easybake():
    common.permission_manager.basic()
    easybake_string = request.form['easybake_string']

    with common.P.transaction:
        notes = common.P.easybake(easybake_string, author=session_manager.get(request).user)
    notes = [{'action': action, 'tagname': tagname} for (action, tagname) in notes]
    return flasktools.json_response(notes)

@site.route('/tag/<tagname>/delete', methods=['POST'])
def post_tag_delete(tagname):
    common.permission_manager.basic()
    with common.P.transaction:
        tag = common.P_tag(tagname, response_type='json')
        tag.delete()
    response = {'action': 'delete_tag', 'tagname': tag.name}
    return flasktools.json_response(response)
