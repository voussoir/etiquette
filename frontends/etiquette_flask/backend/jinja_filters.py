import itertools
import jinja2.filters

import voussoirkit.bytestring

####################################################################################################

filter_functions = []
global_functions = []

def filter_function(function):
    filter_functions.append(function)
    return function

def global_function(function):
    global_functions.append(function)
    return function

def register_all(site):
    for function in filter_functions:
        site.jinja_env.filters[function.__name__] = function

    for function in global_functions:
        site.jinja_env.globals[function.__name__] = function

####################################################################################################

@filter_function
def bytestring(x):
    try:
        return voussoirkit.bytestring.bytestring(x)
    except Exception as exc:
        return '??? b'

@filter_function
def comma_join(l):
    if not l:
        return ''
    return ', '.join(l)

@filter_function
def file_link(photo, short=False):
    if short:
        return f'/photo/{photo.id}/download/{photo.id}{photo.dot_extension}'
    basename = jinja2.filters.do_urlencode(photo.basename)
    return f'/photo/{photo.id}/download/{basename}'

@filter_function
def islice(gen, start, stop):
    return itertools.islice(gen, start, stop)

@filter_function
def join_and_trail(l, s):
    if not l:
        return ''
    return s.join(l) + s

@filter_function
def timestamp_to_8601(timestamp):
    return timestamp.isoformat(' ')

@filter_function
def timestamp_strftime(timestamp, format):
    return timestamp.strftime(format)

@filter_function
def timestamp_to_naturaldate(timestamp):
    return timestamp_strftime(timestamp, '%B %d, %Y')

@filter_function
def users_to_usernames(users):
    if not users:
        return []
    return [user.username for user in users]

####################################################################################################

@global_function
def make_attributes(*booleans, **keyvalues):
    keyvalues = {
        key.replace('_', '-'): value
        for (key, value) in keyvalues.items()
        if value is not None
    }
    attributes = [f'{key}="{jinja2.filters.escape(value)}"' for (key, value) in keyvalues.items()]
    attributes.extend(booleans)
    attributes = ' '.join(attributes)
    return attributes
