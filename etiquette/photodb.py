import bcrypt
import collections
import copy
import json
import logging
import os
import random
import sqlite3
import string
import time

from . import constants
from . import decorators
from . import exceptions
from . import helpers
from . import objects
from . import searchhelpers

from voussoirkit import expressionmatch
from voussoirkit import pathclass
from voussoirkit import safeprint
from voussoirkit import spinal


logging.basicConfig(level=logging.DEBUG)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)


# Note: Setting user_version pragma in init sequence is safe because it only
# happens after the out-of-date check occurs, so no chance of accidentally
# overwriting it.
DATABASE_VERSION = 7
DB_INIT = '''
PRAGMA count_changes = OFF;
PRAGMA cache_size = 10000;
PRAGMA user_version = {user_version};

----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_associated_directories(
    albumid TEXT,
    directory TEXT COLLATE NOCASE
);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
    album_associated_directories(albumid);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
    album_associated_directories(directory);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_group_rel(
    parentid TEXT,
    memberid TEXT
);
CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid TEXT,
    photoid TEXT
);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS albums(
    id TEXT,
    title TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks(
    id TEXT,
    title TEXT,
    url TEXT,
    author_id TEXT
);
CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
CREATE INDEX IF NOT EXISTS index_bookmarks_author on bookmarks(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_numbers(
    tab TEXT,
    last_id TEXT
);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid TEXT,
    tagid TEXT
);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
----------------------------------------------------------------------------------------------------
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
    thumbnail TEXT,
    tagged_at INT,
    author_id TEXT
);
CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_override_filename on
    photos(override_filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid TEXT,
    memberid TEXT
);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT,
    mastername TEXT
);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags(
    id TEXT,
    name TEXT
);
CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users(
    id TEXT,
    username TEXT COLLATE NOCASE,
    password BLOB,
    created INT
);
CREATE INDEX IF NOT EXISTS index_users_id on users(id);
CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
'''.format(user_version=DATABASE_VERSION)


def _helper_filenamefilter(subject, terms):
    basename = subject.lower()
    return all(term in basename for term in terms)

def searchfilter_must_may_forbid(photo_tags, tag_musts, tag_mays, tag_forbids, frozen_children):
    if tag_musts:
        for must in tag_musts:
            for option in frozen_children[must]:
                if option in photo_tags:
                    break
            else:
                # Fail when ANY of the tags fails to find an option.
                return False

    if tag_mays:
        for may in tag_mays:
            for option in frozen_children[may]:
                if option in photo_tags:
                    break
            else:
                continue
            break
        else:
            # Fail when ALL of the tags fail to find an option.
            return False

    if tag_forbids:
        for forbid in tag_forbids:
            for option in frozen_children[forbid]:
                if option in photo_tags:
                    return False

    return True

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


class PDBAlbumMixin:
    def get_album(self, id):
        return self.get_thing_by_id('album', id)

    def get_album_by_path(self, filepath):
        '''
        Return the album with the `associated_directory` of this value, NOT case-sensitive.
        '''
        filepath = os.path.abspath(filepath)
        cur = self.sql.cursor()
        cur.execute('SELECT * FROM album_associated_directories WHERE directory == ?', [filepath])
        fetch = cur.fetchone()
        if fetch is None:
            raise exceptions.NoSuchAlbum(filepath)
        album_id = fetch[constants.SQL_ALBUM_DIRECTORY['albumid']]
        return self.get_album(album_id)

    def get_albums(self):
        yield from self.get_things(thing_type='album')

    def new_album(
            self,
            title=None,
            description=None,
            *,
            associated_directory=None,
            commit=True,
            photos=None,
        ):
        '''
        Create a new album. Photos can be added now or later.
        '''
        if not self.config['enable_new_album']:
            raise exceptions.FeatureDisabled('new_album')

        albumid = self.generate_id('albums')
        title = title or ''
        description = description or ''
        if not isinstance(title, str):
            raise TypeError('Title must be string, not %s' % type(title))

        if not isinstance(description, str):
            raise TypeError('Description must be string, not %s' % type(description))

        cur = self.sql.cursor()
        if associated_directory is not None:
            associated_directory = os.path.abspath(associated_directory)
            cur.execute(
                'SELECT * FROM album_associated_directories WHERE directory == ?',
                [associated_directory]
            )
            fetch = cur.fetchone()
            if fetch is not None:
                album = self.get_album(fetch[constants.SQL_ALBUM_DIRECTORY['albumid']])
                raise exceptions.AlbumExists(album)

        self.log.debug('New Album: %s' % title)
        data = {
            'id': albumid,
            'title': title,
            'description': description,
        }

        (qmarks, bindings) = helpers.binding_filler(constants.SQL_ALBUM_COLUMNS, data)
        query = 'INSERT INTO albums VALUES(%s)' % qmarks
        cur.execute(query, bindings)
        album = objects.Album(self, data)

        if associated_directory is not None:
            data = {
                'albumid': albumid,
                'directory': associated_directory,
            }
            (qmarks, bindings) = helpers.binding_filler(constants.SQL_ALBUM_DIRECTORY_COLUMNS, data)
            query = 'INSERT INTO album_associated_directories VALUES(%s)' % qmarks
            cur.execute(query, bindings)

        if photos:
            for photo in photos:
                photo = self.get_photo(photo)
                album.add_photo(photo, commit=False)

        if commit:
            self.log.debug('Committing - new Album')
            self.commit()
        return album


