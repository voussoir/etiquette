import collections
import converter
import datetime
import functools
import logging
import mimetypes
import os
import PIL.Image
import random
import re
import sqlite3
import string
import sys
import time
import traceback
import warnings

import constants
import decorators
import helpers

try:
    sys.path.append('C:\\git\\else\\Bytestring')
    sys.path.append('C:\\git\\else\\Pathclass')
    sys.path.append('C:\\git\\else\\SpinalTap')
    import bytestring
    import pathclass
    import spinal
except ImportError:
    # pip install
    # https://raw.githubusercontent.com/voussoir/else/master/_voussoirkit/voussoirkit.zip
    from voussoirkit import bytestring
    from voussoirkit import pathclass
    from voussoirkit import spinal

try:
    ffmpeg = converter.Converter(
        ffmpeg_path='C:\\software\\ffmpeg\\bin\\ffmpeg.exe',
        ffprobe_path='C:\\software\\ffmpeg\\bin\\ffprobe.exe',
    )
except converter.ffmpeg.FFMpegError:
    traceback.print_exc()
    ffmpeg = None

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

SQL_LASTID_COLUMNS = [
    'table',
    'last_id',
]

SQL_ALBUM_COLUMNS = [
    'id',
    'title',
    'description',
    'associated_directory'
]
SQL_PHOTO_COLUMNS = [
    'id',
    'filepath',
    'override_filename',
    'extension',
    'width',
    'height',
    'ratio',
    'area',
    'duration',
    'bytes',
    'created',
    'thumbnail',
]
SQL_TAG_COLUMNS = [
    'id',
    'name',
]
SQL_SYN_COLUMNS = [
    'name',
    'master',
]
SQL_ALBUMPHOTO_COLUMNS = [
    'albumid',
    'photoid',
]
SQL_PHOTOTAG_COLUMNS = [
    'photoid',
    'tagid',
]
SQL_TAGGROUP_COLUMNS = [
    'parentid',
    'memberid',
]

SQL_ALBUM = {key:index for (index, key) in enumerate(SQL_ALBUM_COLUMNS)}
SQL_ALBUMPHOTO = {key:index for (index, key) in enumerate(SQL_ALBUMPHOTO_COLUMNS)}
SQL_LASTID = {key:index for (index, key) in enumerate(SQL_LASTID_COLUMNS)}
SQL_PHOTO = {key:index for (index, key) in enumerate(SQL_PHOTO_COLUMNS)}
SQL_PHOTOTAG = {key:index for (index, key) in enumerate(SQL_PHOTOTAG_COLUMNS)}
SQL_SYN = {key:index for (index, key) in enumerate(SQL_SYN_COLUMNS)}
SQL_TAG = {key:index for (index, key) in enumerate(SQL_TAG_COLUMNS)}
SQL_TAGGROUP = {key:index for (index, key) in enumerate(SQL_TAGGROUP_COLUMNS)}

DATABASE_VERSION = 1
DB_INIT = '''
PRAGMA count_changes = OFF;
PRAGMA cache_size = 10000;
PRAGMA user_version = {user_version};
CREATE TABLE IF NOT EXISTS albums(
    id TEXT,
    title TEXT,
    description TEXT,
    associated_directory TEXT COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS photos(
    id TEXT,
    filepath TEXT COLLATE NOCASE,
    override_filename TEXT COLLATE NOCASE,
    extension TEXT,
    width INT,
    height INT,
    ratio REAL,
    area INT,
    duration INT,
    bytes INT,
    created INT,
    thumbnail TEXT
);
CREATE TABLE IF NOT EXISTS tags(
    id TEXT,
    name TEXT
);
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid TEXT,
    photoid TEXT
);
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid TEXT,
    tagid TEXT
);
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid TEXT,
    memberid TEXT
);
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT,
    mastername TEXT
);

CREATE TABLE IF NOT EXISTS id_numbers(
    tab TEXT,
    last_id TEXT
);

-- Album
CREATE INDEX IF NOT EXISTS index_album_id on albums(id);
CREATE INDEX IF NOT EXISTS index_albumrel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_albumrel_photoid on album_photo_rel(photoid);

-- Photo
CREATE INDEX IF NOT EXISTS index_photo_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photo_path on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photo_fakepath on photos(override_filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photo_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photo_extension on photos(extension);

-- Tag
CREATE INDEX IF NOT EXISTS index_tag_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tag_name on tags(name);

-- Photo-tag relation
CREATE INDEX IF NOT EXISTS index_tagrel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_tagrel_tagid on photo_tag_rel(tagid);

-- Tag-synonym relation
CREATE INDEX IF NOT EXISTS index_tagsyn_name on tag_synonyms(name);

-- Tag-group relation
CREATE INDEX IF NOT EXISTS index_grouprel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_grouprel_memberid on tag_group_rel(memberid);
'''.format(user_version=DATABASE_VERSION)


def _helper_extension(ext):
    '''
    When searching, this function normalizes the list of permissible extensions.
    '''
    if isinstance(ext, str):
        ext = [ext]
    if ext is None:
        return set()
    ext = [e.lower().strip('.') for e in ext]
    ext = [e for e in ext if e]
    ext = set(ext)
    return ext

def _helper_filenamefilter(subject, terms):
    basename = subject.lower()
    return all(term in basename for term in terms)

def _helper_minmax(key, value, minimums, maximums):
    '''
    When searching, this function dissects a hyphenated range string
    and inserts the correct k:v pair into both minimums and maximums.
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
    except OutOfOrder as e:
        warnings.warn(constants.WARNING_MINMAX_OOO.format(field=key, min=e.args[1], max=e.args[2]))
        return
    if low is not None:
        minimums[key] = low
    if high is not None:
        maximums[key] = high

def _helper_orderby(orderby):
    '''
    When searching, this function ensures that the user has entered a valid orderby
    query, and normalizes the query text.
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
    sortable = column in [
        'extension',
        'width',
        'height',
        'ratio',
        'area',
        'duration',
        'bytes',
        'created',
        'random',
    ]
    if not sortable:
        warnings.warn(constants.WARNING_ORDERBY_BADCOL.format(column=column))
        return None
    if column == 'random':
        column = 'RANDOM()'

    if sorter not in ['desc', 'asc']:
        warnings.warn(constants.WARNING_ORDERBY_BADSORTER.format(column=column, sorter=sorter))
        sorter = 'desc'
    return (column, sorter)

def _helper_setify(photodb, l, warn_bad_tags=False):
    '''
    When searching, this function converts the list of tag strings that the user
    requested into Tag objects. If a tag doesn't exist we'll either raise an exception
    or just issue a warning.
    '''
    if l is None:
        return set()

    s = set()
    for tag in l:
        tag = tag.strip()
        if tag == '':
            continue
        try:
            tag = photodb.get_tag(tag)
        except NoSuchTag:
            if not warn_bad_tags:
                raise
            warnings.warn(constants.WARNING_NO_SUCH_TAG.format(tag=tag))
            continue
        else:
            s.add(tag)
    return s

def _helper_unitconvert(value):
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

    low = _helper_unitconvert(low)
    high = _helper_unitconvert(high)
    if low is not None and high is not None and low > high:
        raise OutOfOrder(s, low, high)
    return low, high

def get_mimetype(filepath):
    extension = os.path.splitext(filepath)[1].replace('.', '')
    if extension in constants.ADDITIONAL_MIMETYPES:
        return constants.ADDITIONAL_MIMETYPES[extension]
    mimetype = mimetypes.guess_type(filepath)[0]
    if mimetype is not None:
        mimetype = mimetype.split('/')[0]
    return mimetype

def getnow(timestamp=True):
    '''
    Return the current UTC timestamp or datetime object.
    '''
    now = datetime.datetime.now(datetime.timezone.utc)
    if timestamp:
        return now.timestamp()
    return now

