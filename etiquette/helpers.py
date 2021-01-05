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
import zipstream

from voussoirkit import bytestring
from voussoirkit import hms
from voussoirkit import imagetools
from voussoirkit import pathclass
from voussoirkit import stringtools

from . import constants
from . import exceptions

def album_as_directory_map(
        album,
        naming='simplified',
        once_each=True,
        recursive=True,
        root_name=None,
    ):
    '''
    Given an album, produce a dictionary mapping Album objects to directory
    names as they will appear inside the zip archive.
    Sub-albums become subfolders.

    once_each:
        If an album is a child of multiple albums, only one instance is used.
    '''
    directories = {}
    if root_name is not None:
        pass
    elif naming == 'simplified':
        root_name = album.display_name
    elif naming == 'unambiguous':
        root_name = album.full_name
    else:
        raise ValueError(naming)
    root_name = remove_path_badchars(root_name)

    if once_each:
        directories[album] = root_name
    else:
        directories[album] = [root_name]

    if not recursive:
        return directories

    children = album.get_children()
    if naming == 'simplified':
        child_names = decollide_names(children, lambda c: c.display_name)
    elif naming == 'unambiguous':
        child_names = {child: child.full_name for child in children}

    child_maps = (
        album_as_directory_map(
            child,
            once_each=once_each,
            recursive=True,
            root_name=child_names[child],
        )
        for child in children
    )
    descendants = (
        pair
        for child_map in child_maps
        for pair in child_map.items()
    )
    for (child_album, child_directory) in descendants:
        if once_each:
            child_directory = os.path.join(root_name, child_directory)
            directories[child_album] = child_directory
        else:
            child_directory = [os.path.join(root_name, d) for d in child_directory]
            directories.setdefault(child_album, []).extend(child_directory)

    return directories

def album_photos_as_filename_map(
        album,
        naming='simplified',
        once_each=True,
        recursive=True,
        root_name=None,
    ):
    '''
    Given an album, produce a dictionary mapping Photo objects to the
    filenames that will appear inside the zip archive.
    This includes creating subfolders for sub albums.

    once_each:
        If a photo appears in multiple albums, only one instance is used.
    '''
    arcnames = {}

    directories = album_as_directory_map(
        album,
        once_each=once_each,
        recursive=recursive,
        root_name=root_name,
    )

    for (album, directory) in directories.items():
        photos = album.get_photos()
        if naming == 'simplified':
            photo_names = decollide_names(photos, lambda p: p.basename)
        elif naming == 'unambiguous':
            photo_names = {photo: f'{photo.id} - {photo.basename}' for photo in photos}
        for photo in photos:
            photo_name = photo_names[photo]
            if once_each:
                arcname = os.path.join(directory, photo_name)
                arcnames[photo] = arcname
            else:
                arcname = [os.path.join(d, photo_name) for d in directory]
                arcnames.setdefault(photo, []).extend(arcname)

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

def decollide_names(things, namer):
    '''
    When generating zip files, or otherwise exporting photos to disk, it is
    aesthetically preferable to export them using just their basename. But,
    since multiple photos might have the same basename, we occasionally need to
    use their IDs to disambiguate them.
    This function automates that by keeping the basename wherever possible, and
    prefixing items with their ID in the case of a name collision.
    This function takes `things`, which is a collection of either Albums or
    Photos, and `namer` which is a callable that gives us the preferred name
    of the thing (in practice, just a lambda returning Album title,
    Photo basename), and returns a map of {thing: name}. If there are duplicate
    names, they will be disambiguated by adding "id - " to the front.
    '''
    # The majority of this algorithm is dedicated to solving the case where some
    # prankster has named their album such that it contains the ID of another
    # album.
    # For example, consider three Albums (1, "A"), (2, "A"), (3, "1 - A").
    # So when 1 and 2 get disambiguated to (1, "1 - A"), (2, "2 - A"),
    # then suddenly there is a new collision between (1, "1 - A") and
    # (3, "1 - A"), and we need to disambiguate by renaming 3 to "3 - 1 - A".
    # I'm not totally happy with how this function looks, but as long as I get
    # it working I'll just stop looking at it and problem solved!
    collisions = {}
    final = {}
    for thing in things:
        name = namer(thing)
        collisions.setdefault(name, []).append(thing)
        final[thing] = name

    # When the thing is disambiguated by adding its ID, it's done being
    # decollided and can be locked. This ensures that if disambiguating one
    # thing causes a new collision with a prank entry, only the prank needs to
    # get renamed on the second pass. We don't need to keep prefixing the
    # thing's ID onto the same thing over and over again.
    locked = set()
    while True:
        collision = {
            name: set(things).difference(locked)
            for (name, things) in collisions.items()
            if len(things) > 1
        }
        if not collision:
            break
        for (name, things) in collision.items():
            for thing in things:
                myname = f'{thing.id} - {name}'
                locked.add(thing)
                collisions[name].remove(thing)
                collisions.setdefault(myname, []).append(thing)
                final[thing] = myname
    return final

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

    if not probe or not probe.video:
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
    Try to parse the string as an int, float, or bytestring, or hms.
    '''
    if s is None:
        return None

    s = s.strip()

    if ':' in s:
        return hms.hms_to_seconds(s)

    elif all(c in '0123456789' for c in s):
        return int(s)

    elif all(c in '0123456789.' for c in s):
        return float(s)

    else:
        return bytestring.parsebytes(s)

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

    f = filepath.open('rb')
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

def remove_path_badchars(filepath, allowed=''):
    '''
    Remove the bad characters seen in constants.FILENAME_BADCHARS, except
    those which you explicitly permit.

    'file*name' -> 'filename'
    ('D:\\file*name', allowed=':\\') -> 'D:\\filename'
    '''
    badchars = stringtools.remove_characters(constants.FILENAME_BADCHARS, allowed)
    filepath = stringtools.remove_characters(filepath, badchars)
    filepath = stringtools.remove_control_characters(filepath)

    filepath = filepath.replace('/', os.sep)
    filepath = filepath.replace('\\', os.sep)
    return filepath

def run_generator(g):
    for x in g:
        pass

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
    arcnames = album_photos_as_filename_map(album, once_each=True, recursive=recursive)
    for (photo, arcname) in arcnames.items():
        zipfile.write(filename=photo.real_path.absolute_path, arcname=arcname)

    # Add the album metadata as an {id}.txt file within each directory.
    directories = album_as_directory_map(album, once_each=True, recursive=recursive)
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
