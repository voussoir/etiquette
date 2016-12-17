import math
import mimetypes
import os

import exceptions
import constants
import warnings

def chunk_sequence(sequence, chunk_length, allow_incomplete=True):
    '''
    Given a sequence, divide it into sequences of length `chunk_length`.

    allow_incomplete:
        If True, allow the final chunk to be shorter if the
        given sequence is not an exact multiple of `chunk_length`.
        If False, the incomplete chunk will be discarded.
    '''
    (complete, leftover) = divmod(len(sequence), chunk_length)
    if not allow_incomplete:
        leftover = 0

    chunk_count = complete + min(leftover, 1)

    chunks = []
    for x in range(chunk_count):
        left = chunk_length * x
        right = left + chunk_length
        chunks.append(sequence[left:right])

    return chunks

def comma_split(s):
    '''
    Split the string apart by commas, discarding all extra whitespace and
    blank phrases.
    '''
    if s is None:
        return s
    s = s.replace(' ', ',')
    s = [x.strip() for x in s.split(',')]
    s = [x for x in s if x]
    return s

def edit_params(original, modifications):
    '''
    Given a dictionary representing URL parameters,
    apply the modifications and return a URL parameter string.

    {'a':1, 'b':2}, {'b':3} => ?a=1&b=3
    '''
    new_params = original.copy()
    new_params.update(modifications)
    if not new_params:
        return ''
    new_params = ['%s=%s' % (k, v) for (k, v) in new_params.items() if v]
    new_params = '&'.join(new_params)
    if new_params:
        new_params = '?' + new_params
    return new_params

def fit_into_bounds(image_width, image_height, frame_width, frame_height):
    '''
    Given the w+h of the image and the w+h of the frame,
    return new w+h that fits the image into the frame
    while maintaining the aspect ratio.
    '''
    ratio = min(frame_width/image_width, frame_height/image_height)

    new_width = int(image_width * ratio)
    new_height = int(image_height * ratio)

    return (new_width, new_height)

def get_mimetype(filepath):
    extension = os.path.splitext(filepath)[1].replace('.', '')
    if extension in constants.ADDITIONAL_MIMETYPES:
        return constants.ADDITIONAL_MIMETYPES[extension]
    mimetype = mimetypes.guess_type(filepath)[0]
    if mimetype is not None:
        mimetype = mimetype.split('/')[0]
    return mimetype

def hyphen_range(s):
    '''
    Given a string like '1-3', return ints (1, 3) representing lower
    and upper bounds.

    Supports bytestring.parsebytes and hh:mm:ss format.
    '''
    s = s.strip()
    s = s.replace(' ', '')
    if not s:
        return (None, None)
    parts = s.split('-')
    parts = [part.strip() or None for part in parts]
    if len(parts) == 1:
        low = parts[0]
        high = None
    elif len(parts) == 2:
        (low, high) = parts
    else:
        raise ValueError('Too many hyphens')

    low = _unitconvert(low)
    high = _unitconvert(high)
    if low is not None and high is not None and low > high:
        raise exceptions.OutOfOrder(s, low, high)
    return low, high

def hms_to_seconds(hms):
    '''
    Convert hh:mm:ss string to an integer seconds.
    '''
    hms = hms.split(':')
    seconds = 0
    if len(hms) == 3:
        seconds += int(hms[0])*3600
        hms.pop(0)
    if len(hms) == 2:
        seconds += int(hms[0])*60
        hms.pop(0)
    if len(hms) == 1:
        seconds += int(hms[0])
    return seconds

def is_xor(*args):
    '''
    Return True if and only if one arg is truthy.
    '''
    return [bool(a) for a in args].count(True) == 1

def read_filebytes(filepath, range_min, range_max, chunk_size=2 ** 20):
    '''
    Yield chunks of bytes from the file between the endpoints.
    '''
    range_span = range_max - range_min

    #print('read span', range_min, range_max, range_span)
    f = open(filepath, 'rb')
    f.seek(range_min)
    sent_amount = 0
    with f:
        while sent_amount < range_span:
            #print(sent_amount)
            chunk = f.read(chunk_size)
            if len(chunk) == 0:
                break

            yield chunk
            sent_amount += len(chunk)

