'''
This file provides functions that convert the Etiquette objects into
dictionaries suitable for JSON serializing.
'''

def album(a, minimal=False):
    j = {
        'type': 'album',
        'id': a.id,
        'description': a.description,
        'title': a.title,
        'author': user_or_none(a.get_author()),
    }
    if not minimal:
        j['photos'] = [photo(p) for p in a.get_photos()]
        j['parents'] = [album(p, minimal=True) for p in a.get_parents()]
        j['sub_albums'] = [album(c, minimal=True) for c in a.get_children()]

    return j

def bookmark(b):
    j = {
        'type': 'bookmark',
        'id': b.id,
        'author': user_or_none(b.get_author()),
        'url': b.url,
        'title': b.title,
    }
    return j

def exception(e):
    j = {
        'type': 'error',
        'error_type': e.error_type,
        'error_message': e.error_message,
    }
    return j

def photo(p, include_albums=True, include_tags=True):
    j = {
        'type': 'photo',
        'id': p.id,
        'author': user_or_none(p.get_author()),
        'extension': p.extension,
        'width': p.width,
        'height': p.height,
        'ratio': p.ratio,
        'area': p.area,
        'bytes': p.bytes,
        'duration_str': p.duration_string,
        'duration': p.duration,
        'bytes_str': p.bytestring,
        'has_thumbnail': bool(p.thumbnail),
        'created': p.created,
        'filename': p.basename,
        'mimetype': p.mimetype,
        'searchhidden': bool(p.searchhidden),
    }
    if include_albums:
        j['albums'] = [album(a, minimal=True) for a in p.get_containing_albums()]

    if include_tags:
        j['tags'] = [tag(t, minimal=True) for t in p.get_tags()]

    return j

def tag(t, include_synonyms=False, minimal=False):
    j = {
        'type': 'tag',
        'id': t.id,
        'name': t.name,
    }
    if not minimal:
        j['author'] = user_or_none(t.get_author())
        j['description'] = t.description
        j['children'] = [tag(c, minimal=True) for c in t.get_children()]

    if include_synonyms:
        j['synonyms'] = list(t.get_synonyms())
    return j

def user(u):
    j = {
        'type': 'user',
        'id': u.id,
        'username': u.username,
        'created': u.created,
        'display_name': u.display_name,
    }
    return j

def user_or_none(u):
    if u is None:
        return None
    return user(u)
