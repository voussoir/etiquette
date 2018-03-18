import flask; from flask import request

import etiquette

from .. import decorators
from .. import jsonify
from .. import common

site = common.site
session_manager = common.session_manager


# Individual tags ##################################################################################

@site.route('/tags/<specific_tag>')
@site.route('/tags/<specific_tag>.json')
def get_tags_specific_redirect(specific_tag):
    return flask.redirect(request.url.replace('/tags/', '/tag/'))

# Tag metadata operations ##########################################################################

@site.route('/tag/<specific_tag>/edit', methods=['POST'])
@decorators.catch_etiquette_exception
def post_tag_edit(specific_tag):
    tag = common.P_tag(specific_tag)
    name = request.form.get('name', '').strip()
    if name:
        tag.rename(name, commit=False)

    description = request.form.get('description', None)
    tag.edit(description=description)

    response = etiquette.jsonify.tag(tag)
    response = jsonify.make_json_response(response)
    return response

# Tag listings #####################################################################################

def get_tags_core(specific_tag=None):
    if specific_tag is None:
        tags = common.P.get_tags()
    else:
        tags = specific_tag.walk_children()
    tags = list(tags)
    tags.sort(key=lambda x: x.qualified_name())
    return tags

@site.route('/tag/<specific_tag_name>')
@site.route('/tags')
@session_manager.give_token
def get_tags_html(specific_tag_name=None):
    if specific_tag_name is None:
        specific_tag = None
    else:
        specific_tag = common.P_tag(specific_tag_name, response_type='html')
        if specific_tag.name != specific_tag_name:
            new_url = request.url.replace('/tag/' + specific_tag_name, '/tag/' + specific_tag.name)
            response = flask.redirect(new_url)
            return response
    tags = get_tags_core(specific_tag)
    session = session_manager.get(request)
    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)
    response = flask.render_template(
        'tags.html',
        include_synonyms=include_synonyms,
        session=session,
        specific_tag=specific_tag,
        tags=tags,
    )
    return response

@site.route('/tag/<specific_tag_name>.json')
@site.route('/tags.json')
@session_manager.give_token
def get_tags_json(specific_tag_name=None):
    if specific_tag_name is None:
        specific_tag = None
    else:
        specific_tag = common.P_tag(specific_tag_name, response_type='json')
        if specific_tag.name != specific_tag_name:
            new_url = request.url.replace('/tag/' + specific_tag_name, '/tag/' + specific_tag.name)
            return flask.redirect(new_url)
    tags = get_tags_core(specific_tag=specific_tag)
    include_synonyms = request.args.get('synonyms')
    include_synonyms = include_synonyms is None or etiquette.helpers.truthystring(include_synonyms)
    tags = [etiquette.jsonify.tag(tag, include_synonyms=include_synonyms) for tag in tags]
    return jsonify.make_json_response(tags)

# Tag create and delete ############################################################################

@site.route('/tags/create_tag', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_create():
    '''
    Create a tag.
    '''
    easybake_string = request.form['tagname']
    user = session_manager.get(request).user
    notes = common.P.easybake(easybake_string, author=user)
    notes = [{'action': action, 'tagname': tagname} for (action, tagname) in notes]
    return jsonify.make_json_response(notes)

@site.route('/tags/delete_synonym', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete_synonym():
    '''
    Delete a synonym.
    '''
    synonym = request.form['tagname']
    synonym = synonym.split('+')[-1].split('.')[-1]

    try:
        master_tag = common.P_tag(synonym, response_type='json')
    except etiquette.exceptions.NoSuchTag as exc:
        raise etiquette.exceptions.NoSuchSynonym(*exc.given_args, **exc.given_kwargs)
    else:
        master_tag.remove_synonym(synonym)

    response = {'action':'delete_synonym', 'synonym': synonym}
    return jsonify.make_json_response(response)

@site.route('/tags/delete_tag', methods=['POST'])
@decorators.catch_etiquette_exception
@decorators.required_fields(['tagname'], forbid_whitespace=True)
def post_tag_delete():
    '''
    Delete a tag.
    '''
    tagname = request.form['tagname']
    tagname = tagname.split('.')[-1].split('+')[0]
    tag = common.P.get_tag(name=tagname)

    tag.delete()
    response = {'action': 'delete_tag', 'tagname': tag.name}
    return jsonify.make_json_response(response)
