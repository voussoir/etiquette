import etiquette
import jinja2.filters

import voussoirkit.bytestring

def bytestring(x):
    try:
        return voussoirkit.bytestring.bytestring(x)
    except Exception as e:
        return '??? b'

def file_link(photo, short=False):
    if short:
        return f'/file/{photo.id}{photo.dot_extension}'
    basename = jinja2.filters.do_urlencode(photo.basename)
    return f'/file/{photo.id}/{basename}'

def sort_by_qualname(tags):
    tags = sorted(tags, key=lambda x: x.qualified_name())
    return tags