class PDBBookmarkMixin:
    def get_bookmark(self, id):
        cur = self.sql.cursor()
        cur.execute('SELECT * FROM bookmarks WHERE id == ?', [id])
        fetch = cur.fetchone()
        if fetch is None:
            raise exceptions.NoSuchBookmark(id)
        bookmark = objects.Bookmark(self, fetch)
        return bookmark

    def get_bookmarks(self):
        yield from self.get_things(thing_type='bookmark')

    def new_bookmark(self, url, title=None, *, author=None, commit=True):
        if not self.config['enable_new_bookmark']:
            raise exceptions.FeatureDisabled('new_bookmark')

        if not url:
            raise ValueError('Must provide a URL')

        bookmark_id = self.generate_id('bookmarks')
        title = title or None
        author_id = self.get_user_id_or_none(author)

        # To do: NORMALIZATION AND VALIDATION

        data = {
            'author_id': author_id,
            'id': bookmark_id,
            'title': title,
            'url': url,
        }

        (qmarks, bindings) = helpers.binding_filler(constants.SQL_BOOKMARK_COLUMNS, data)
        query = 'INSERT INTO bookmarks VALUES(%s)' % qmarks
        cur = self.sql.cursor()
        cur.execute(query, bindings)

        bookmark = objects.Bookmark(self, data)
        if commit:
            self.log.debug('Committing - new Bookmark')
            self.commit()
        return bookmark