def seconds_to_hms(seconds):
    '''
    Convert integer number of seconds to an hh:mm:ss string.
    Only the necessary fields are used.
    '''
    seconds = math.ceil(seconds)
    (minutes, seconds) = divmod(seconds, 60)
    (hours, minutes) = divmod(minutes, 60)
    parts = []
    if hours: parts.append(hours)
    if minutes: parts.append(minutes)
    parts.append(seconds)
    hms = ':'.join('%02d' % part for part in parts)
    return hms

def truthystring(s):
    if isinstance(s, (bool, int)) or s is None:
        return s
    s = s.lower()
    if s in {'1', 'true', 't', 'yes', 'y', 'on'}:
        return True
    if s in {'null', 'none'}:
        return None
    return False

#===============================================================================

def _minmax(key, value, minimums, maximums):
    '''
    When searching, this function dissects a hyphenated range string
    and inserts the correct k:v pair into both minimums and maximums.
    ('area', '100-200', {}, {}) --> {'area': 100}, {'area': 200} (MODIFIED IN PLACE)
    '''
    if value is None:
        return
    if isinstance(value, (int, float)):
        minimums[key] = value
        return
    try:
        (low, high) = hyphen_range(value)
    except ValueError:
        warnings.warn(constants.WARNING_MINMAX_INVALID.format(field=key, value=value))
        return
    except exceptions.OutOfOrder as e:
        warnings.warn(constants.WARNING_MINMAX_OOO.format(field=key, min=e.args[1], max=e.args[2]))
        return
    if low is not None:
        minimums[key] = low
    if high is not None:
        maximums[key] = high

def _normalize_extensions(extensions):
    '''
    When searching, this function normalizes the list of inputted extensions.
    '''
    if isinstance(extensions, str):
        extensions = extensions.split()
    if extensions is None:
        return set()
    extensions = [e.lower().strip('.').strip() for e in extensions]
    extensions = set(e for e in extensions if e)
    return extensions

def _orderby(orderby):
    '''
    When searching, this function ensures that the user has entered a valid orderby
    query, and normalizes the query text.

    'random asc' --> ('random', 'asc')
    'area' --> ('area', 'desc')
    '''
    orderby = orderby.lower().strip()
    if orderby == '':
        return None

    orderby = orderby.split(' ')
    if len(orderby) == 2:
        (column, sorter) = orderby
    elif len(orderby) == 1:
        column = orderby[0]
        sorter = 'desc'
    else:
        return None

    #print(column, sorter)
    if column not in constants.ALLOWED_ORDERBY_COLUMNS:
        warnings.warn(constants.WARNING_ORDERBY_BADCOL.format(column=column))
        return None
    if column == 'random':
        column = 'RANDOM()'

    if sorter not in ['desc', 'asc']:
        warnings.warn(constants.WARNING_ORDERBY_BADSORTER.format(column=column, sorter=sorter))
        sorter = 'desc'
    return (column, sorter)

def _setify_tags(photodb, tags, warn_bad_tags=False):
    '''
    When searching, this function converts the list of tag strings that the user
    requested into Tag objects. If a tag doesn't exist we'll either raise an exception
    or just issue a warning.
    '''
    if tags is None:
        return set()

    tagset = set()
    for tag in tags:
        tag = tag.strip()
        if tag == '':
            continue
        try:
            tag = photodb.get_tag(tag)
            tagset.add(tag)
        except exceptions.NoSuchTag:
            if warn_bad_tags:
                warnings.warn(constants.WARNING_NO_SUCH_TAG.format(tag=tag))
                continue
            else:
                raise

    return tagset

def _unitconvert(value):
    '''
    When parsing hyphenated ranges, this function is used to convert
    strings like "1k" to 1024 and "1:00" to 60.
    '''
    if value is None:
        return None
    if ':' in value:
        return helpers.hms_to_seconds(value)
    elif all(c in '0123456789.' for c in value):
        return float(value)
    else:
        return bytestring.parsebytes(value)
