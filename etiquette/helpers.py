'''
This file provides functions which are used in various places throughout the
codebase but don't deserve to be methods of any class.
'''
import datetime
import hashlib
import math
import mimetypes
import os
import PIL.Image
import re
import unicodedata
import zipstream

from voussoirkit import bytestring
from voussoirkit import imagetools
from voussoirkit import pathclass

from . import constants
from . import exceptions

def album_as_directory_map(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping Album objects to directory
    names as they will appear inside the zip archive.
    Sub-albums become subfolders.

    If an album is a child of multiple albums, only one instance is used.
    '''
    directories = {}
    if album.title:
        title = remove_path_badchars(album.title)
        root_folder = f'album {album.id} - {title}'
    else:
        root_folder = f'album {album.id}'

    directories[album] = root_folder
    if recursive:
        for child_album in album.get_children():
            child_directories = album_as_directory_map(child_album, recursive=True)
            for (child_album, child_directory) in child_directories.items():
                child_directory = os.path.join(root_folder, child_directory)
                directories[child_album] = child_directory

    return directories

def album_photos_as_filename_map(album, recursive=True):
    '''
    Given an album, produce a dictionary mapping Photo objects to the
    filenames that will appear inside the zip archive.
    This includes creating subfolders for sub albums.

    If a photo appears in multiple albums, only one instance is used.
    '''
    arcnames = {}
    directories = album_as_directory_map(album, recursive=recursive)
    for (album, directory) in directories.items():
        photos = album.get_photos()
        for photo in photos:
            photo_name = f'{photo.id} - {photo.basename}'
            arcnames[photo] = os.path.join(directory, photo_name)

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
    Given a sequence, yield lists of length `chunk_length`.

    allow_incomplete:
        If True, allow the final chunk to be shorter if the
        given sequence is not an exact multiple of `chunk_length`.
        If False, the incomplete chunk will be discarded.
    '''
    import itertools
    iterator = iter(sequence)
    while True:
        chunk = list(itertools.islice(iterator, chunk_length))
        if not chunk:
            break
        if len(chunk) == chunk_length or allow_incomplete:
            yield chunk

def comma_space_split(s):
    '''
    Split the string apart by commas and spaces, discarding all extra
    whitespace and blank phrases.

    'a b, c,,d' -> ['a', 'b', 'c', 'd']
    '''
    if s is None:
        return s
    return re.split(r'[ ,]+', s.strip())

def dict_to_tuple(d):
    return tuple(sorted(d.items()))

def generate_image_thumbnail(filepath, width, height):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(filepath)
    image = PIL.Image.open(filepath)
    (image_width, image_height) = image.size
    (new_width, new_height) = imagetools.fit_into_bounds(
        image_width=image_width,
        image_height=image_height,
        frame_width=width,
        frame_height=height,
        only_shrink=True,
    )
    if (new_width, new_height) != (image_width, image_height):
        image = image.resize((new_width, new_height))

    if image.mode == 'RGBA':
        background = checkerboard_image(
            color_1=(256, 256, 256),
            color_2=(128, 128, 128),
            image_size=image.size,
            checker_size=8,
        )
        # Thanks Yuji Tomita
        # http://stackoverflow.com/a/9459208
        background.paste(image, mask=image.split()[3])
        image = background

    image = image.convert('RGB')
    return image

def generate_video_thumbnail(filepath, outfile, width, height, **special):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(filepath)
    probe = constants.ffmpeg.probe(filepath)
    if not probe.video:
        return False

    size = imagetools.fit_into_bounds(
        image_width=probe.video.video_width,
        image_height=probe.video.video_height,
        frame_width=width,
        frame_height=height,
    )
    size = '%dx%d' % size
    duration = probe.video.duration

    if 'timestamp' in special:
        timestamp = special['timestamp']
    elif duration < 3:
        timestamp = 0
    else:
        timestamp = 2

    constants.ffmpeg.thumbnail(
        filepath,
        outfile=outfile,
        quality=2,
        size=size,
        time=timestamp,
    )
    return True

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

def hash_file(filepath, hasher):
    bytestream = read_filebytes(filepath)
    for chunk in bytestream:
        hasher.update(chunk)
    return hasher.hexdigest()

def hash_file_md5(filepath):
    return hash_file(filepath, hasher=hashlib.md5())

def hash_photoset(photos):
    '''
    Given some photos, return a fingerprint string for that particular set.
    '''
    hasher = hashlib.md5()

    photo_ids = sorted(set(p.id for p in photos))
    for photo_id in photo_ids:
        hasher.update(photo_id.encode('utf-8'))

    return hasher.hexdigest()

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
        (low, high) = (parts[0], None)
    elif len(parts) == 2:
        (low, high) = parts
    else:
        raise ValueError('Too many hyphens.')

    low = parse_unit_string(low)
    high = parse_unit_string(high)

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
        seconds += int(hms[0]) * 3600
        hms.pop(0)
    if len(hms) == 2:
        seconds += int(hms[0]) * 60
        hms.pop(0)
    if len(hms) == 1:
        seconds += float(hms[0])
    return seconds

def is_xor(*args):
    '''
    Return True if and only if one arg is truthy.
    '''
    return [bool(a) for a in args].count(True) == 1

def natural_sorter(x):
    '''
    Used for sorting files in 'natural' order instead of lexicographic order,
    so that you get 1 2 3 4 5 6 7 8 9 10 11 12 13 ...
    instead of 1 10 11 12 13 2 3 4 5 ...
    Thank you Mark Byers
    http://stackoverflow.com/a/11150413
    '''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return alphanum_key(x)

def now(timestamp=True):
    '''
    Return the current UTC timestamp or datetime object.
    '''
    n = datetime.datetime.now(datetime.timezone.utc)
    if timestamp:
        return n.timestamp()
    return n

def parse_unit_string(s):
    '''
    Try to parse the string as a float, or bytestring, or hms.
    '''
    if s is None:
        return None

    if ':' in s:
        return hms_to_seconds(s)

    elif all(c in '0123456789.' for c in s):
        return float(s)

    else:
        return bytestring.parsebytes(s)

def random_hex(length=12):
    randbytes = os.urandom(math.ceil(length / 2))
    token = ''.join('{:02x}'.format(x) for x in randbytes)
    token = token[:length]
    return token

def read_filebytes(filepath, range_min=0, range_max=None, chunk_size=bytestring.MIBIBYTE):
    '''
    Yield chunks of bytes from the file between the endpoints.
    '''
    filepath = pathclass.Path(filepath)
    if not filepath.exists:
        raise FileNotFoundError(filepath)
    if range_max is None:
        range_max = filepath.size
    range_span = (range_max + 1) - range_min

    f = open(filepath.absolute_path, 'rb')
    sent_amount = 0
    with f:
        f.seek(range_min)
        while sent_amount < range_span:
            chunk = f.read(chunk_size)
            if len(chunk) == 0:
                break

            needed = range_span - sent_amount
            if len(chunk) >= needed:
                yield chunk[:needed]
                break

            yield chunk
            sent_amount += len(chunk)

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

def run_generator(g):
    for x in g:
        pass

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
    if hours or minutes:
        parts.append(minutes)
    parts.append(seconds)
    hms = ':'.join(f'{part:02d}' for part in parts)
    return hms

def slice_before(li, item):
    index = li.index(item)
    return li[:index]

def split_easybake_string(ebstring):
    '''
    Given an easybake string, return (tagname, synonym, rename_to), where
    tagname may be a full qualified name, and at least one of
    synonym or rename_to will be None since both are not posible at once.

    'languages.python' -> ('languages.python', None, None)
    'languages.python+py' -> ('languages.python', 'py', None)
    'languages.python=bestlang' -> ('languages.python', None, 'bestlang')
    '''
    ebstring = ebstring.strip()
    ebstring = ebstring.strip('.+=')

    if ebstring == '':
        raise exceptions.EasyBakeError('No tag supplied.')

    if '=' in ebstring and '+' in ebstring:
        raise exceptions.EasyBakeError('Cannot rename and assign snynonym at once.')

    rename_parts = ebstring.split('=')
    if len(rename_parts) > 2:
        raise exceptions.EasyBakeError('Too many equals signs.')

    if len(rename_parts) == 2:
        (ebstring, rename_to) = rename_parts

    elif len(rename_parts) == 1:
        (ebstring, rename_to) = (rename_parts[0], None)

    synonym_parts = ebstring.split('+')
    if len(synonym_parts) > 2:
        raise exceptions.EasyBakeError('Too many plus signs.')

    if len(synonym_parts) == 2:
        (tagname, synonym) = synonym_parts

    elif len(synonym_parts) == 1:
        (tagname, synonym) = (synonym_parts[0], None)

    if not tagname:
        raise exceptions.EasyBakeError('No tag supplied.')

    tagname = tagname.strip('.')
    return (tagname, synonym, rename_to)

def truthystring(s):
    '''
    If s is already a boolean, int, or None, return a boolean or None.
    If s is a string, return True, False, or None based on the options presented
    in constants.TRUTHYSTRING_TRUE, constants.TRUTHYSTRING_NONE, or False
    for all else. Case insensitive.
    '''
    if s is None:
        return None

    if isinstance(s, (bool, int)):
        return bool(s)

    if not isinstance(s, str):
        raise TypeError(f'String should be {bool}, {int}, {str}, or None, not {type(s)}.')

    s = s.lower()
    if s in constants.TRUTHYSTRING_TRUE:
        return True
    if s in constants.TRUTHYSTRING_NONE:
        return None
    return False

def zip_album(album, recursive=True):
    '''
    Given an album, return a zipstream zipfile that contains the album's
    photos (recursive = include children's photos) organized into folders
    for each album. Each album folder also gets a text file containing
    the album's name and description if applicable.

    If an album is a child of multiple albums, only one instance is used.
    If a photo appears in multiple albums, only one instance is used.
    '''
    zipfile = zipstream.ZipFile()

    # Add the photos.
    arcnames = album_photos_as_filename_map(album, recursive=recursive)
    for (photo, arcname) in arcnames.items():
        zipfile.write(filename=photo.real_path.absolute_path, arcname=arcname)

    # Add the album metadata as an {id}.txt file within each directory.
    directories = album_as_directory_map(album, recursive=recursive)
    for (inner_album, directory) in directories.items():
        metafile_text = []
        if inner_album.title:
            metafile_text.append(f'Title: {inner_album.title}')

        if inner_album.description:
            metafile_text.append(f'Description: {inner_album.description}')

        if not metafile_text:
            continue

        metafile_text = '\r\n\r\n'.join(metafile_text)
        metafile_text = metafile_text.encode('utf-8')
        metafile_name = f'album {inner_album.id}.txt'
        metafile_name = os.path.join(directory, metafile_name)
        zipfile.writestr(
            arcname=metafile_name,
            data=metafile_text,
        )

    return zipfile

def zip_photos(photos):
    '''
    Given some photos, return a zipstream zipfile that contains the files.
    '''
    zipfile = zipstream.ZipFile()

    for photo in photos:
        if not photo.real_path.is_file:
            continue
        arcname = os.path.join('photos', f'{photo.id} - {photo.basename}')
        zipfile.write(filename=photo.real_path.absolute_path, arcname=arcname)

    return zipfile