def normalize_filepath(filepath):
    '''
    Remove some bad characters.
    '''
    filepath = filepath.replace('/', os.sep)
    filepath = filepath.replace('\\', os.sep)
    filepath = filepath.replace('<', '')
    filepath = filepath.replace('>', '')
    return filepath

def normalize_tagname(tagname):
    '''
    Tag names can only consist of VALID_TAG_CHARS.
    The given tagname is lowercased, gets its spaces and hyphens
    replaced by underscores, and is stripped of any not-whitelisted
    characters.
    '''
    tagname = tagname.lower()
    tagname = tagname.replace('-', '_')
    tagname = tagname.replace(' ', '_')
    tagname = (c for c in tagname if c in constants.VALID_TAG_CHARS)
    tagname = ''.join(tagname)

    if len(tagname) < constants.MIN_TAG_NAME_LENGTH:
        raise TagTooShort(tagname)
    if len(tagname) > constants.MAX_TAG_NAME_LENGTH:
        raise TagTooLong(tagname)

    return tagname

def operate(operand_stack, operator_stack):
    #print('before:', operand_stack, operator_stack)
    operator = operator_stack.pop()
    if operator == 'NOT':
        operand = operand_stack.pop()
        value = operand ^ 1
    else:
        right = operand_stack.pop()
        left = operand_stack.pop()
        if operator == 'OR':
            value = left | right
        elif operator == 'AND':
            value = left & right
        else:
            raise ValueError('werwer')
    operand_stack.append(value)
    #print('after:', operand_stack, operator_stack)

def raise_no_such_thing(exception_class, thing_id=None, thing_name=None, comment=''):
    if thing_id is not None:
        message = 'ID: %s. %s' % (thing_id, comment)
    elif thing_name is not None:
        message = 'Name: %s. %s' % (thing_name, comment)
    else:
        message = ''
    raise exception_class(message)

def searchfilter_expression(photo_tags, expression, frozen_children, warn_bad_tags):
    photo_tags = set(tag.name for tag in photo_tags)
    operator_stack = collections.deque()
    operand_stack = collections.deque()

    expression = expression.replace('-', ' ')
    expression = expression.strip()
    if not expression:
        return False
    expression = expression.replace('(', ' ( ')
    expression = expression.replace(')', ' ) ')
    while '  ' in expression:
        expression = expression.replace('  ', ' ')
    tokens = [token for token in expression.split(' ') if token]
    has_operand = False
    can_shortcircuit = False

    for token in tokens:
        #print(token, end=' ', flush=True)
        if can_shortcircuit and token != ')':
            continue

        if token not in constants.EXPRESSION_OPERATORS:
            try:
                token = normalize_tagname(token)
                value = any(option in photo_tags for option in frozen_children[token])
            except KeyError:
                if warn_bad_tags:
                    warnings.warn(constants.NO_SUCH_TAG.format(tag=token))
                else:
                    raise NoSuchTag(token)
                return False
            operand_stack.append(value)
            if has_operand:
                operate(operand_stack, operator_stack)
            has_operand = True
            continue

        if token == '(':
            has_operand = False

        if token == ')':
            if not can_shortcircuit:
                while operator_stack[-1] != '(':
                    operate(operand_stack, operator_stack)
                operator_stack.pop()
            has_operand = True
            continue

        can_shortcircuit = (
            has_operand and
            (
                (operand_stack[-1] == 0 and token == 'AND') or
                (operand_stack[-1] == 1 and token == 'OR')
            )
        )
        if can_shortcircuit:
            if operator_stack and operator_stack[-1] == '(':
                operator_stack.pop()
            continue

        operator_stack.append(token)
        #time.sleep(.3)
    #print()
    while len(operand_stack) > 1 or len(operator_stack) > 0:
        operate(operand_stack, operator_stack)
    #print(operand_stack)
    return operand_stack.pop()

def searchfilter_must_may_forbid(photo_tags, tag_musts, tag_mays, tag_forbids, frozen_children):
    if tag_musts and not all(any(option in photo_tags for option in frozen_children[must]) for must in tag_musts):
        #print('Failed musts')
        return False

    if tag_mays and not any(option in photo_tags for may in tag_mays for option in frozen_children[may]):
        #print('Failed mays')
        return False

    if tag_forbids and any(option in photo_tags for forbid in tag_forbids for option in frozen_children[forbid]):
        #print('Failed forbids')
        return False

    return True

def select(sql, query, bindings=None):
    bindings = bindings or []
    cursor = sql.cursor()
    cursor.execute(query, bindings)
    while True:
        fetch = cursor.fetchone()
        if fetch is None:
            break
        yield fetch

def tag_export_easybake(tags, depth=0):
    lines = []
    for tag in tags:
        if not hasattr(tag, 'string'):
            tag.string = tag.name
        children = tag.children()
        synonyms = tag.synonyms()
        lines.append(tag.string)

        for synonym in synonyms:
            synonym = tag.string + '+' + synonym
            lines.append(synonym)

        for child in children:
            child.string = tag.string + '.' + child.name
        child_bake = tag_export_easybake(children, depth=depth+1)
        if child_bake != '':
            lines.append(child_bake)

    lines = '\n'.join(lines)
    return lines

def tag_export_json(tags):
    def fill(tag):
        children = {child.name:fill(child) for child in tag.children()}
        return children
    result = {}
    for tag in tags:
        result[tag.name] = fill(tag)
    return result

def tag_export_qualname_map(tags):
    lines = tag_export_easybake(tags)
    lines = lines.split('\n')
    lines = [line for line in lines if line]
    qualname_map = {}
    for line in lines:
        key = line.split('.')[-1].split('+')[-1]
        value = line.split('+')[0]
        qualname_map[key] = value
    return qualname_map

def tag_export_stdout(tags, depth=0):
    for tag in tags:
        children = tag.children()
        synonyms = tag.synonyms()

        pad = '    ' * depth
        synpad = '    ' * (depth + 1)
        print(pad + str(tag))

        for synonym in synonyms:
            print(synpad + synonym)

        tag_export_stdout(children, depth=depth+1)

        if tag.parent() is None:
            print()

@decorators.time_me
def tag_export_totally_flat(tags):
    result = {}
    for tag in tags:
        for child in tag.walk_children():
            children = list(child.walk_children())
            result[child] = children
            for synonym in child.synonyms():
                result[synonym] = children
    return result

####################################################################################################
####################################################################################################

class CantSynonymSelf(Exception):
    pass

class NoSuchAlbum(Exception):
    pass

class NoSuchGroup(Exception):
    pass

class NoSuchPhoto(Exception):
    pass

class NoSuchSynonym(Exception):
    pass

class NoSuchTag(Exception):
    pass


class PhotoExists(Exception):
    pass

class TagExists(Exception):
    pass

class GroupExists(Exception):
    pass


class TagTooLong(Exception):
    pass

class TagTooShort(Exception):
    pass

class XORException(Exception):
    pass

class OutOfOrder(Exception):
    pass


####################################################################################################
####################################################################################################


