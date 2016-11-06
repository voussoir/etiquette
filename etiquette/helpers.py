import math

import constants

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

def read_filebytes(filepath, range_min, range_max):
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
            chunk = f.read(constants.FILE_READ_CHUNK)
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
