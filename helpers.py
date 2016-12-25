import datetime
import math
import mimetypes
import os

import constants
import exceptions

from voussoirkit import bytestring

def album_zip_directories(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping Album objects to directory
    names as they will appear inside the zip archive.
    Sub-albums become subfolders.
    '''
    directories = {}
    if album.title:
        root_folder = '%s - %s' % (album.id, normalize_filepath(album.title))
    else:
        root_folder = '%s' % album.id

    directories[album] = root_folder
    if recursive:
        for child_album in album.children():
            child_directories = album_zip_directories(child_album, recursive=True)
            for (child_album, child_directory) in child_directories.items():
                child_directory = os.path.join(root_folder, child_directory)
                directories[child_album] = child_directory
    return directories
    
def album_zip_filenames(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping local filepaths to the filenames
    that will appear inside the zip archive.
    This includes creating subfolders for sub albums.

    If a photo appears in multiple albums, only the first is used.
    '''
    arcnames = {}
    directories = album_zip_directories(album, recursive=recursive)
    for (album, directory) in directories.items():
        photos = album.photos()
        for photo in photos:
            if photo.real_filepath in arcnames:
                continue
            photo_name = '%s - %s' % (photo.id, photo.basename)
            arcnames[photo.real_filepath] = os.path.join(directory, photo_name)

    return arcnames

def binding_filler(column_names, values, require_all=True):
    '''
    Manually aligning question marks and bindings is annoying.
    Given the table's column names and a dictionary of {column: value},
    return the question marks and the list of bindings in the right order.
    '''
    values = values.copy()
    for column in column_names:
        if column in values:
            continue
        if require_all:
            raise ValueError('Missing column "%s"' % column)
        else:
            values.setdefault(column, None)
    qmarks = '?' * len(column_names)
    qmarks = ', '.join(qmarks)
    bindings = [values[column] for column in column_names]
    return (qmarks, bindings)

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

def normalize_extension(extension):
    pass

def normalize_filepath(filepath, allowed=''):
    '''
    Remove some bad characters.
    '''
    badchars = remove_characters(constants.FILENAME_BADCHARS, allowed)
    filepath = remove_characters(filepath, badchars)

    filepath = filepath.replace('/', os.sep)
    filepath = filepath.replace('\\', os.sep)
    return filepath

def now(timestamp=True):
    '''
    Return the current UTC timestamp or datetime object.
    '''
    n = datetime.datetime.now(datetime.timezone.utc)
    if timestamp:
        return n.timestamp()
    return n

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

def remove_characters(text, characters):
    translator = {ord(c): None for c in characters}
    text = text.translate(translator)
    return text

def remove_control_characters(text):
    '''
    Thanks SilentGhost
    http://stackoverflow.com/a/4324823
    '''
    translator = dict.fromkeys(range(32))
    text = text.translate(translator)
    return text

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
    bindings = bindings or []
    cursor = sql.cursor()
    cursor.execute(query, bindings)
    while True:
        fetch = cursor.fetchone()
        if fetch is None:
            break
        yield fetch

def truthystring(s):
    if isinstance(s, (bool, int)) or s is None:
        return s
    s = s.lower()
    if s in {'1', 'true', 't', 'yes', 'y', 'on'}:
        return True
    if s in {'null', 'none'}:
        return None
    return False


def _unitconvert(value):
    '''
    When parsing hyphenated ranges, this function is used to convert
    strings like "1k" to 1024 and "1:00" to 60.
    '''
    if value is None:
        return None
    if ':' in value:
        return hms_to_seconds(value)
    elif all(c in '0123456789.' for c in value):
        return float(value)
    else:
        return bytestring.parsebytes(value)