class PDBAlbumMixin:
    def get_album(self, id):
        return self.get_thing_by_id('album', id)

    def get_album_by_path(self, filepath):
        '''
        Return the album with the `associated_directory` of this value, NOT case-sensitive.
        '''
        filepath = os.path.abspath(filepath)
        self.cur.execute('SELECT * FROM albums WHERE associated_directory == ?', [filepath])
        f = self.cur.fetchone()
        if f is None:
            raise NoSuchAlbum(filepath)
        return self.get_album(f[SQL_ALBUM['id']])

    def get_albums(self):
        yield from self.get_things(thing_type='album')

    def new_album(self,
            associated_directory=None,
            commit=True,
            description=None,
            photos=None,
            title=None,
        ):
        '''
        Create a new album. Photos can be added now or later.
        '''
        # Albums share the tag table's ID counter
        albumid = self.generate_id('tags')
        title = title or ''
        description = description or ''
        if associated_directory is not None:
            associated_directory = os.path.abspath(associated_directory)

        if not isinstance(title, str):
            raise TypeError('Title must be string, not %s' % type(title))

        if not isinstance(description, str):
            raise TypeError('Description must be string, not %s' % type(description))

        data = [None] * len(SQL_ALBUM_COLUMNS)
        data[SQL_ALBUM['id']] = albumid
        data[SQL_ALBUM['title']] = title
        data[SQL_ALBUM['description']] = description
        data[SQL_ALBUM['associated_directory']] = associated_directory

        self.cur.execute('INSERT INTO albums VALUES(?, ?, ?, ?)', data)
        album = Album(self, data)
        if photos:
            for photo in photos:
                photo = self.get_photo(photo)
                album.add_photo(photo, commit=False)

        if commit:
            log.debug('Committing - new Album')
            self.commit()
        return album


class PDBPhotoMixin:
    def get_photo(self, photoid):
        return self.get_thing_by_id('photo', photoid)

    def get_photo_by_path(self, filepath):
        filepath = os.path.abspath(filepath)
        self.cur.execute('SELECT * FROM photos WHERE filepath == ?', [filepath])
        fetch = self.cur.fetchone()
        if fetch is None:
            raise_no_such_thing(NoSuchPhoto, thing_name=filepath)
        photo = Photo(self, fetch)
        return photo

    def get_photos_by_recent(self, count=None):
        '''
        Yield photo objects in order of creation time.
        '''
        if count is not None and count <= 0:
            return
        # We're going to use a second cursor because the first one may
        # get used for something else, deactivating this query.
        temp_cur = self.sql.cursor()
        temp_cur.execute('SELECT * FROM photos ORDER BY created DESC')
        while True:
            f = temp_cur.fetchone()
            if f is None:
                break
            photo = Photo(self, f)

            yield photo

            if count is None:
                continue
            count -= 1
            if count <= 0:
                break

    def purge_deleted_files(self):
        '''
        Remove Photo entries if their corresponding file is no longer found.
        '''
        photos = self.get_photos_by_recent()
        for photo in photos:
            if os.path.exists(photo.real_filepath):
                continue
            photo.delete()

    def purge_empty_albums(self):
        albums = self.get_albums()
        for album in albums:
            if album.children() or album.photos():
                continue
            album.delete()

    def new_photo(
            self,
            filename,
            allow_duplicates=False,
            commit=True,
            do_metadata=True,
            do_thumbnail=True,
            tags=None,
        ):
        '''
        Given a filepath, determine its attributes and create a new Photo object in the
        database. Tags may be applied now or later.

        If `allow_duplicates` is False, we will first check the database for any files
        with the same path and raise PhotoExists if found.

        Returns the Photo object.
        '''
        filename = os.path.abspath(filename)
        assert os.path.isfile(filename)
        if not allow_duplicates:
            try:
                existing = self.get_photo_by_path(filename)
            except NoSuchPhoto:
                pass
            else:
                exc = PhotoExists(filename, existing)
                exc.photo = existing
                raise exc

        extension = os.path.splitext(filename)[1]
        extension = extension.replace('.', '')
        extension = normalize_tagname(extension)
        created = int(getnow())
        photoid = self.generate_id('photos')

        data = [None] * len(SQL_PHOTO_COLUMNS)
        data[SQL_PHOTO['id']] = photoid
        data[SQL_PHOTO['filepath']] = filename
        data[SQL_PHOTO['override_filename']] = None
        data[SQL_PHOTO['extension']] = extension
        data[SQL_PHOTO['created']] = created
        # These will be filled in just a moment
        data[SQL_PHOTO['bytes']] = None
        data[SQL_PHOTO['width']] = None
        data[SQL_PHOTO['height']] = None
        data[SQL_PHOTO['area']] = None
        data[SQL_PHOTO['ratio']] = None
        data[SQL_PHOTO['duration']] = None
        data[SQL_PHOTO['thumbnail']] = None

        self.cur.execute('INSERT INTO photos VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', data)
        photo = Photo(self, data)
        if do_metadata:
            photo.reload_metadata(commit=False)
        if do_thumbnail:
            photo.generate_thumbnail(commit=False)

        tags = tags or []
        tags = [self.get_tag(tag) for tag in tags]
        for tag in tags:
            photo.add_tag(tag, commit=False)

        if commit:
            log.debug('Commiting - new_photo')
        return photo

    def search(
            self,
            area=None,
            width=None,
            height=None,
            ratio=None,
            bytes=None,
            duration=None,

            created=None,
            extension=None,
            extension_not=None,
            filename=None,
            has_tags=None,
            mimetype=None,
            tag_musts=None,
            tag_mays=None,
            tag_forbids=None,
            tag_expression=None,

            warn_bad_tags=False,
            limit=None,
            offset=None,
            orderby=None,
        ):
        '''
        PHOTO PROPERTISE
        area, width, height, ratio, bytes, duration:
            A hyphen_range string representing min and max. Or just a number for lower bound.

        TAGS AND FILTERS
        created:
            A hyphen_range string respresenting min and max. Or just a number for lower bound.

        extension:
            A string or list of strings of acceptable file extensions.

        extension_not:
            A string or list of strings of unacceptable file extensions.

        filename:
            A string or list of strings which will be split into words. The file's basename
            must include every word, NOT case-sensitive.

        has_tags:
            If True, require that the Photo has >=1 tag.
            If False, require that the Photo has no tags.
            If None, not considered.

        mimetype:
            A string or list of strings of acceptable mimetypes. 'image', 'video', ...

        tag_musts:
            A list of tag names or Tag objects.
            Photos MUST have ALL tags in this list.

        tag_mays:
            A list of tag names or Tag objects.
            Photos MUST have AT LEAST ONE tag in this list.

        tag_forbids:
            A list of tag names or Tag objects.
            Photos MUST NOT have ANY tag in the list.

        tag_expression:
            A string like 'family AND (animals OR vacation)' to filter by.
            Can NOT be used with the must, may, forbid style search.

        QUERY OPTIONS
        warn_bad_tags:
            If a tag is not found, issue a warning but continue the search.
            Otherwise, a NoSuchTag exception would be raised.

        limit:
            The maximum number of *successful* results to yield.

        offset:
            How many *successful* results to skip before we start yielding.

        orderby:
            A list of strings like ['ratio DESC', 'created ASC'] to sort
            and subsort the results.
            Descending is assumed if not provided.
        '''
        start_time = time.time()
        maximums = {}
        minimums = {}
        _helper_minmax('area', area, minimums, maximums)
        _helper_minmax('created', created, minimums, maximums)
        _helper_minmax('width', width, minimums, maximums)
        _helper_minmax('height', height, minimums, maximums)
        _helper_minmax('ratio', ratio, minimums, maximums)
        _helper_minmax('bytes', bytes, minimums, maximums)
        _helper_minmax('duration', duration, minimums, maximums)
        orderby = orderby or []

        extension = _helper_extension(extension)
        extension_not = _helper_extension(extension_not)
        mimetype = _helper_extension(mimetype)

        if filename is not None:
            if not isinstance(filename, str):
                filename = ' '.join(filename)
            filename = set(term.lower() for term in filename.strip().split(' '))

        if (tag_musts or tag_mays or tag_forbids) and tag_expression:
            raise XORException('Expression filter cannot be used with musts, mays, forbids')

        tag_musts = _helper_setify(self, tag_musts, warn_bad_tags=warn_bad_tags)
        tag_mays = _helper_setify(self, tag_mays, warn_bad_tags=warn_bad_tags)
        tag_forbids = _helper_setify(self, tag_forbids, warn_bad_tags=warn_bad_tags)

        query = 'SELECT * FROM photos'
        orderby = [_helper_orderby(o) for o in orderby]
        orderby = [o for o in orderby if o]
        if orderby:
            whereable_columns = [o[0] for o in orderby if o[0] != 'RANDOM()']
            whereable_columns = [column + ' IS NOT NULL' for column in whereable_columns]
            if whereable_columns:
                query += ' WHERE '
                query += ' AND '.join(whereable_columns)
            orderby = [' '.join(o) for o in orderby]
            orderby = ', '.join(orderby)
            query += ' ORDER BY %s' % orderby
        else:
            query += ' ORDER BY created DESC'
        print(query)
        generator = select(self.sql, query)

        # To lighten the amount of database reading here, `frozen_children` is a dict where
        # EVERY tag in the db is a key, and the value is a list of ALL ITS NESTED CHILDREN.
        # This representation is memory inefficient, but it is faster than repeated
        # database lookups
        is_must_may_forbid = bool(tag_musts or tag_mays or tag_forbids)
        is_tagsearch = is_must_may_forbid or tag_expression
        if is_tagsearch:
            if self._cached_frozen_children:
                frozen_children = self._cached_frozen_children
            else:
                frozen_children = self.export_tags(tag_export_totally_flat)
                self._cached_frozen_children = frozen_children
        photos_received = 0

        for fetch in generator:
            photo = Photo(self, fetch)

            if extension and photo.extension not in extension:
                #print('Failed extension')
                continue

            if extension_not and photo.extension in extension_not:
                #print('Failed extension_not')
                continue

            if mimetype and photo.mimetype() not in mimetype:
                #print('Failed mimetype')
                continue

            if filename and not _helper_filenamefilter(subject=photo.basename, terms=filename):
                #print('Failed filename')
                continue

            if any(not fetch[SQL_PHOTO[key]] or fetch[SQL_PHOTO[key]] > value for (key, value) in maximums.items()):
                #print('Failed maximums')
                continue

            if any(not fetch[SQL_PHOTO[key]] or fetch[SQL_PHOTO[key]] < value for (key, value) in minimums.items()):
                #print('Failed minimums')
                continue

            if (has_tags is not None) or is_tagsearch:
                photo_tags = photo.tags()

                if has_tags is False and len(photo_tags) > 0:
                    continue

                if has_tags is True and len(photo_tags) == 0:
                    continue

                photo_tags = set(photo_tags)

                if tag_expression:
                    if not searchfilter_expression(photo_tags, tag_expression, frozen_children, warn_bad_tags):
                        continue
                elif is_must_may_forbid:
                    if not searchfilter_must_may_forbid(photo_tags, tag_musts, tag_mays, tag_forbids, frozen_children):
                        continue

            if offset is not None and offset > 0:
                offset -= 1
                continue

            if limit is not None and photos_received >= limit:
                break

            photos_received += 1
            yield photo

        end_time = time.time()
        print(end_time - start_time)


