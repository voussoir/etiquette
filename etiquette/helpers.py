'''
This file provides functions which are used in various places throughout the
codebase but don't deserve to be methods of any class.
'''

import datetime
import math
import mimetypes
import os
import PIL.Image
import unicodedata

from . import constants
from . import exceptions

from voussoirkit import bytestring

def album_zip_directories(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping Album objects to directory
    names as they will appear inside the zip archive.
    Sub-albums become subfolders.
    '''
    directories = {}
    if album.title:
        root_folder = 'album %s - %s' % (album.id, remove_path_badchars(album.title))
    else:
        root_folder = 'album %s' % album.id

    directories[album] = root_folder
    if recursive:
        for child_album in album.get_children():
            child_directories = album_zip_directories(child_album, recursive=True)
            for (child_album, child_directory) in child_directories.items():
                child_directory = os.path.join(root_folder, child_directory)
                directories[child_album] = child_directory
    return directories

def album_zip_filenames(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping local filepaths to the
    filenames that will appear inside the zip archive.
    This includes creating subfolders for sub albums.

    If a photo appears in multiple albums, only the first is used.
    '''
    arcnames = {}
    directories = album_zip_directories(album, recursive=recursive)
    for (album, directory) in directories.items():
        photos = album.get_photos()
        for photo in photos:
            filepath = photo.real_path.absolute_path
            if filepath in arcnames:
                continue
            photo_name = '%s - %s' % (photo.id, photo.basename)
            arcnames[filepath] = os.path.join(directory, photo_name)

    return arcnames

def checkerboard_image(color_1, color_2, image_size, checker_size):
    '''
    Generate a PIL Image with a checkerboard pattern.

    color_1:
        The color starting in the top left. Either RGB tuple or a string
        that PIL understands.
    color_2:
        The alternate color
    image_size:
        Tuple of two integers, the image size in pixels.
    checker_size:
        Tuple of two integers, the size of each checker in pixels.
    '''
    image = PIL.Image.new('RGB', image_size, color_1)
    checker = PIL.Image.new('RGB', (checker_size, checker_size), color_2)
    offset = True
    for y in range(0, image_size[1], checker_size):
        for x in range(0, image_size[0], checker_size * 2):
            x += offset * checker_size
            image.paste(checker, (x, y))
        offset = not offset
    return image

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

def comma_space_split(s):
    '''
    Split the string apart by commas and spaces, discarding all extra
    whitespace and blank phrases.

    'a b, c,,d' -> ['a', 'b', 'c', 'd']
    '''
    if s is None:
        return s
    s = s.replace(' ', ',')
    s = [x.strip() for x in s.split(',')]
    s = [x for x in s if x]
    return s

def dict_to_params(d):
    '''
    Given a dictionary of URL parameters, return a URL parameter string.

    {'a':1, 'b':2} -> '?a=1&b=2'
    '''
    if not d:
        return ''
    params = ['%s=%s' % (k, v) for (k, v) in d.items() if v]
    params = '&'.join(params)
    if params:
        params = '?' + params
    return params

def fit_into_bounds(image_width, image_height, frame_width, frame_height):
    '''
    Given the w+h of the image and the w+h of the frame,
    return new w+h that fits the image into the frame
    while maintaining the aspect ratio.

    (1920, 1080, 400, 400) -> (400, 225)
    '''
    ratio = min(frame_width/image_width, frame_height/image_height)

    new_width = int(image_width * ratio)
    new_height = int(image_height * ratio)

    return (new_width, new_height)

def get_mimetype(filepath):
    '''
    Extension to mimetypes.guess_type which uses my
    constants.ADDITIONAL_MIMETYPES.
    '''
    extension = os.path.splitext(filepath)[1].replace('.', '')
    mimetype = constants.ADDITIONAL_MIMETYPES.get(extension, None)
    if mimetype is None:
        mimetype = mimetypes.guess_type(filepath)[0]
    return mimetype

def hyphen_range(s):
    '''
    Given a string like '1-3', return numbers (1, 3) representing lower
    and upper bounds.

    Supports bytestring.parsebytes and hh:mm:ss format, for example
    '1k-2k', '10:00-20:00', '4gib-'
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
        raise exceptions.OutOfOrder(range=s, min=low, max=high)
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
        seconds += float(hms[0])
    return seconds

def is_xor(*args):
    '''
    Return True if and only if one arg is truthy.
    '''
    return [bool(a) for a in args].count(True) == 1

def now(timestamp=True):
    '''
    Return the current UTC timestamp or datetime object.
    '''
    n = datetime.datetime.now(datetime.timezone.utc)
    if timestamp:
        return n.timestamp()
    return n

def random_hex(length=12):
    randbytes = os.urandom(math.ceil(length / 2))
    token = ''.join('{:02x}'.format(x) for x in randbytes)
    token = token[:length]
    return token

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

def recursive_dict_update(target, supply):
    '''
    Update target using supply, but when the value is a dictionary update the
    insides instead of replacing the dictionary itself.
    '''
    for (key, value) in supply.items():
        if isinstance(value, dict):
            existing = target.get(key, None)
            if existing is None:
                target[key] = value
            else:
                recursive_dict_update(existing, value)
        else:
            target[key] = value

def recursive_dict_keys(d):
    '''
    Given a dictionary, return a set containing all of its keys and the keys of
    all other dictionaries that appear as values within. The subkeys will use \\
    to indicate their lineage.

    {
        'hi': {
            'ho': 'neighbor'
        }
    }

    returns

    {'hi', 'hi\\ho'}
    '''
    keys = set(d.keys())
    for (key, value) in d.items():
        if isinstance(value, dict):
            subkeys = {'%s\\%s' % (key, subkey) for subkey in recursive_dict_keys(value)}
            keys.update(subkeys)
    return keys

def remove_characters(text, characters):
    translator = {ord(c): None for c in characters}
    text = text.translate(translator)
    return text

def remove_control_characters(text):
    '''
    Thanks Alex Quinn
    https://stackoverflow.com/a/19016117

    unicodedata.category(character) returns some two-character string
    where if [0] is a C then the character is a control character.
    '''
    return ''.join(c for c in text if unicodedata.category(c)[0] != 'C')

def remove_path_badchars(filepath, allowed=''):
    '''
    Remove the bad characters seen in constants.FILENAME_BADCHARS, except
    those which you explicitly permit.

    'file*name' -> 'filename'
    ('D:\\file*name', allowed=':\\') -> 'D:\\filename'
    '''
    badchars = remove_characters(constants.FILENAME_BADCHARS, allowed)
    filepath = remove_characters(filepath, badchars)
    filepath = remove_control_characters(filepath)

    filepath = filepath.replace('/', os.sep)
    filepath = filepath.replace('\\', os.sep)
    return filepath

def seconds_to_hms(seconds):
    '''
    Convert integer number of seconds to an hh:mm:ss string.
    Only the necessary fields are used.
    '''
    seconds = math.ceil(seconds)
    (minutes, seconds) = divmod(seconds, 60)
    (hours, minutes) = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(hours)
    if minutes:
        parts.append(minutes)
    parts.append(seconds)
    hms = ':'.join('%02d' % part for part in parts)
    return hms

def select_generator(sql, query, bindings=None):
    '''
    Perform the query, and yield the results.
    '''
    bindings = bindings or []
    cursor = sql.cursor()
    cursor.execute(query, bindings)
    while True:
        fetch = cursor.fetchone()
        if fetch is None:
            break
        yield fetch

def sql_listify(items):
    '''
    Given a list of strings, return a string in the form of an SQL list.

    ['hi', 'ho', 'hey'] -> '("hi", "ho", "hey")'
    '''
    return '(%s)' % ', '.join('"%s"' % item for item in items)

def truthystring(s):
    '''
    Convert strings to True, False, or None based on the options presented
    in constants.TRUTHYSTRING_TRUE, constants.TRUTHYSTRING_NONE, or False
    for all else.

    Case insensitive.
    '''
    if isinstance(s, (bool, int)) or s is None:
        return s
    s = s.lower()
    if s in constants.TRUTHYSTRING_TRUE:
        return True
    if s in constants.TRUTHYSTRING_NONE:
        return None
    return False


_numerical_characters = set('0123456789.')
def _unitconvert(value):
    '''
    When parsing hyphenated ranges, this function is used to convert
    strings like "1k" to 1024 and "1:00" to 60.
    '''
    if value is None:
        return None
    if ':' in value:
        return hms_to_seconds(value)
    elif all(c in _numerical_characters for c in value):
        return float(value)
    else:
        return bytestring.parsebytes(value)
