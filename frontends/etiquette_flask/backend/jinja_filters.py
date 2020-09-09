import datetime
import jinja2.filters

import voussoirkit.bytestring


def bytestring(x):
    try:
        return voussoirkit.bytestring.bytestring(x)
    except Exception as e:
        return '??? b'

def comma_join(l):
    if not l:
        return ''
    return ', '.join(l)

def file_link(photo, short=False):
    if short:
        return f'/file/{photo.id}{photo.dot_extension}'
    basename = jinja2.filters.do_urlencode(photo.basename)
    return f'/file/{photo.id}/{basename}'

def make_attributes(*booleans, **keyvalues):
    keyvalues = {key: value for (key, value) in keyvalues.items() if value is not None}
    attributes = [f'{key}="{jinja2.filters.escape(value)}"' for (key, value) in keyvalues.items()]
    attributes.extend(booleans)
    attributes = ' '.join(attributes)
    return attributes

def sort_tags(tags):
    tags = sorted(tags, key=lambda x: x.name)
    return tags

def timestamp_to_8601(timestamp):
    return datetime.datetime.utcfromtimestamp(timestamp).isoformat(' ') + ' UTC'

def timestamp_to_string(timestamp, format):
    date = datetime.datetime.utcfromtimestamp(timestamp)
    return date.strftime(format)

def timestamp_to_naturaldate(timestamp):
    return timestamp_to_string(timestamp, '%B %d, %Y')