class PDBTagMixin:
    def export_tags(self, exporter=tag_export_stdout, specific_tag=None):
        '''
        Send the top-level tags to function `exporter`.
        Strings 'start' and 'stop' are sent before and after the tags are sent.
        Recursion is to be handled by the exporter.
        '''
        if specific_tag is None:
            items = list(self.get_tags())
            items = [item for item in items if item.parent() is None]
            items.sort(key=lambda x: x.name)
        else:
            items = [self.get_tag(specific_tag)]
        return exporter(items)

    def get_tag(self, name=None, id=None):
        '''
        Redirect to get_tag_by_id or get_tag_by_name after xor-checking the parameters.
        '''
        if not helpers.is_xor(id, name):
            raise XORException('One and only one of `id`, `name` can be passed.')

        if id is not None:
            return self.get_tag_by_id(id)
        elif name is not None:
            return self.get_tag_by_name(name)
        else:
            raise_no_such_thing(NoSuchTag, thing_id=id, thing_name=name)

    def get_tag_by_id(self, id):
        return self.get_thing_by_id('tag', thing_id=id)

    def get_tag_by_name(self, tagname):
        if isinstance(tagname, Tag):
            tagname = tagname.name

        tagname = tagname.split('.')[-1].split('+')[0]
        tagname = normalize_tagname(tagname)

        while True:
            # Return if it's a toplevel, or resolve the synonym and try that.
            self.cur.execute('SELECT * FROM tags WHERE name == ?', [tagname])
            fetch = self.cur.fetchone()
            if fetch is not None:
                return Tag(self, fetch)

            self.cur.execute('SELECT * FROM tag_synonyms WHERE name == ?', [tagname])
            fetch = self.cur.fetchone()
            if fetch is None:
                # was not a top tag or synonym
                raise_no_such_thing(NoSuchTag, thing_name=tagname)
            tagname = fetch[SQL_SYN['master']]

    def get_tags(self):
        yield from self.get_things(thing_type='tag')

    def new_tag(self, tagname, commit=True):
        '''
        Register a new tag in and return the Tag object.
        '''
        tagname = normalize_tagname(tagname)
        try:
            self.get_tag_by_name(tagname)
        except NoSuchTag:
            pass
        else:
            raise TagExists(tagname)

        tagid = self.generate_id('tags')
        self._cached_frozen_children = None
        self.cur.execute('INSERT INTO tags VALUES(?, ?)', [tagid, tagname])
        if commit:
            log.debug('Commiting - new_tag')
            self.commit()
        tag = Tag(self, [tagid, tagname])
        return tag