class PDBPhotoMixin:
    def get_photo(self, photoid):
        return self.get_thing_by_id('photo', photoid)

    def get_photo_by_path(self, filepath):
        filepath = os.path.abspath(filepath)
        cur = self.sql.cursor()
        cur.execute('SELECT * FROM photos WHERE filepath == ?', [filepath])
        fetch = cur.fetchone()
        if fetch is None:
            raise exceptions.NoSuchPhoto(filepath)
        photo = objects.Photo(self, fetch)
        return photo

    def get_photos_by_recent(self, count=None):
        '''
        Yield photo objects in order of creation time.
        '''
        if count is not None and count <= 0:
            return
        # We're going to use a second cursor because the first one may
        # get used for something else, deactivating this query.
        cur = self.sql.cursor()
        cur.execute('SELECT * FROM photos ORDER BY created DESC')
        while True:
            fetch = cur.fetchone()
            if fetch is None:
                break
            photo = objects.Photo(self, fetch)

            yield photo

            if count is None:
                continue
            count -= 1
            if count <= 0:
                break

    def new_photo(
            self,
            filename,
            *,
            allow_duplicates=False,
            author=None,
            commit=True,
            do_metadata=True,
            do_thumbnail=True,
            tags=None,
        ):
        '''
        Given a filepath, determine its attributes and create a new Photo object in the
        database. Tags may be applied now or later.

        If `allow_duplicates` is False, we will first check the database for any files
        with the same path and raise exceptions.PhotoExists if found.

        Returns the Photo object.
        '''
        if not self.config['enable_new_photo']:
            raise exceptions.FeatureDisabled('new_photo')

        filename = os.path.abspath(filename)
        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)

        if not allow_duplicates:
            try:
                existing = self.get_photo_by_path(filename)
            except exceptions.NoSuchPhoto:
                pass
            else:
                raise exceptions.PhotoExists(existing)

        self.log.debug('New Photo: %s' % filename)
        author_id = self.get_user_id_or_none(author)

        extension = os.path.splitext(filename)[1]
        extension = extension.replace('.', '')
        #extension = self.normalize_tagname(extension)
        created = int(helpers.now())
        photoid = self.generate_id('photos')

        data = {
            'id': photoid,
            'filepath': filename,
            'override_filename': None,
            'extension': extension,
            'created': created,
            'tagged_at': None,
            'author_id': author_id,
            # These will be filled in during the metadata stage.
            'bytes': None,
            'width': None,
            'height': None,
            'area': None,
            'ratio': None,
            'duration': None,
            'thumbnail': None,
        }

        (qmarks, bindings) = helpers.binding_filler(constants.SQL_PHOTO_COLUMNS, data)
        query = 'INSERT INTO photos VALUES(%s)' % qmarks
        cur = self.sql.cursor()
        cur.execute(query, bindings)
        photo = objects.Photo(self, data)

        if do_metadata:
            photo.reload_metadata(commit=False)
        if do_thumbnail:
            photo.generate_thumbnail(commit=False)

        tags = tags or []
        tags = [self.get_tag(tag) for tag in tags]
        for tag in tags:
            photo.add_tag(tag, commit=False)

        if commit:
            self.log.debug('Committing - new_photo')
            self.commit()
        return photo

    def purge_deleted_files(self, photos=None, *, commit=True):
        '''
        Remove Photo entries if their corresponding file is no longer found.

        photos: An iterable of Photo objects to check.
        If not provided, everything is checked.
        '''
        if photos is None:
            photos = self.get_photos_by_recent()

        for photo in photos:
            if os.path.exists(photo.real_filepath):
                continue
            photo.delete(commit=False)
        if commit:
            self.log.debug('Committing - purge deleted photos')
            self.commit()

    def purge_empty_albums(self, *, commit=True):
        albums = self.get_albums()
        for album in albums:
            if album.children() or album.photos():
                continue
            album.delete(commit=False)
        if commit:
            self.log.debug('Committing - purge empty albums')
            self.commit()

    def search(
            self,
            *,
            area=None,
            width=None,
            height=None,
            ratio=None,
            bytes=None,
            duration=None,

            authors=None,
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

            limit=None,
            offset=None,
            orderby=None,
            warning_bag=None,
            give_back_parameters=False,
        ):
        '''
        PHOTO PROPERTIES
        area, width, height, ratio, bytes, duration:
            A hyphen_range string representing min and max. Or just a number
            for lower bound.

        TAGS AND FILTERS
        authors:
            A list of User objects, or usernames, or user ids.

        created:
            A hyphen_range string respresenting min and max. Or just a number
            for lower bound.

        extension:
            A string or list of strings of acceptable file extensions.

        extension_not:
            A string or list of strings of unacceptable file extensions.
            Including '*' will forbid all extensions

        filename:
            A string or list of strings in the form of an expression.
            Match is CASE-INSENSITIVE.
            Examples:
            '.pdf AND (programming OR "survival guide")'
            '.pdf programming python' (implicitly AND each term)

        has_tags:
            If True, require that the Photo has >=1 tag.
            If False, require that the Photo has no tags.
            If None, any amount is okay.

        mimetype:
            A string or list of strings of acceptable mimetypes.
            'image', 'video', ...

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
            A string or list of strings in the form of an expression.
            Can NOT be used with the must, may, forbid style search.
            Examples:
            'family AND (animals OR vacation)'
            'family vacation outdoors' (implicitly AND each term)

        QUERY OPTIONS
        limit:
            The maximum number of *successful* results to yield.

        offset:
            How many *successful* results to skip before we start yielding.

        orderby:
            A list of strings like ['ratio DESC', 'created ASC'] to sort
            and subsort the results.
            Descending is assumed if not provided.

        warning_bag:
            If provided, invalid search queries will add a warning to the bag
            and try their best to continue. The generator will yield the bag
            back to you as the final object.
            Without the bag, exceptions may be raised.

        give_back_parameters:
            If True, the generator's first yield will be a dictionary of all the
            cleaned up, normalized parameters. The user may have given us loads
            of trash, so we should show them the formatting we want.
        '''
        start_time = time.time()

        # MINMAXERS

        has_tags = searchhelpers.normalize_has_tags(has_tags)
        if has_tags is False:
            tag_musts = None
            tag_mays = None
            tag_forbids = None
            tag_expression = None    
        else:
            _helper = lambda tagset: searchhelpers.normalize_tag_mmf(
                photodb=self,
                tags=tagset,
                warning_bag=warning_bag
            )
            tag_musts = _helper(tag_musts)
            tag_mays = _helper(tag_mays)
            tag_forbids = _helper(tag_forbids)
            tag_expression = searchhelpers.normalize_tag_expression(tag_expression)

        #print(tag_musts, tag_mays, tag_forbids)
        if (tag_musts or tag_mays or tag_forbids) and tag_expression:
            message = 'Expression filter cannot be used with musts, mays, forbids'
            if warning_bag:
                warning_bag.add(message)
                tag_musts = None
                tag_mays = None
                tag_forbids = None
                tag_expression = None
            else:
                raise exceptions.NotExclusive(message)

        extension = searchhelpers.normalize_extensions(extension)
        extension_not = searchhelpers.normalize_extensions(extension_not)
        mimetype = searchhelpers.normalize_extensions(mimetype)

        authors = searchhelpers.normalize_authors(authors, photodb=self, warning_bag=warning_bag)

        filename = searchhelpers.normalize_filename(filename)

        limit = searchhelpers.normalize_limit(limit, warning_bag=warning_bag)

        offset = searchhelpers.normalize_offset(offset)
        if offset is None:
            offset = 0

        maximums = {}
        minimums = {}
        searchhelpers.minmax('area', area, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('created', created, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('width', width, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('height', height, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('ratio', ratio, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('bytes', bytes, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('duration', duration, minimums, maximums, warning_bag=warning_bag)

        orderby = searchhelpers.normalize_orderby(orderby)
        notnulls = []
        if extension or mimetype:
            notnulls.append('extension')
        if width or height or ratio or area:
            notnulls.append('width')
        if bytes:
            notnulls.append('bytes')
        if duration:
            notnulls.append('duration')
        query = searchhelpers.build_query(orderby, notnulls)
        print(query)
        generator = helpers.select_generator(self.sql, query)

        if orderby is None:
            giveback_orderby = None
        else:
            giveback_orderby = [term.replace('RANDOM()', 'random') for term in orderby]
        if give_back_parameters:
            parameters = {
                'area': area,
                'width': width,
                'height': height,
                'ratio': ratio,
                'bytes': bytes,
                'duration': duration,
                'authors': authors,
                'created': created,
                'extension': extension,
                'extension_not': extension_not,
                'filename': filename,
                'has_tags': has_tags,
                'mimetype': mimetype,
                'tag_musts': tag_musts,
                'tag_mays': tag_mays,
                'tag_forbids': tag_forbids,
                'tag_expression': tag_expression,
                'limit': limit,
                'offset': offset,
                'orderby': giveback_orderby,
            }
            yield parameters

        # FROZEN CHILDREN
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

        if tag_expression:
            expression_tree = expressionmatch.ExpressionTree.parse(tag_expression)
            expression_tree.map(self.normalize_tagname)
            expression_matcher = searchhelpers.tag_expression_matcher_builder(
                frozen_children,
                warning_bag=warning_bag,
            )
            for node in expression_tree.walk_leaves():
                if node.token in frozen_children:
                    continue

                exc = exceptions.NoSuchTag(node.token)
                if warning_bag is not None:
                    warning_bag.add(exc.error_message)
                    node.token = None
                else:
                    raise exc

            expression_tree.prune()

        if filename:
            filename_tree = expressionmatch.ExpressionTree.parse(filename)
            filename_tree.map(lambda x: x.lower())

        photos_received = 0

        # LET'S GET STARTED
        for fetch in generator:
            photo = objects.Photo(self, fetch)

            if extension and photo.extension not in extension:
                #print('Failed extension')
                continue

            ext_fail = (
                extension_not and
                (
                    ('*' in extension_not and photo.extension) or
                    (photo.extension in extension_not)
                )
            )
            if ext_fail:
                #print('Failed extension_not')
                continue

            if mimetype and photo.simple_mimetype not in mimetype:
                #print('Failed mimetype')
                continue

            if authors and photo.author_id not in authors:
                #print('Failed author')
                continue

            if filename and not filename_tree.evaluate(photo.basename.lower()):
                #print('Failed filename')
                continue

            if any(
                not fetch[constants.SQL_PHOTO[key]] or
                fetch[constants.SQL_PHOTO[key]] > value for (key, value) in maximums.items()
                ):
                #print('Failed maximums')
                continue

            if any(
                not fetch[constants.SQL_PHOTO[key]] or
                fetch[constants.SQL_PHOTO[key]] < value for (key, value) in minimums.items()
                ):
                #print('Failed minimums')
                continue

            if (has_tags is not None) or is_tagsearch:
                photo_tags = set(photo.tags())

                if has_tags is False and len(photo_tags) > 0:
                    #print('Failed has_tags=False')
                    continue

                if has_tags is True and len(photo_tags) == 0:
                    #print('Failed has_tags=True')
                    continue

                if tag_expression:
                    success = expression_tree.evaluate(
                        photo_tags,
                        match_function=expression_matcher,
                    )
                    if not success:
                        #print('Failed tag expression')
                        continue
                elif is_must_may_forbid:
                    success = searchfilter_must_may_forbid(
                        photo_tags=photo_tags,
                        tag_musts=tag_musts,
                        tag_mays=tag_mays,
                        tag_forbids=tag_forbids,
                        frozen_children=frozen_children,
                    )
                    if not success:
                        #print('Failed tag mmf')
                        continue

            if offset > 0:
                offset -= 1
                continue

            if limit is not None and photos_received >= limit:
                break

            photos_received += 1
            yield photo

        if warning_bag and warning_bag.warnings:
            yield warning_bag

        end_time = time.time()
        print('Search results took:', end_time - start_time)


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
            raise exceptions.NotExclusive('One and only one of `id`, `name` must be passed.')

        if id is not None:
            return self.get_tag_by_id(id)
        else:
            return self.get_tag_by_name(name)

    def get_tag_by_id(self, id):
        return self.get_thing_by_id('tag', thing_id=id)

    def get_tag_by_name(self, tagname):
        if isinstance(tagname, objects.Tag):
            tagname = tagname.name

        tagname = tagname.strip('.+')
        tagname = tagname.split('.')[-1].split('+')[0]
        tagname = self.normalize_tagname(tagname)

        cur = self.sql.cursor()
        while True:
            # Return if it's a toplevel...
            cur.execute('SELECT * FROM tags WHERE name == ?', [tagname])
            fetch = cur.fetchone()
            if fetch is not None:
                return objects.Tag(self, fetch)

            # ...or resolve the synonym and try again.
            cur.execute('SELECT * FROM tag_synonyms WHERE name == ?', [tagname])
            fetch = cur.fetchone()
            if fetch is None:
                # was not a master tag or synonym
                raise exceptions.NoSuchTag(tagname)
            tagname = fetch[constants.SQL_SYN['master']]

    def get_tags(self):
        yield from self.get_things(thing_type='tag')

    def new_tag(self, tagname, *, commit=True):
        '''
        Register a new tag and return the Tag object.
        '''
        if not self.config['enable_new_tag']:
            raise exceptions.FeatureDisabled('new_tag')

        tagname = self.normalize_tagname(tagname)
        try:
            existing_tag = self.get_tag_by_name(tagname)
        except exceptions.NoSuchTag:
            pass
        else:
            raise exceptions.TagExists(existing_tag)

        tagid = self.generate_id('tags')
        self._cached_frozen_children = None
        cur = self.sql.cursor()
        cur.execute('INSERT INTO tags VALUES(?, ?)', [tagid, tagname])
        if commit:
            self.log.debug('Committing - new_tag')
            self.commit()
        tag = objects.Tag(self, [tagid, tagname])
        return tag

    def normalize_tagname(self, tagname):
        '''
        Tag names can only consist of characters defined in the config.
        The given tagname is lowercased, gets its spaces and hyphens
        replaced by underscores, and is stripped of any not-whitelisted
        characters.
        '''
        original_tagname = tagname
        tagname = tagname.lower()
        tagname = tagname.replace('-', '_')
        tagname = tagname.replace(' ', '_')
        tagname = (c for c in tagname if c in self.config['valid_tag_chars'])
        tagname = ''.join(tagname)

        if len(tagname) < self.config['min_tag_name_length']:
            raise exceptions.TagTooShort(original_tagname)

        elif len(tagname) > self.config['max_tag_name_length']:
            raise exceptions.TagTooLong(tagname)

        else:
            return tagname


class PDBUserMixin:
    def generate_user_id(self):
        '''
        User IDs are randomized instead of integers like the other objects,
        so they get their own method.
        '''
        possible = string.digits + string.ascii_uppercase
        cur = self.sql.cursor()
        for retry in range(20):
            user_id = [random.choice(possible) for x in range(self.config['id_length'])]
            user_id = ''.join(user_id)

            cur.execute('SELECT * FROM users WHERE id == ?', [user_id])
            if cur.fetchone() is None:
                break
        else:
            raise Exception('Failed to create user id after 20 tries.')

        return user_id

    def get_user(self, username=None, id=None):
        if not helpers.is_xor(id, username):
            raise exceptions.NotExclusive('One and only one of `id`, `username` must be passed.')

        cur = self.sql.cursor()
        if username is not None:
            cur.execute('SELECT * FROM users WHERE username == ?', [username])
        else:
            cur.execute('SELECT * FROM users WHERE id == ?', [id])

        fetch = cur.fetchone()
        if fetch is not None:
            return objects.User(self, fetch)
        else:
            raise exceptions.NoSuchUser(username or id)

    def get_user_id_or_none(self, user):
        '''
        For methods that create photos, albums, etc., we sometimes associate
        them with an author but sometimes not. This method hides validation
        that those methods would otherwise have to duplicate.
        '''
        if isinstance(user, objects.User):
            if user.photodb != self:
                raise ValueError('That user does not belong to this photodb')
            author_id = user.id
        elif user is not None:
            # Confirm that this string is an ID and not junk.
            author_id = self.get_user(id=user).id
        else:
            author_id = None
        return author_id

    def login(self, user_id, password):
        cur = self.sql.cursor()
        cur.execute('SELECT * FROM users WHERE id == ?', [user_id])
        fetch = cur.fetchone()

        if fetch is None:
            raise exceptions.WrongLogin()

        stored_password = fetch[constants.SQL_USER['password']]

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        success = bcrypt.checkpw(password, stored_password)
        if not success:
            raise exceptions.WrongLogin()

        return objects.User(self, fetch)

    def register_user(self, username, password, commit=True):
        if not self.config['enable_new_user']:
            raise exceptions.FeatureDisabled('new_user')

        if len(username) < self.config['min_username_length']:
            raise exceptions.UsernameTooShort(
                username=username,
                min_length=self.config['min_username_length']
            )

        if len(username) > self.config['max_username_length']:
            raise exceptions.UsernameTooLong(
                username=username,
                max_length=self.config['max_username_length']
            )

        badchars = [c for c in username if c not in self.config['valid_username_chars']]
        if badchars:
            raise exceptions.InvalidUsernameChars(username=username, badchars=badchars)

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        if len(password) < self.config['min_password_length']:
            raise exceptions.PasswordTooShort(min_length=self.config['min_password_length'])

        try:
            existing_user = self.get_user(username=username)
        except exceptions.NoSuchUser:
            pass
        else:
            raise exceptions.UserExists(existing_user)

        user_id = self.generate_user_id()
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        created = int(helpers.now())

        data = {
            'id': user_id,
            'username': username,
            'password': hashed_password,
            'created': created,
        }

        (qmarks, bindings) = helpers.binding_filler(constants.SQL_USER_COLUMNS, data)
        query = 'INSERT INTO users VALUES(%s)' % qmarks
        cur = self.sql.cursor()
        cur.execute(query, bindings)

        if commit:
            self.log.debug('Committing - register user')
            self.commit()

        return objects.User(self, data)


class PhotoDB(PDBAlbumMixin, PDBBookmarkMixin, PDBPhotoMixin, PDBTagMixin, PDBUserMixin):
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
            data_directory=None,
        ):
        if data_directory is None:
            data_directory = constants.DEFAULT_DATADIR

        # DATA DIR PREP
        data_directory = helpers.normalize_filepath(data_directory, allowed='/\\')
        self.data_directory = pathclass.Path(data_directory)
        os.makedirs(self.data_directory.absolute_path, exist_ok=True)

        # DATABASE
        self.database_file = self.data_directory.with_child('phototagger.db')
        existing_database = self.database_file.exists
        self.sql = sqlite3.connect(self.database_file.absolute_path)
        self.cur = self.sql.cursor()

        if existing_database:
            self.cur.execute('PRAGMA user_version')
            existing_version = self.cur.fetchone()[0]
            if existing_version != DATABASE_VERSION:
                message = constants.ERROR_DATABASE_OUTOFDATE
                message = message.format(current=existing_version, new=DATABASE_VERSION)
                raise SystemExit(message)

        statements = DB_INIT.split(';')
        for statement in statements:
            self.cur.execute(statement)
        self.sql.commit()

        # CONFIG
        self.config = copy.deepcopy(constants.DEFAULT_CONFIGURATION)
        self.config_filepath = self.data_directory.with_child('config.json')
        user_config_exists = self.config_filepath.is_file
        if user_config_exists:
            with open(self.config_filepath.absolute_path, 'r') as handle:
                user_config = json.load(handle)
            needs_dump = len(user_config) < len(self.config)
            self.config.update(user_config)
        else:
            needs_dump = True

        if (not user_config_exists) or needs_dump:
            with open(self.config_filepath.absolute_path, 'w') as handle:
                handle.write(json.dumps(self.config, indent=4, sort_keys=True))


        # THUMBNAIL DIRECTORY
        self.thumbnail_directory = self.data_directory.with_child('site_thumbnails')
        os.makedirs(self.thumbnail_directory.absolute_path, exist_ok=True)

        # OTHER
        self.log = logging.getLogger(__name__)
        self.log.setLevel(self.config['log_level'])
        self.on_commit_queue = []
        self._cached_frozen_children = None

    def __repr__(self):
        return 'PhotoDB(data_directory={datadir})'.format(datadir=repr(self.data_directory))

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

    def digest_directory(
            self,
            directory,
            *,
            exclude_directories=None,
            exclude_filenames=None,
            make_albums=True,
            recurse=True,
            commit=True,
        ):
        '''
        Create an album, and add the directory's contents to it recursively.

        If a Photo object already exists for a file, it will be added to the correct album.
        '''
        if not os.path.isdir(directory):
            raise ValueError('Not a directory: %s' % directory)
        if exclude_directories is None:
            exclude_directories = self.config['digest_exclude_dirs']
        if exclude_filenames is None:
            exclude_filenames = self.config['digest_exclude_files']

        directory = spinal.str_to_fp(directory)
        directory.correct_case()
        generator = spinal.walk_generator(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            recurse=recurse,
            yield_style='nested',
        )

        if make_albums:
            try:
                album = self.get_album_by_path(directory.absolute_path)
            except exceptions.NoSuchAlbum:
                album = self.new_album(
                    associated_directory=directory.absolute_path,
                    commit=False,
                    title=directory.basename,
                )
            albums = {directory.absolute_path: album}

        for (current_location, directories, files) in generator:
            # Create the photo object
            new_photos = []
            for filepath in files:
                try:
                    photo = self.new_photo(filepath.absolute_path, commit=False)
                except exceptions.PhotoExists as e:
                    photo = e.photo
                new_photos.append(photo)

            if not make_albums:
                continue

            # Ensure that the current directory is an album.
            current_album = albums.get(current_location.absolute_path, None)
            if current_album is None:
                try:
                    current_album = self.get_album_by_path(current_location.absolute_path)
                except exceptions.NoSuchAlbum:
                    current_album = self.new_album(
                        associated_directory=current_location.absolute_path,
                        commit=False,
                        title=current_location.basename,
                    )
                albums[current_location.absolute_path] = current_album

            parent = albums.get(current_location.parent.absolute_path, None)
            if parent is not None:
                try:
                    parent.add(current_album, commit=False)
                except exceptions.GroupExists:
                    pass
            for photo in new_photos:
                current_album.add_photo(photo, commit=False)

        if commit:
            self.log.debug('Committing - digest')
            self.commit()

        if make_albums:
            return album
        else:
            return None

    def easybake(self, ebstring):
        '''
        Easily create tags, groups, and synonyms with a string like
        "group1.group2.tag+synonym"
        "family.parents.dad+father"
        etc
        '''
        output_notes = []
        def create_or_get(name):
            #print('cog', name)
            try:
                item = self.get_tag(name)
                note = ('existing_tag', item.qualified_name())
            except exceptions.NoSuchTag:
                item = self.new_tag(name)
                note = ('new_tag', item.qualified_name())
            output_notes.append(note)
            return item

        ebstring = ebstring.strip()
        ebstring = ebstring.strip('.+=')
        if ebstring == '':
            raise exceptions.EasyBakeError('No tag supplied')

        if '=' in ebstring and '+' in ebstring:
            raise exceptions.EasyBakeError('Cannot rename and assign snynonym at once')

        rename_parts = ebstring.split('=')
        if len(rename_parts) == 2:
            (ebstring, rename_to) = rename_parts
        elif len(rename_parts) == 1:
            ebstring = rename_parts[0]
            rename_to = None
        else:
            raise exceptions.EasyBakeError('Too many equals signs')

        create_parts = ebstring.split('+')
        if len(create_parts) == 2:
            (tag, synonym) = create_parts
        elif len(create_parts) == 1:
            tag = create_parts[0]
            synonym = None
        else:
            raise exceptions.EasyBakeError('Too many plus signs')

        if not tag:
            raise exceptions.EasyBakeError('No tag supplied')

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
                except exceptions.GroupExists:
                    pass
            tag = tags[-1]

        if synonym:
            tag.add_synonym(synonym)
            note = ('new_synonym', '%s+%s' % (tag.name, synonym))
            output_notes.append(note)
            print('New syn %s' % synonym)
        return output_notes

    def generate_id(self, table):
        '''
        Create a new ID number that is unique to the given table.
        Note that while this method may INSERT / UPDATE, it does not commit.
        We'll wait for that to happen in whoever is calling us, so we know the
        ID is actually used.
        '''
        table = table.lower()
        if table not in ['photos', 'tags', 'albums', 'bookmarks']:
            raise ValueError('Invalid table requested: %s.', table)

        cur = self.sql.cursor()
        cur.execute('SELECT * FROM id_numbers WHERE tab == ?', [table])
        fetch = cur.fetchone()
        if fetch is None:
            # Register new value
            new_id_int = 1
            do_insert = True
        else:
            # Use database value
            new_id_int = int(fetch[constants.SQL_LASTID['last_id']]) + 1
            do_insert = False

        new_id = str(new_id_int).rjust(self.config['id_length'], '0')
        if do_insert:
            cur.execute('INSERT INTO id_numbers VALUES(?, ?)', [table, new_id])
        else:
            cur.execute('UPDATE id_numbers SET last_id = ? WHERE tab == ?', [new_id, table])
        return new_id

    def get_thing_by_id(self, thing_type, thing_id):
        thing_map = _THING_CLASSES[thing_type]

        if isinstance(thing_id, thing_map['class']):
            thing_id = thing_id.id

        query = 'SELECT * FROM %s WHERE id == ?' % thing_map['table']
        cur = self.sql.cursor()
        cur.execute(query, [thing_id])
        thing = cur.fetchone()
        if thing is None:
            raise thing_map['exception'](thing_id)
        thing = thing_map['class'](self, thing)
        return thing

    def get_things(self, thing_type, orderby=None):
        thing_map = _THING_CLASSES[thing_type]

        cur = self.sql.cursor()
        if orderby:
            cur.execute('SELECT * FROM %s ORDER BY %s' % (thing_map['table'], orderby))
        else:
            cur.execute('SELECT * FROM %s' % thing_map['table'])

        things = cur.fetchall()
        for thing in things:
            thing = thing_map['class'](self, db_row=thing)
            yield thing


_THING_CLASSES = {
    'album':
    {
        'class': objects.Album,
        'exception': exceptions.NoSuchAlbum,
        'table': 'albums',
    },
    'bookmark':
    {
        'class': objects.Bookmark,
        'exception': exceptions.NoSuchBookmark,
        'table': 'bookmarks',
    },
    'photo':
    {
        'class': objects.Photo,
        'exception': exceptions.NoSuchPhoto,
        'table': 'photos',
    },
    'tag':
    {
        'class': objects.Tag,
        'exception': exceptions.NoSuchTag,
        'table': 'tags',
    },
    'user':
    {
        'class': objects.User,
        'exception': exceptions.NoSuchUser,
        'table': 'users',
    }
}

if __name__ == '__main__':
    p = PhotoDB()
    print(p)
