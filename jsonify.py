import flask
import helpers
import json

def make_json_response(j, *args, **kwargs):
    dumped = json.dumps(j)
    response = flask.Response(dumped, *args, **kwargs)
    response.headers['Content-Type'] = 'application/json;charset=utf-8'
    return response

def album(a, minimal=False):
    j = {
        'id': a.id,
        'description': a.description,
        'title': a.title,
    }
    if not minimal:
        j['photos'] = [photo(p) for p in a.photos()]
        j['parent'] = a.parent()
        j['sub_albums'] = [child.id for child in a.children()]

    return j

def photo(p, include_albums=True, include_tags=True):
    tags = p.tags()
    tags.sort(key=lambda x: x.name)
    j = {
        'id': p.id,
        'extension': p.extension,
        'width': p.width,
        'height': p.height,
        'ratio': p.ratio,
        'area': p.area,
        'bytes': p.bytes,
        'duration_str': helpers.seconds_to_hms(p.duration) if p.duration is not None else None,
        'duration': p.duration,
        'bytes_str': p.bytestring(),
        'has_thumbnail': bool(p.thumbnail),
        'created': p.created,
        'filename': p.basename,
        'mimetype': p.mimetype(),
    }
    if include_albums:
        j['albums'] = [album(a, minimal=True) for a in p.albums()]

    if include_tags:
        j['tags'] = [tag(t) for t in tags]

    return j

def tag(t):
    j = {
        'id': t.id,
        'name': t.name,
        'qualified_name': t.qualified_name(),
    }
    return j