class PhotoDB(PDBAlbumMixin, PDBPhotoMixin, PDBTagMixin):
    '''
    This class represents an SQLite3 database containing the following tables:

    albums:
        Rows represent the inclusion of a photo in an album

    photos:
        Rows represent image files on the local disk.
        Entries contain a unique ID, the image's filepath, and metadata
        like dimensions and filesize.

    tags:
        Rows represent labels, which can be applied to an arbitrary number of
        photos. Photos may be selected by which tags they contain.
        Entries contain a unique ID and a name.

    photo_tag_rel:
        Rows represent a Photo's ownership of a particular Tag.

    tag_synonyms:
        Rows represent relationships between two tag names, so that they both
        resolve to the same Tag object when selected. Entries contain the
        subordinate name and master name.
        The master name MUST also exist in the `tags` table.
        If a new synonym is created referring to another synoym, the master name
        will be resolved and used instead, so a synonym never points to another synonym.
        Tag objects will ALWAYS represent the master tag.

        Note that the entries in this table do not contain ID numbers.
        The rationale here is that "coco" is a synonym for "chocolate" regardless
        of the "chocolate" tag's ID, and that if a tag is renamed, its synonyms
        do not necessarily follow.
        The `rename` method of Tag objects includes a parameter
        `apply_to_synonyms` if you do want them to follow.
    '''
    def __init__(
            self,
            databasename=constants.DEFAULT_DBNAME,
            thumbnail_folder=constants.DEFAULT_THUMBDIR,
            id_length=constants.DEFAULT_ID_LENGTH,
        ):
        self.databasename = databasename
        self.database_abspath = os.path.abspath(databasename)
        existing_database = os.path.exists(databasename)
        self.sql = sqlite3.connect(databasename)
        self.cur = self.sql.cursor()
        if existing_database:
            self.cur.execute('PRAGMA user_version')
            existing_version = self.cur.fetchone()[0]
            if existing_version != DATABASE_VERSION:
                message = constants.ERROR_DATABASE_OUTOFDATE
                message = message.format(current=existing_version, new=DATABASE_VERSION)
                log.critical(message)
                raise SystemExit

        statements = DB_INIT.split(';')
        for statement in statements:
            self.cur.execute(statement)

        self.thumbnail_folder = os.path.abspath(thumbnail_folder)
        os.makedirs(thumbnail_folder, exist_ok=True)

        self.id_length = id_length

        self.on_commit_queue = []
        self._cached_frozen_children = None

    def __repr__(self):
        return 'PhotoDB(databasename={dbname})'.format(dbname=repr(self.databasename))

    def _uncache(self):
        self._cached_frozen_children = None

    def commit(self):
        while self.on_commit_queue:
            task = self.on_commit_queue.pop()
            print(task)
            args = task.get('args', [])
            kwargs = task.get('kwargs', {})
            task['action'](*args, **kwargs)
        self.sql.commit()

    def digest_directory(self, directory, exclude_directories=None, exclude_filenames=None, commit=True):
        '''
        Create an album, and add the directory's contents to it recursively.

        If a Photo object already exists for a file, it will be added to the correct album.
        '''
        if not os.path.isdir(directory):
            raise ValueError('Not a directory: %s' % directory)
        if exclude_directories is None:
            exclude_directories = constants.DEFAULT_DIGEST_EXCLUDE_DIRS
        if exclude_filenames is None:
            exclude_filenames = constants.DEFAULT_DIGEST_EXCLUDE_FILES

        directory = spinal.str_to_fp(directory)
        directory.correct_case()
        generator = spinal.walk_generator(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            yield_style='nested',
        )
        try:
            album = self.get_album_by_path(directory.absolute_path)
        except NoSuchAlbum:
            album = self.new_album(
                associated_directory=directory.absolute_path,
                commit=False,
                title=directory.basename,
            )

        albums = {directory.absolute_path: album}
        for (current_location, directories, files) in generator:
            current_album = albums.get(current_location.absolute_path, None)
            if current_album is None:
                try:
                    current_album = self.get_album_by_path(current_location.absolute_path)
                except NoSuchAlbum:
                    current_album = self.new_album(
                        associated_directory=current_location.absolute_path,
                        commit=False,
                        title=current_location.basename,
                    )
                    print('Created %s' % current_album.title)
                albums[current_location.absolute_path] = current_album
                parent = albums[current_location.parent.absolute_path]
                try:
                    parent.add(current_album, commit=False)
                except GroupExists:
                    pass
                #print('Added to %s' % parent.title)
            for filepath in files:
                try:
                    photo = self.new_photo(filepath.absolute_path, commit=False)
                except PhotoExists as e:
                    photo = e.photo
                current_album.add_photo(photo, commit=False)

        if commit:
            log.debug('Commiting - digest')
            self.commit()
        return album

    def digest_new_files(
            self,
            directory,
            exclude_directories=None,
            exclude_filenames=None,
            recurse=False,
            commit=True
        ):
        '''
        Walk the directory and add new files as Photos.
        Does NOT create or modify any albums like `digest_directory` does.
        '''
        if not os.path.isdir(directory):
            raise ValueError('Not a directory: %s' % directory)
        if exclude_directories is None:
            exclude_directories = constants.DEFAULT_DIGEST_EXCLUDE_DIRS
        if exclude_filenames is None:
            exclude_filenames = constants.DEFAULT_DIGEST_EXCLUDE_FILES

        directory = spinal.str_to_fp(directory)
        generator = spinal.walk_generator(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            recurse=recurse,
            yield_style='flat',
        )
        for filepath in generator:
            filepath = filepath.absolute_path
            try:
                photo = self.get_photo_by_path(filepath)
            except NoSuchPhoto:
                pass
            else:
                continue
            photo = self.new_photo(filepath, commit=False)
        if commit:
            log.debug('Committing - digest_new_files')
            self.commit()


    def easybake(self, string):
        '''
        Easily create tags, groups, and synonyms with a string like
        "group1.group2.tag+synonym"
        "family.parents.dad+father"
        etc
        '''
        output_notes = []
        def create_or_get(name):
            print('cog', name)
            try:
                item = self.get_tag(name)
                note = ('existing_tag', item.qualified_name())
            except NoSuchTag:
                item = self.new_tag(name)
                note = ('new_tag', item.qualified_name())
            output_notes.append(note)
            return item

        string = string.strip()
        string = string.strip('.+=')
        if string == '':
            return

        if '=' in string and '+' in string:
            raise ValueError('Cannot rename and assign snynonym at once')

        rename_parts = string.split('=')
        if len(rename_parts) == 2:
            (string, rename_to) = rename_parts
        elif len(rename_parts) == 1:
            string = rename_parts[0]
            rename_to = None
        else:
            raise ValueError('Too many equals signs')

        create_parts = string.split('+')
        if len(create_parts) == 2:
            (tag, synonym) = create_parts
        elif len(create_parts) == 1:
            tag = create_parts[0]
            synonym = None
        else:
            raise ValueError('Too many plus signs')

        if not tag:
            return None

        if rename_to:
            tag = self.get_tag(tag)
            note = ('rename', '%s=%s' % (tag.name, rename_to))
            tag.rename(rename_to)
            output_notes.append(note)
        else:
            tag_parts = tag.split('.')
            tags = [create_or_get(t) for t in tag_parts]
            for (higher, lower) in zip(tags, tags[1:]):
                try:
                    lower.join_group(higher)
                    note = ('join_group', '%s.%s' % (higher.name, lower.name))
                    output_notes.append(note)
                except GroupExists:
                    pass
            tag = tags[-1]

        if synonym:
            try:
                tag.add_synonym(synonym)
                note = ('new_synonym', '%s+%s' % (tag.name, synonym))
                output_notes.append(note)
                print('New syn %s' % synonym)
            except TagExists:
                pass
        return output_notes

    def generate_id(self, table):
        '''
        Create a new ID number that is unique to the given table.
        Note that this method does not commit the database. We'll wait for that
        to happen in whoever is calling us, so we know the ID is actually used.
        '''
        table = table.lower()
        if table not in ['photos', 'tags', 'groups']:
            raise ValueError('Invalid table requested: %s.', table)

        do_insert = False

        self.cur.execute('SELECT * FROM id_numbers WHERE tab == ?', [table])
        fetch = self.cur.fetchone()
        if fetch is None:
            # Register new value
            new_id_int = 1
            do_insert = True
        else:
            # Use database value
            new_id_int = int(fetch[SQL_LASTID['last_id']]) + 1

        new_id = str(new_id_int).rjust(self.id_length, '0')
        if do_insert:
            self.cur.execute('INSERT INTO id_numbers VALUES(?, ?)', [table, new_id])
        else:
            self.cur.execute('UPDATE id_numbers SET last_id = ? WHERE tab == ?', [new_id, table])
        return new_id

    def get_thing_by_id(self, thing_type, thing_id):
        thing_map = self.thing_map(thing_type)

        if isinstance(thing_id, thing_map['class']):
            thing_id = thing_id.id

        query = 'SELECT * FROM %s WHERE id == ?' % thing_map['table']
        self.cur.execute(query, [thing_id])
        thing = self.cur.fetchone()
        if thing is None:
            return raise_no_such_thing(thing_map['exception'], thing_id=thing_id)
        thing = thing_map['class'](self, thing)
        return thing

    def get_things(self, thing_type, orderby=None):
        thing_map = self.thing_map(thing_type)

        if orderby:
            self.cur.execute('SELECT * FROM %s ORDER BY %s' % (thing_map['table'], orderby))
        else:
            self.cur.execute('SELECT * FROM %s' % thing_map['table'])

        things = self.cur.fetchall()
        for thing in things:
            thing = thing_map['class'](self, row_tuple=thing)
            yield thing

    def thing_map(self, thing_type):
        return {
            'album':
            {
                'class': Album,
                'exception': NoSuchAlbum,
                'table': 'albums',
            },
            'tag':
            {
                'class': Tag,
                'exception': NoSuchTag,
                'table': 'tags',
            },
            'photo':
            {
                'class': Photo,
                'exception': NoSuchPhoto,
                'table': 'photos',
            },
        }[thing_type]

####################################################################################################
####################################################################################################


class ObjectBase:
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.id == other.id

    def __format__(self, formcode):
        if formcode == 'r':
            return repr(self)
        else:
            return str(self)

    def __hash__(self):
        return hash(self.id)


class GroupableMixin:
    def add(self, member, commit=True):
        '''
        Add a Tag object to this group.

        If that object is already a member of another group, a GroupExists is raised.
        '''
        if not isinstance(member, type(self)):
            raise TypeError('Member must be of type %s' % type(self))

        self.photodb.cur.execute('SELECT * FROM tag_group_rel WHERE memberid == ?', [member.id])
        fetch = self.photodb.cur.fetchone()
        if fetch is not None:
            if fetch[SQL_TAGGROUP['parentid']] == self.id:
                that_group = self
            else:
                that_group = self.group_getter(id=fetch[SQL_TAGGROUP['parentid']])
            raise GroupExists('%s already in group %s' % (member.name, that_group.name))

        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute('INSERT INTO tag_group_rel VALUES(?, ?)', [self.id, member.id])
        if commit:
            log.debug('Commiting - add to group')
            self.photodb.commit()

    def children(self):
        self.photodb.cur.execute('SELECT * FROM tag_group_rel WHERE parentid == ?', [self.id])
        fetch = self.photodb.cur.fetchall()
        results = []
        for f in fetch:
            memberid = f[SQL_TAGGROUP['memberid']]
            child = self.group_getter(id=memberid)
            results.append(child)
        if isinstance(self, Tag):
            results.sort(key=lambda x: x.name)
        else:
            results.sort(key=lambda x: x.id)
        return results

    def delete(self, delete_children=False, commit=True):
        '''
        Delete a tag and its relationship with photos, synonyms, and tag groups.

        delete_children:
            If True, all children will be deleted.
            Otherwise they'll just be raised up one level.
        '''
        self.photodb._cached_frozen_children = None
        if delete_children:
            for child in self.children():
                child.delete(delete_children=delete_children, commit=False)
        else:
            # Lift children
            parent = self.parent()
            if parent is None:
                # Since this group was a root, children become roots by removing the row.
                self.photodb.cur.execute('DELETE FROM tag_group_rel WHERE parentid == ?', [self.id])
            else:
                # Since this group was a child, its parent adopts all its children.
                self.photodb.cur.execute(
                    'UPDATE tag_group_rel SET parentid == ? WHERE parentid == ?',
                    [parent.id, self.id]
                )
        # Note that this part comes after the deletion of children to prevent issues of recursion.
        self.photodb.cur.execute('DELETE FROM tag_group_rel WHERE memberid == ?', [self.id])
        if commit:
            log.debug('Committing - delete tag')
            self.photodb.commit()

    def parent(self):
        '''
        Return the Tag object of which this is a member, or None.
        '''
        self.photodb.cur.execute('SELECT * FROM tag_group_rel WHERE memberid == ?', [self.id])
        fetch = self.photodb.cur.fetchone()
        if fetch is None:
            return None

        parentid = fetch[SQL_TAGGROUP['parentid']]
        return self.group_getter(id=parentid)

    def join_group(self, group, commit=True):
        '''
        Leave the current group, then call `group.add(self)`.
        '''
        if isinstance(group, str):
            group = self.photodb.get_tag(group)
        if not isinstance(group, type(self)):
            raise TypeError('Group must also be %s' % type(self))

        if self == group:
            raise ValueError('Cant join self')

        self.leave_group(commit=commit)
        group.add(self, commit=commit)

    def leave_group(self, commit=True):
        '''
        Leave the current group and become independent.
        '''
        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute('DELETE FROM tag_group_rel WHERE memberid == ?', [self.id])
        if commit:
            log.debug('Committing - leave group')
            self.photodb.commit()

    def walk_children(self):
        yield self
        for child in self.children():
            yield from child.walk_children()

    def walk_parents(self):
        parent = self.parent()
        while parent is not None:
            yield parent
            parent = parent.parent()


class Album(ObjectBase, GroupableMixin):
    def __init__(self, photodb, row_tuple):
        self.photodb = photodb
        self.id = row_tuple[SQL_ALBUM['id']]
        self.title = row_tuple[SQL_ALBUM['title']]
        self.name = 'Album %s' % self.id
        self.description = row_tuple[SQL_ALBUM['description']]
        self.group_getter = self.photodb.get_album

    def __repr__(self):
        return 'Album:{id}'.format(id=self.id)

    def add_photo(self, photo, commit=True):
        if self.photodb != photo.photodb:
            raise ValueError('Not the same PhotoDB')
        if self.has_photo(photo):
            return
        self.photodb.cur.execute('INSERT INTO album_photo_rel VALUES(?, ?)', [self.id, photo.id])
        if commit:
            log.debug('Committing - add photo to album')
            self.photodb.commit()

    def add_tag_to_all(self, tag, nested_children=True):
        tag = self.photodb.get_tag(tag)
        if nested_children:
            photos = self.walk_photos()
        else:
            photos = self.photos()
        for photo in photos:
            photo.add_tag(tag)

    def delete(self, delete_children=False, commit=True):
        log.debug('Deleting album {album:r}'.format(album=self))
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        self.photodb.cur.execute('DELETE FROM albums WHERE id == ?', [self.id])
        self.photodb.cur.execute('DELETE FROM album_photo_rel WHERE albumid == ?', [self.id])
        if commit:
            log.debug('Committing - delete album')
            self.photodb.commit()

    def edit(self, title=None, description=None, commit=True):
        if title is None:
            title = self.title
        if description is None:
            description = self.description
        self.photodb.cur.execute(
            'UPDATE albums SET title=?, description=? WHERE id == ?',
            [title, description, self.id]
        )
        self.title = title
        self.description = description
        if commit:
            log.debug('Committing - edit album')
            self.photodb.commit()

    def has_photo(self, photo):
        if not isinstance(photo, Photo):
            raise TypeError('Must be a %s' % Photo)
        self.photodb.cur.execute(
            'SELECT * FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        return self.photodb.cur.fetchone() is not None

    def photos(self):
        photos = []
        generator = select(
            self.photodb.sql,
            'SELECT * FROM album_photo_rel WHERE albumid == ?',
            [self.id]
        )
        for photo in generator:
            photoid = photo[SQL_ALBUMPHOTO['photoid']]
            photo = self.photodb.get_photo(photoid)
            photos.append(photo)
        photos.sort(key=lambda x: x.basename.lower())
        return photos

    def remove_photo(self, photo, commit=True):
        if not self.has_photo(photo):
            return
        self.photodb.cur.execute(
            'DELETE FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        if commit:
            self.photodb.commit()

    def walk_photos(self):
        yield from self.photos()
        children = self.walk_children()
        # The first yield is itself
        next(children)
        for child in children:
            print(child)
            yield from child.walk_photos()

class Photo(ObjectBase):
    '''
    A PhotoDB entry containing information about an image file.
    Photo objects cannot exist without a corresponding PhotoDB object, because
    Photos are not the actual image data, just the database entry.
    '''
    def __init__(self, photodb, row_tuple):
        self.photodb = photodb
        self.id = row_tuple[SQL_PHOTO['id']]
        self.real_filepath = row_tuple[SQL_PHOTO['filepath']]
        self.real_filepath = normalize_filepath(self.real_filepath)
        self.filepath = row_tuple[SQL_PHOTO['override_filename']] or self.real_filepath
        self.basename = row_tuple[SQL_PHOTO['override_filename']] or os.path.basename(self.real_filepath)
        self.extension = row_tuple[SQL_PHOTO['extension']]
        self.width = row_tuple[SQL_PHOTO['width']]
        self.height = row_tuple[SQL_PHOTO['height']]
        self.ratio = row_tuple[SQL_PHOTO['ratio']]
        self.area = row_tuple[SQL_PHOTO['area']]
        self.bytes = row_tuple[SQL_PHOTO['bytes']]
        self.duration = row_tuple[SQL_PHOTO['duration']]
        self.created = row_tuple[SQL_PHOTO['created']]
        self.thumbnail = row_tuple[SQL_PHOTO['thumbnail']]

    def __reinit__(self):
        self.photodb.cur.execute('SELECT * FROM photos WHERE id == ?', [self.id])
        row = self.photodb.cur.fetchone()
        self.__init__(self.photodb, row)

    def __repr__(self):
        return 'Photo:{id}'.format(id=self.id)

    def add_tag(self, tag, commit=True):
        tag = self.photodb.get_tag(tag)

        if self.has_tag(tag, check_children=False):
            return

        # If the tag is above one we already have, keep our current one.
        existing = self.has_tag(tag, check_children=True)
        if existing:
            log.debug('Preferring existing {exi:s} over {tag:s}'.format(exi=existing, tag=tag))
            return

        # If the tag is beneath one we already have, remove our current one
        # in favor of the new, more specific tag.
        for parent in tag.walk_parents():
            if self.has_tag(parent, check_children=False):
                log.debug('Preferring new {tag:s} over {par:s}'.format(tag=tag, par=parent))
                self.remove_tag(parent)


        log.debug('Applying tag {tag:s} to photo {pho:s}'.format(tag=tag, pho=self))
        self.photodb.cur.execute('INSERT INTO photo_tag_rel VALUES(?, ?)', [self.id, tag.id])
        if commit:
            log.debug('Committing - add photo tag')
            self.photodb.commit()

    def albums(self):
        '''
        Return the albums of which this photo is a member.
        '''
        self.photodb.cur.execute('SELECT albumid FROM album_photo_rel WHERE photoid == ?', [self.id])
        fetch = self.photodb.cur.fetchall()
        albums = [self.photodb.get_album(f[0]) for f in fetch]
        return albums

    def bytestring(self):
        return bytestring.bytestring(self.bytes)

    def copy_tags(self, other_photo):
        for tag in other_photo.tags():
            self.add_tag(tag)

    def delete(self, commit=True):
        '''
        Delete the Photo and its relation to any tags and albums.
        '''
        log.debug('Deleting photo {photo:r}'.format(photo=self))
        self.photodb.cur.execute('DELETE FROM photos WHERE id == ?', [self.id])
        self.photodb.cur.execute('DELETE FROM photo_tag_rel WHERE photoid == ?', [self.id])
        self.photodb.cur.execute('DELETE FROM album_photo_rel WHERE photoid == ?', [self.id])
        if commit:
            log.debug('Committing - delete photo')
            self.photodb.commit()

    @decorators.time_me
    def generate_thumbnail(self, commit=True, **special):
        '''
        special:
            For videos, you can provide a `timestamp` to take the thumbnail from.
        '''
        hopeful_filepath = self.make_thumbnail_filepath()
        return_filepath = None

        mime = self.mimetype()
        if mime == 'image':
            log.debug('Thumbnailing %s' % self.real_filepath)
            try:
                image = PIL.Image.open(self.real_filepath)
                image = image.convert('RGB')
            except (OSError, ValueError):
                pass
            else:
                (width, height) = image.size
                (new_width, new_height) = helpers.fit_into_bounds(
                    image_width=width,
                    image_height=height,
                    frame_width=constants.THUMBNAIL_WIDTH,
                    frame_height=constants.THUMBNAIL_HEIGHT,
                )
                if new_width < width:
                    image = image.resize((new_width, new_height))
                image.save(hopeful_filepath, quality=50)
                return_filepath = hopeful_filepath

        elif mime == 'video' and ffmpeg:
            #print('video')
            probe = ffmpeg.probe(self.real_filepath)
            try:
                if probe.video:
                    size = helpers.fit_into_bounds(
                        image_width=probe.video.video_width,
                        image_height=probe.video.video_height,
                        frame_width=constants.THUMBNAIL_WIDTH,
                        frame_height=constants.THUMBNAIL_HEIGHT,
                    )
                    size = '%dx%d' % size
                    duration = probe.video.duration
                    if 'timestamp' in special:
                        timestamp = special['timestamp']
                    else:
                        if duration < 3:
                            timestamp = 0
                        else:
                            timestamp = 2
                    ffmpeg.thumbnail(self.real_filepath, time=timestamp, quality=2, size=size, outfile=hopeful_filepath)
            except:
                traceback.print_exc()
            else:
                return_filepath = hopeful_filepath


        if return_filepath != self.thumbnail:
            self.photodb.cur.execute('UPDATE photos SET thumbnail = ? WHERE id == ?', [return_filepath, self.id])
            self.thumbnail = return_filepath

        if commit:
            log.debug('Committing - generate thumbnail')
            self.photodb.commit()

        self.__reinit__()
        return self.thumbnail

    def has_tag(self, tag, check_children=True):
        '''
        Return the Tag object if this photo contains that tag. Otherwise return False.

        check_children:
            If True, children of the requested tag are counted
        '''
        tag = self.photodb.get_tag(tag)

        if check_children:
            tags = tag.walk_children()
        else:
            tags = [tag]

        for tag in tags:
            self.photodb.cur.execute(
                'SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid == ?',
                [self.id, tag.id]
            )
            if self.photodb.cur.fetchone() is not None:
                return tag

        return False

    def make_thumbnail_filepath(self):
        chunked_id = helpers.chunk_sequence(self.id, 3)
        basename = chunked_id[-1]
        folder = chunked_id[:-1]
        folder = os.sep.join(folder)
        folder = os.path.join(self.photodb.thumbnail_folder, folder)
        if folder:
            os.makedirs(folder, exist_ok=True)
        hopeful_filepath = os.path.join(folder, basename) + '.jpg'
        return hopeful_filepath

    def mimetype(self):
        return get_mimetype(self.real_filepath)

    @decorators.time_me
    def reload_metadata(self, commit=True):
        '''
        Load the file's height, width, etc as appropriate for this type of file.
        '''
        self.bytes = os.path.getsize(self.real_filepath)
        self.width = None
        self.height = None
        self.area = None
        self.ratio = None
        self.duration = None

        mime = self.mimetype()
        if mime == 'image':
            try:
                image = PIL.Image.open(self.real_filepath)
            except (OSError, ValueError):
                log.debug('Failed to read image data for {photo:r}'.format(photo=self))
            else:
                (self.width, self.height) = image.size
                image.close()
                log.debug('Loaded image data for {photo:r}'.format(photo=self))

        elif mime == 'video' and ffmpeg:
            try:
                probe = ffmpeg.probe(self.real_filepath)
                if probe and probe.video:
                    self.duration = probe.format.duration or probe.video.duration
                    self.width = probe.video.video_width
                    self.height = probe.video.video_height
            except:
                traceback.print_exc()

        elif mime == 'audio':
            try:
                probe = ffmpeg.probe(self.real_filepath)
                if probe and probe.audio:
                    self.duration = probe.audio.duration
            except:
                traceback.print_exc()

        if self.width and self.height:
            self.area = self.width * self.height
            self.ratio = round(self.width / self.height, 2)

        self.photodb.cur.execute(
            'UPDATE photos SET width=?, height=?, area=?, ratio=?, duration=?, bytes=? WHERE id==?',
            [self.width, self.height, self.area, self.ratio, self.duration, self.bytes, self.id],
        )
        if commit:
            log.debug('Committing - reload metadata')
            self.photodb.commit()

    def remove_tag(self, tag, commit=True):
        tag = self.photodb.get_tag(tag)

        log.debug('Removing tag {t} from photo {p}'.format(t=repr(tag), p=repr(self)))
        tags = list(tag.walk_children())
        for tag in tags:
            self.photodb.cur.execute(
                'DELETE FROM photo_tag_rel WHERE photoid == ? AND tagid == ?',
                [self.id, tag.id]
            )
        if commit:
            log.debug('Committing - remove photo tag')
            self.photodb.commit()

    def rename_file(self, new_filename, move=False, commit=True):
        '''
        Rename the file on the disk as well as in the database.
        If `move` is True, allow this operation to move the file.
        Otherwise, slashes will be considered an error.
        '''
        current_dir = os.path.normcase(os.path.dirname(self.real_filepath))
        new_filename = normalize_filepath(new_filename)
        new_dir = os.path.normcase(os.path.dirname(new_filename))
        if new_dir == '':
            new_dir = current_dir
            new_abspath = os.path.join(new_dir, new_filename)
        else:
            new_abspath = os.path.abspath(new_filename)
            new_dir = os.path.normcase(os.path.dirname(new_abspath))
        if (new_dir != current_dir) and not move:
            raise ValueError('Cannot move the file without param move=True')

        os.makedirs(new_dir, exist_ok=True)
        new_basename = os.path.basename(new_abspath)

        new_abs_norm = os.path.normcase(new_abspath)
        current_norm = os.path.normcase(self.real_filepath)

        if new_abs_norm != current_norm:
            try:
                os.link(self.real_filepath, new_abspath)
            except OSError:
                # Happens when trying to hardlink across disks
                spinal.copy_file(self.real_filepath, new_abspath)

        self.photodb.cur.execute(
            'UPDATE photos SET filepath = ? WHERE filepath == ?',
            [new_abspath, self.real_filepath]
        )

        if commit:
            if new_abs_norm != current_norm:
                os.remove(self.real_filepath)
            else:
                os.rename(self.real_filepath, new_abspath)
            log.debug('Committing - rename file')
            self.photodb.commit()
        else:
            queue_action = {'action': os.remove, 'args': [self.real_filepath]}
            self.photodb.on_commit_queue.append(queue_action)
        
        self.__reinit__()

    def tags(self):
        '''
        Return the tags assigned to this Photo.
        '''
        tags = []
        generator = select(
            self.photodb.sql,
            'SELECT * FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        )
        for tag in generator:
            tagid = tag[SQL_PHOTOTAG['tagid']]
            tag = self.photodb.get_tag(id=tagid)
            tags.append(tag)
        return tags


class Tag(ObjectBase, GroupableMixin):
    '''
    A Tag, which can be applied to Photos for organization.
    '''
    def __init__(self, photodb, row_tuple):
        self.photodb = photodb
        self.id = row_tuple[SQL_TAG['id']]
        self.name = row_tuple[SQL_TAG['name']]
        self.group_getter = self.photodb.get_tag
        self._cached_qualified_name = None

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        elif isinstance(other, Tag):
            return self.id == other.id and self.name == other.name
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        rep = 'Tag:{id}:{name}'.format(name=self.name, id=self.id)
        return rep

    def __str__(self):
        rep = 'Tag:{name}'.format(name=self.name)
        return rep

    def add_synonym(self, synname, commit=True):
        synname = normalize_tagname(synname)

        if synname == self.name:
            raise ValueError('Cannot assign synonym to itself.')

        try:
            tag = self.photodb.get_tag_by_name(synname)
        except NoSuchTag:
            pass
        else:
            raise TagExists(synname)

        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute('INSERT INTO tag_synonyms VALUES(?, ?)', [synname, self.name])

        if commit:
            log.debug('Committing - add synonym')
            self.photodb.commit()

    def convert_to_synonym(self, mastertag, commit=True):
        '''
        Convert an independent tag into a synonym for a different independent tag.
        All photos which possess the current tag will have it replaced
        with the new master tag.
        All synonyms of the old tag will point to the new tag.

        Good for when two tags need to be merged under a single name.
        '''
        mastertag = self.photodb.get_tag(mastertag)

        # Migrate the old tag's synonyms to the new one
        # UPDATE is safe for this operation because there is no chance of duplicates.
        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute(
            'UPDATE tag_synonyms SET mastername = ? WHERE mastername == ?',
            [mastertag.name, self.name]
        )

        # Iterate over all photos with the old tag, and swap them to the new tag
        # if they don't already have it.
        generator = select(self.photodb.sql, 'SELECT * FROM photo_tag_rel WHERE tagid == ?', [self.id])
        for relationship in generator:
            photoid = relationship[SQL_PHOTOTAG['photoid']]
            self.photodb.cur.execute('SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid == ?', [photoid, mastertag.id])
            if self.photodb.cur.fetchone() is None:
                self.photodb.cur.execute('INSERT INTO photo_tag_rel VALUES(?, ?)', [photoid, mastertag.id])

        # Then delete the relationships with the old tag
        self.delete()

        # Enjoy your new life as a monk.
        mastertag.add_synonym(self.name, commit=False)
        if commit:
            log.debug('Committing - convert to synonym')
            self.photodb.commit()

    def delete(self, delete_children=False, commit=True):
        log.debug('Deleting tag {tag:r}'.format(tag=self))
        self.photodb._cached_frozen_children = None
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        self.photodb.cur.execute('DELETE FROM tags WHERE id == ?', [self.id])
        self.photodb.cur.execute('DELETE FROM photo_tag_rel WHERE tagid == ?', [self.id])
        self.photodb.cur.execute('DELETE FROM tag_synonyms WHERE mastername == ?', [self.name])
        if commit:
            log.debug('Committing - delete tag')
            self.photodb.commit()

    def qualified_name(self):
        '''
        Return the 'group1.group2.tag' string for this tag.
        '''
        if self._cached_qualified_name:
            return self._cached_qualified_name
        string = self.name
        for parent in self.walk_parents():
            string = parent.name + '.' + string
        self._cached_qualified_name = string
        return string

    def remove_synonym(self, synname, commit=True):
        '''
        Delete a synonym.
        This will have no effect on photos or other synonyms because
        they always resolve to the master tag before application.
        '''
        synname = normalize_tagname(synname)
        self.photodb.cur.execute('SELECT * FROM tag_synonyms WHERE name == ?', [synname])
        fetch = self.photodb.cur.fetchone()
        if fetch is None:
            raise NoSuchSynonym(synname)

        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute('DELETE FROM tag_synonyms WHERE name == ?', [synname])
        if commit:
            log.debug('Committing - remove synonym')
            self.photodb.commit()

    def rename(self, new_name, apply_to_synonyms=True, commit=True):
        '''
        Rename the tag. Does not affect its relation to Photos or tag groups.
        '''
        new_name = normalize_tagname(new_name)
        if new_name == self.name:
            return

        try:
            self.photodb.get_tag(new_name)
        except NoSuchTag:
            pass
        else:
            raise TagExists(new_name)

        self._cached_qualified_name = None
        self.photodb._cached_frozen_children = None
        self.photodb.cur.execute('UPDATE tags SET name = ? WHERE id == ?', [new_name, self.id])
        if apply_to_synonyms:
            self.photodb.cur.execute(
                'UPDATE tag_synonyms SET mastername = ? WHERE mastername = ?',
                [new_name, self.name]
            )

        self.name = new_name
        if commit:
            log.debug('Committing - rename tag')
            self.photodb.commit()

    def synonyms(self):
        self.photodb.cur.execute('SELECT name FROM tag_synonyms WHERE mastername == ?', [self.name])
        fetch = self.photodb.cur.fetchall()
        fetch = [f[0] for f in fetch]
        fetch.sort()
        return fetch


if __name__ == '__main__':
    p = PhotoDB()
    print(p)
