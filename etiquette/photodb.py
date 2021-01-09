import bcrypt
import json
import os
import random
import re
import sqlite3
import tempfile
import time
import types

from voussoirkit import cacheclass
from voussoirkit import configlayers
from voussoirkit import expressionmatch
from voussoirkit import passwordy
from voussoirkit import pathclass
from voussoirkit import ratelimiter
from voussoirkit import spinal
from voussoirkit import sqlhelpers
from voussoirkit import vlogging

from . import constants
from . import decorators
from . import exceptions
from . import helpers
from . import objects
from . import searchhelpers
from . import tag_export

####################################################################################################

class PDBAlbumMixin:
    def __init__(self):
        super().__init__()

    def get_album(self, id):
        return self.get_thing_by_id('album', id)

    def get_album_count(self):
        return self.sql_select_one('SELECT COUNT(id) FROM albums')[0]

    def get_albums(self):
        return self.get_things(thing_type='album')

    def get_albums_by_id(self, ids):
        return self.get_things_by_id('album', ids)

    def get_albums_by_path(self, directory):
        '''
        Yield Albums with the `associated_directory` of this value,
        NOT case-sensitive.
        '''
        directory = pathclass.Path(directory)
        query = 'SELECT albumid FROM album_associated_directories WHERE directory == ?'
        bindings = [directory.absolute_path]
        album_rows = self.sql_select(query, bindings)
        album_ids = (album_id for (album_id,) in album_rows)
        return self.get_albums_by_id(album_ids)

    def get_albums_by_sql(self, query, bindings=None):
        return self.get_things_by_sql('album', query, bindings)

    def get_albums_within_directory(self, directory):
        # This function is something of a stopgap measure since `search` only
        # searches for photos and then yields their containing albums. Thus it
        # is not possible for search to find albums that contain no photos.
        # I'd like to find a better solution than this separate method.
        directory = pathclass.Path(directory)
        directory.assert_is_directory()
        pattern = directory.absolute_path.rstrip(os.sep)
        pattern = f'{pattern}{os.sep}%'
        album_rows = self.sql_select(
            'SELECT DISTINCT albumid FROM album_associated_directories WHERE directory LIKE ?',
            [pattern]
        )
        album_ids = (album_id for (album_id,) in album_rows)
        albums = self.get_albums_by_id(album_ids)
        return albums

    def get_root_albums(self):
        '''
        Yield Albums that have no parent.
        '''
        return self.get_root_things('album')

    @decorators.required_feature('album.new')
    @decorators.transaction
    def new_album(
            self,
            title=None,
            description=None,
            *,
            associated_directories=None,
            author=None,
            photos=None,
        ):
        '''
        Create a new album. Photos can be added now or later.
        '''
        # These might raise exceptions.
        title = objects.Album.normalize_title(title)
        description = objects.Album.normalize_description(description)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        album_id = self.generate_id(table='albums')
        self.log.info('New Album: %s %s.', album_id, title)

        data = {
            'id': album_id,
            'title': title,
            'description': description,
            'created': helpers.now(),
            'author_id': author_id,
        }
        self.sql_insert(table='albums', data=data)

        album = self.get_cached_instance('album', data)

        associated_directories = associated_directories or ()
        if isinstance(associated_directories, str):
            associated_directories = [associated_directories]
        album.add_associated_directories(associated_directories)

        if photos is not None:
            photos = [self.get_photo(photo) for photo in photos]
            album.add_photos(photos)

        return album

    @decorators.transaction
    def purge_deleted_associated_directories(self, albums=None):
        directories = self.sql_select('SELECT DISTINCT directory FROM album_associated_directories')
        directories = (pathclass.Path(directory) for (directory,) in directories)
        directories = [directory.absolute_path for directory in directories if not directory.exists]
        if not directories:
            return
        self.log.info('Purging associated directories %s.', directories)
        directories = sqlhelpers.listify(directories)

        query = f'DELETE FROM album_associated_directories WHERE directory in {directories}'
        if albums is not None:
            album_ids = sqlhelpers.listify(a.id for a in albums)
            query += f' AND albumid IN {album_ids}'
        self.sql_execute(query)
        yield from directories

    @decorators.transaction
    def purge_empty_albums(self, albums=None):
        if albums is None:
            to_check = set(self.get_albums())
        else:
            to_check = set()
            for album in albums:
                to_check.update(album.walk_children())

        while to_check:
            album = to_check.pop()
            if album.get_children() or album.get_photos():
                continue
            # This may have been the last child of an otherwise empty parent.
            to_check.update(album.get_parents())
            album.delete()
            yield album

####################################################################################################

class PDBBookmarkMixin:
    def __init__(self):
        super().__init__()

    def get_bookmark(self, id):
        return self.get_thing_by_id('bookmark', id)

    def get_bookmark_count(self):
        return self.sql_select_one('SELECT COUNT(id) FROM bookmarks')[0]

    def get_bookmarks(self):
        return self.get_things(thing_type='bookmark')

    def get_bookmarks_by_id(self, ids):
        return self.get_things_by_id('bookmark', ids)

    def get_bookmarks_by_sql(self, query, bindings=None):
        return self.get_things_by_sql('bookmark', query, bindings)

    @decorators.required_feature('bookmark.new')
    @decorators.transaction
    def new_bookmark(self, url, title=None, *, author=None):
        # These might raise exceptions.
        title = objects.Bookmark.normalize_title(title)
        url = objects.Bookmark.normalize_url(url)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        bookmark_id = self.generate_id(table='bookmarks')
        self.log.info('New Bookmark: %s %s %s.', bookmark_id, title, url)

        data = {
            'id': bookmark_id,
            'title': title,
            'url': url,
            'created': helpers.now(),
            'author_id': author_id,
        }
        self.sql_insert(table='bookmarks', data=data)

        bookmark = self.get_cached_instance('bookmark', data)

        return bookmark

####################################################################################################

class PDBCacheManagerMixin:
    _THING_CLASSES = {
        'album':
        {
            'class': objects.Album,
            'exception': exceptions.NoSuchAlbum,
        },
        'bookmark':
        {
            'class': objects.Bookmark,
            'exception': exceptions.NoSuchBookmark,
        },
        'photo':
        {
            'class': objects.Photo,
            'exception': exceptions.NoSuchPhoto,
        },
        'tag':
        {
            'class': objects.Tag,
            'exception': exceptions.NoSuchTag,
        },
        'user':
        {
            'class': objects.User,
            'exception': exceptions.NoSuchUser,
        }
    }

    def __init__(self):
        super().__init__()

    def clear_all_caches(self):
        self.caches['album'].clear()
        self.caches['bookmark'].clear()
        self.caches['photo'].clear()
        self.caches['tag'].clear()
        self.caches['tag_exports'].clear()
        self.caches['user'].clear()

    def get_cached_instance(self, thing_type, db_row):
        '''
        Check if there is already an instance in the cache and return that.
        Otherwise, a new instance is created, cached, and returned.

        Note that in order to call this method you have to already have a
        db_row which means performing some select. If you only have the ID,
        use get_thing_by_id, as there may already be a cached instance to save
        you the select.
        '''
        thing_map = self._THING_CLASSES[thing_type]

        thing_class = thing_map['class']
        thing_table = thing_class.table
        thing_cache = self.caches[thing_type]

        if isinstance(db_row, dict):
            thing_id = db_row['id']
        else:
            thing_index = constants.SQL_INDEX[thing_table]
            thing_id = db_row[thing_index['id']]

        try:
            thing = thing_cache[thing_id]
        except KeyError:
            self.log.loud('Cache miss %s %s.', thing_type, thing_id)
            thing = thing_class(self, db_row)
            thing_cache[thing_id] = thing
        return thing

    def get_cached_tag_export(self, function, **kwargs):
        if isinstance(function, str):
            function = getattr(tag_export, function)
        if 'tags' in kwargs:
            kwargs['tags'] = tuple(kwargs['tags'])
        key = (function.__name__,) + helpers.dict_to_tuple(kwargs)
        try:
            exp = self.caches['tag_exports'][key]
            return exp
        except KeyError:
            exp = function(**kwargs)
            if isinstance(exp, types.GeneratorType):
                exp = tuple(exp)
            self.caches['tag_exports'][key] = exp
            return exp

    def get_root_things(self, thing_type):
        '''
        For Groupable types, yield things which have no parent.
        '''
        thing_map = self._THING_CLASSES[thing_type]

        thing_class = thing_map['class']
        thing_table = thing_class.table
        group_table = thing_class.group_table

        query = f'''
        SELECT * FROM {thing_table}
        WHERE NOT EXISTS (
            SELECT 1 FROM {group_table}
            WHERE memberid == {thing_table}.id
        )
        '''

        rows = self.sql_select(query)
        for row in rows:
            thing = self.get_cached_instance(thing_type, row)
            yield thing

    def get_thing_by_id(self, thing_type, thing_id):
        '''
        This method will first check the cache to see if there is already an
        instance with that ID, in which case we don't need to perform any SQL
        select. If it is not in the cache, then a new instance is created,
        cached, and returned.
        '''
        thing_map = self._THING_CLASSES[thing_type]

        thing_class = thing_map['class']
        if isinstance(thing_id, thing_class):
            # This could be used to check if your old reference to an object is
            # still in the cache, or re-select it from the db to make sure it
            # still exists and re-cache.
            # Probably an uncommon need but... no harm I think.
            thing_id = thing_id.id

        thing_cache = self.caches[thing_type]
        try:
            return thing_cache[thing_id]
        except KeyError:
            pass

        query = f'SELECT * FROM {thing_class.table} WHERE id == ?'
        bindings = [thing_id]
        thing_row = self.sql_select_one(query, bindings)
        if thing_row is None:
            raise thing_map['exception'](thing_id)
        thing = thing_class(self, thing_row)
        thing_cache[thing_id] = thing
        return thing

    def get_things(self, thing_type):
        '''
        Yield things, unfiltered, in whatever order they appear in the database.
        '''
        thing_map = self._THING_CLASSES[thing_type]
        table = thing_map['class'].table
        query = f'SELECT * FROM {table}'

        things = self.sql_select(query)
        for thing_row in things:
            thing = self.get_cached_instance(thing_type, thing_row)
            yield thing

    def get_things_by_id(self, thing_type, thing_ids):
        '''
        Given multiple IDs, this method will find which ones are in the cache
        and which ones need to be selected from the db.
        This is better than calling get_thing_by_id in a loop because we can
        use a single SQL select to get batches of up to 999 items.

        Note: The order of the output will most likely not match the order of
        the input, because we first pull items from the cache before requesting
        the rest from the database.
        '''
        thing_map = self._THING_CLASSES[thing_type]
        thing_class = thing_map['class']
        thing_cache = self.caches[thing_type]

        ids_needed = set()
        for thing_id in thing_ids:
            try:
                thing = thing_cache[thing_id]
            except KeyError:
                ids_needed.add(thing_id)
            else:
                yield thing

        if not ids_needed:
            return

        self.log.loud('Cache miss %s %s.', thing_type, ids_needed)

        ids_needed = list(ids_needed)
        while ids_needed:
            # SQLite3 has a limit of 999 ? in a query, so we must batch them.
            id_batch = ids_needed[:999]
            ids_needed = ids_needed[999:]

            qmarks = ','.join('?' * len(id_batch))
            qmarks = f'({qmarks})'
            query = f'SELECT * FROM {thing_class.table} WHERE id IN {qmarks}'
            more_things = self.sql_select(query, id_batch)
            for thing_row in more_things:
                # Normally we would call `get_cached_instance` instead of
                # constructing here. But we already know for a fact that this
                # object is not in the cache because it made it past the
                # previous loop.
                thing = thing_class(self, db_row=thing_row)
                thing_cache[thing.id] = thing
                yield thing

    def get_things_by_sql(self, thing_type, query, bindings=None):
        '''
        Use an arbitrary SQL query to select things from the database.
        Your query select *, all the columns of the thing's table.
        '''
        thing_rows = self.sql_select(query, bindings)
        for thing_row in thing_rows:
            yield self.get_cached_instance(thing_type, thing_row)

####################################################################################################

class PDBPhotoMixin:
    def __init__(self):
        super().__init__()

    def assert_no_such_photo_by_path(self, filepath):
        try:
            existing = self.get_photo_by_path(filepath)
        except exceptions.NoSuchPhoto:
            return
        else:
            raise exceptions.PhotoExists(existing)

    def get_photo(self, id):
        return self.get_thing_by_id('photo', id)

    def get_photo_by_inode(self, dev, ino):
        dev_ino = f'{dev},{ino}'
        query = 'SELECT * FROM photos WHERE dev_ino == ?'
        bindings = [dev_ino]
        photo_row = self.sql_select_one(query, bindings)
        if photo_row is None:
            raise exceptions.NoSuchPhoto(dev_ino)
        photo = self.get_cached_instance('photo', photo_row)
        return photo

    def get_photo_by_path(self, filepath):
        filepath = pathclass.Path(filepath)
        query = 'SELECT * FROM photos WHERE filepath == ?'
        bindings = [filepath.absolute_path]
        photo_row = self.sql_select_one(query, bindings)
        if photo_row is None:
            raise exceptions.NoSuchPhoto(filepath)
        photo = self.get_cached_instance('photo', photo_row)
        return photo

    def get_photo_count(self):
        return self.sql_select_one('SELECT COUNT(id) FROM photos')[0]

    def get_photos_by_id(self, ids):
        return self.get_things_by_id('photo', ids)

    def get_photos_by_recent(self, count=None):
        '''
        Yield photo objects in order of creation time.
        '''
        if count is not None and count <= 0:
            return

        query = 'SELECT * FROM photos ORDER BY created DESC'
        photo_rows = self.sql_select(query)
        for photo_row in photo_rows:
            photo = self.get_cached_instance('photo', photo_row)
            yield photo

            if count is None:
                continue
            count -= 1
            if count <= 0:
                break

    def get_photos_by_sql(self, query, bindings=None):
        return self.get_things_by_sql('photo', query, bindings)

    @decorators.required_feature('photo.new')
    @decorators.transaction
    def new_photo(
            self,
            filepath,
            *,
            author=None,
            do_metadata=True,
            do_thumbnail=True,
            searchhidden=False,
            tags=None,
        ):
        '''
        Given a filepath, determine its attributes and create a new Photo object
        in the database. Tags may be applied now or later.

        Returns the Photo object.
        '''
        # These might raise exceptions
        filepath = pathclass.Path(filepath)
        if not filepath.is_file:
            raise FileNotFoundError(filepath.absolute_path)

        self.assert_no_such_photo_by_path(filepath=filepath)

        author_id = self.get_user_id_or_none(author)

        # Ok.
        photo_id = self.generate_id(table='photos')
        self.log.info('New Photo: %s %s.', photo_id, filepath.absolute_path)

        data = {
            'id': photo_id,
            'filepath': filepath.absolute_path,
            'basename': filepath.basename,
            'override_filename': None,
            'extension': filepath.extension.no_dot,
            'created': helpers.now(),
            'tagged_at': None,
            'author_id': author_id,
            'searchhidden': searchhidden,
            # These will be filled in during the metadata stage.
            'dev_ino': None,
            'bytes': None,
            'width': None,
            'height': None,
            'area': None,
            'ratio': None,
            'duration': None,
            'thumbnail': None,
        }
        self.sql_insert(table='photos', data=data)

        photo = self.get_cached_instance('photo', data)

        if do_metadata:
            photo.reload_metadata()
        if do_thumbnail:
            photo.generate_thumbnail()

        tags = tags or []
        tags = [self.get_tag(name=tag) for tag in tags]
        for tag in tags:
            photo.add_tag(tag)

        return photo

    @decorators.transaction
    def purge_deleted_files(self, photos=None):
        '''
        Delete Photos whose corresponding file on disk is missing.

        photos:
            An iterable of Photo objects to check.
            If not provided, all photos are checked.

        If you only want to delete photos that have not been tagged, consider
        P.purge_deleted_files(P.search(has_tags=False, is_searchhidden=None)).
        '''
        if photos is None:
            photos = self.get_photos_by_recent()

        for photo in photos:
            if photo.real_path.exists:
                continue
            photo.delete()
            yield photo

    def search(
            self,
            *,
            area=None,
            width=None,
            height=None,
            ratio=None,
            bytes=None,
            duration=None,

            author=None,
            created=None,
            extension=None,
            extension_not=None,
            filename=None,
            has_tags=None,
            has_thumbnail=None,
            is_searchhidden=False,
            mimetype=None,
            tag_musts=None,
            tag_mays=None,
            tag_forbids=None,
            tag_expression=None,
            within_directory=None,

            limit=None,
            offset=None,
            orderby=None,
            warning_bag=None,
            give_back_parameters=False,

            yield_albums=True,
            yield_photos=True,
        ):
        '''
        PHOTO PROPERTIES
        area, width, height, ratio, bytes, duration:
            A hyphen_range string representing min and max. Or just a number
            for lower bound.

        TAGS AND FILTERS
        author:
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

        has_thumbnail:
            Require a thumbnail?
            If None, anything is okay.

        is_searchhidden:
            Find photos that are marked as searchhidden?
            If True, find *only* searchhidden photos.
            If False, find *only* nonhidden photos.
            If None, either is okay.
            Default False.

        mimetype:
            A string or list of strings of acceptable mimetypes.
            'image', 'video', ...
            Note we are only interested in the simple "video", "audio" etc.
            For exact mimetypes you might as well use an extension search.

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

        within_directory:
            A string or list of strings or pathclass Paths of directories.
            Photos MUST have a `filepath` that is a child of one of these
            directories.

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

        yield_albums:
            If True, albums which contain photos matching the search will also
            be returned.
        '''
        start_time = time.time()

        maximums = {}
        minimums = {}
        searchhelpers.minmax('area', area, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('created', created, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('width', width, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('height', height, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('ratio', ratio, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('bytes', bytes, minimums, maximums, warning_bag=warning_bag)
        searchhelpers.minmax('duration', duration, minimums, maximums, warning_bag=warning_bag)

        author = searchhelpers.normalize_author(author, photodb=self, warning_bag=warning_bag)
        extension = searchhelpers.normalize_extension(extension)
        extension_not = searchhelpers.normalize_extension(extension_not)
        filename = searchhelpers.normalize_filename(filename)
        has_tags = searchhelpers.normalize_has_tags(has_tags)
        has_thumbnail = searchhelpers.normalize_has_thumbnail(has_thumbnail)
        is_searchhidden = searchhelpers.normalize_is_searchhidden(is_searchhidden)
        mimetype = searchhelpers.normalize_extension(mimetype)
        within_directory = searchhelpers.normalize_within_directory(within_directory, warning_bag=warning_bag)
        yield_albums = searchhelpers.normalize_yield_albums(yield_albums)
        yield_photos = searchhelpers.normalize_yield_photos(yield_photos)

        if has_tags is False:
            if (tag_musts or tag_mays or tag_forbids or tag_expression) and warning_bag:
                warning_bag.add("has_tags=False so all tag requests are ignored.")
            tag_musts = None
            tag_mays = None
            tag_forbids = None
            tag_expression = None
        else:
            tag_musts = searchhelpers.normalize_tagset(self, tag_musts, warning_bag=warning_bag)
            tag_mays = searchhelpers.normalize_tagset(self, tag_mays, warning_bag=warning_bag)
            tag_forbids = searchhelpers.normalize_tagset(self, tag_forbids, warning_bag=warning_bag)
            tag_expression = searchhelpers.normalize_tag_expression(tag_expression)

        if extension is not None and extension_not is not None:
            extension = extension.difference(extension_not)

        tags_fixed = searchhelpers.normalize_mmf_vs_expression_conflict(
            tag_musts,
            tag_mays,
            tag_forbids,
            tag_expression,
            warning_bag,
        )
        (tag_musts, tag_mays, tag_forbids, tag_expression) = tags_fixed

        if tag_expression:
            tag_expression_tree = searchhelpers.tag_expression_tree_builder(
                tag_expression=tag_expression,
                photodb=self,
                warning_bag=warning_bag,
            )
            if tag_expression_tree is None:
                giveback_tag_expression = None
                tag_expression = None
            else:
                giveback_tag_expression = str(tag_expression_tree)
                frozen_children = self.get_cached_tag_export('flat_dict', tags=self.get_root_tags())
                tag_match_function = searchhelpers.tag_expression_matcher_builder(frozen_children)
        else:
            giveback_tag_expression = None

        if has_tags is True and (tag_musts or tag_mays):
            # has_tags check is redundant then, so disable it.
            has_tags = None

        limit = searchhelpers.normalize_limit(limit, warning_bag=warning_bag)
        offset = searchhelpers.normalize_offset(offset, warning_bag=warning_bag)
        orderby = searchhelpers.normalize_orderby(orderby, warning_bag=warning_bag)

        if filename:
            try:
                filename_tree = expressionmatch.ExpressionTree.parse(filename)
                filename_tree.map(lambda x: x.lower())
            except expressionmatch.NoTokens:
                filename_tree = None
        else:
            filename_tree = None

        if orderby:
            giveback_orderby = [
                f'{friendly}-{direction}'
                for (friendly, expanded, direction) in orderby
            ]
            orderby = [(expanded, direction) for (friendly, expanded, direction) in orderby]
        else:
            giveback_orderby = None
            orderby = [('created', 'desc')]

        if give_back_parameters:
            parameters = {
                'area': area,
                'width': width,
                'height': height,
                'ratio': ratio,
                'bytes': bytes,
                'duration': duration,
                'author': list(author) or None,
                'created': created,
                'extension': list(extension) or None,
                'extension_not': list(extension_not) or None,
                'filename': filename or None,
                'has_tags': has_tags,
                'has_thumbnail': has_thumbnail,
                'mimetype': list(mimetype) or None,
                'tag_musts': tag_musts or None,
                'tag_mays': tag_mays or None,
                'tag_forbids': tag_forbids or None,
                'tag_expression': giveback_tag_expression or None,
                'within_directory': within_directory or None,
                'limit': limit,
                'offset': offset or None,
                'orderby': giveback_orderby,
                'yield_albums': yield_albums,
                'yield_photos': yield_photos,
            }
            yield parameters

        if not yield_albums and not yield_photos:
            exc = exceptions.NoYields(['yield_albums', 'yield_photos'])
            if warning_bag:
                warning_bag.add(exc)
                yield warning_bag
                return
            else:
                raise exceptions.NoYields(['yield_albums', 'yield_photos'])

        photo_tag_rel_exist_clauses = searchhelpers.photo_tag_rel_exist_clauses(
            tag_musts,
            tag_mays,
            tag_forbids,
        )

        notnulls = set()
        yesnulls = set()
        wheres = []
        bindings = []

        if author:
            author_ids = [user.id for user in author]
            wheres.append(f'author_id IN {sqlhelpers.listify(author_ids)}')

        if extension:
            if '*' in extension:
                wheres.append('extension != ""')
            else:
                qmarks = ', '.join('?' * len(extension))
                wheres.append(f'extension IN ({qmarks})')
                bindings.extend(extension)

        if extension_not:
            if '*' in extension_not:
                wheres.append('extension == ""')
            else:
                qmarks = ', '.join('?' * len(extension_not))
                wheres.append(f'extension NOT IN ({qmarks})')
                bindings.extend(extension_not)

        if mimetype:
            notnulls.add('extension')

        if within_directory:
            patterns = {d.absolute_path.rstrip(os.sep) for d in within_directory}
            patterns = {f'{d}{os.sep}%' for d in patterns}
            clauses = ['filepath LIKE ?'] * len(patterns)
            if len(clauses) > 1:
                clauses = ' OR '.join(clauses)
                clauses = f'({clauses})'
            else:
                clauses = clauses.pop()
            wheres.append(clauses)
            bindings.extend(patterns)

        if has_tags is True:
            wheres.append('EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')
        if has_tags is False:
            wheres.append('NOT EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')

        if yield_albums and not yield_photos:
            wheres.append('EXISTS (SELECT 1 FROM album_photo_rel WHERE photoid == photos.id)')

        if has_thumbnail is True:
            notnulls.add('thumbnail')
        elif has_thumbnail is False:
            yesnulls.add('thumbnail')

        for (column, direction) in orderby:
            if column != 'RANDOM()':
                notnulls.add(column)

        if is_searchhidden is True:
            wheres.append('searchhidden == 1')
        elif is_searchhidden is False:
            wheres.append('searchhidden == 0')

        for column in notnulls:
            wheres.append(column + ' IS NOT NULL')
        for column in yesnulls:
            wheres.append(column + ' IS NULL')

        for (column, value) in minimums.items():
            wheres.append(column + ' >= ' + str(value))

        for (column, value) in maximums.items():
            wheres.append(column + ' <= ' + str(value))

        if photo_tag_rel_exist_clauses:
            wheres.extend(photo_tag_rel_exist_clauses)

        query = ['SELECT * FROM photos']

        if wheres:
            wheres = 'WHERE ' + ' AND '.join(wheres)
            query.append(wheres)

        if orderby:
            orderby = [f'{column} {direction}' for (column, direction) in orderby]
            orderby = ', '.join(orderby)
            orderby = 'ORDER BY ' + orderby
            query.append(orderby)

        query = ' '.join(query)

        query = f'{"-" * 80}\n{query}\n{"-" * 80}'

        self.log.debug('\n%s %s', query, bindings)
        #explain = self.sql_execute('EXPLAIN QUERY PLAN ' + query, bindings)
        #print('\n'.join(str(x) for x in explain.fetchall()))
        generator = self.sql_select(query, bindings)
        seen_albums = set()
        results_received = 0
        for row in generator:
            photo = self.get_cached_instance('photo', row)

            if mimetype and photo.simple_mimetype not in mimetype:
                continue

            if filename_tree and not filename_tree.evaluate(photo.basename.lower()):
                continue

            if tag_expression:
                photo_tags = set(photo.get_tags())
                success = tag_expression_tree.evaluate(
                    photo_tags,
                    match_function=tag_match_function,
                )
                if not success:
                    continue

            if offset > 0:
                offset -= 1
                continue

            if limit is not None and results_received >= limit:
                break

            if yield_albums:
                new_albums = photo.get_containing_albums().difference(seen_albums)
                yield from new_albums
                results_received += len(new_albums)
                seen_albums.update(new_albums)

            if yield_photos:
                yield photo
                results_received += 1

        if warning_bag and warning_bag.warnings:
            yield warning_bag

        end_time = time.time()
        self.log.debug('Search took %s.', end_time - start_time)

####################################################################################################

class PDBSQLMixin:
    def __init__(self):
        super().__init__()
        self.on_commit_queue = []
        self.on_rollback_queue = []
        self.savepoints = []
        self._cached_sql_tables = None

    def assert_table_exists(self, table):
        if not self._cached_sql_tables:
            self._cached_sql_tables = self.get_sql_tables()
        if table not in self._cached_sql_tables:
            raise exceptions.BadTable(table)

    def commit(self, message=None):
        if message is not None:
            self.log.debug('Committing - %s.', message)

        while len(self.on_commit_queue) > 0:
            task = self.on_commit_queue.pop(-1)
            if isinstance(task, str):
                # savepoints.
                continue
            args = task.get('args', [])
            kwargs = task.get('kwargs', {})
            action = task['action']
            try:
                action(*args, **kwargs)
            except Exception as exc:
                self.log.debug(f'{action} raised {repr(exc)}.')
                self.rollback()
                raise

        self.savepoints.clear()
        self.sql.commit()

    def get_sql_tables(self):
        query = 'SELECT name FROM sqlite_master WHERE type = "table"'
        table_rows = self.sql_select(query)
        tables = set(name for (name,) in table_rows)
        return tables

    def release_savepoint(self, savepoint, allow_commit=False):
        '''
        Releasing a savepoint removes that savepoint from the timeline, so that
        you can no longer roll back to it. Then your choices are to commit
        everything, or roll back to a previous point. If you release the
        earliest savepoint, the database will commit.
        '''
        if savepoint not in self.savepoints:
            self.log.warn('Tried to release nonexistent savepoint %s.', savepoint)
            return

        is_commit = savepoint == self.savepoints[0]
        if is_commit and not allow_commit:
            self.log.debug('Not committing %s without allow_commit=True.', savepoint)
            return

        if is_commit:
            # We want to perform the on_commit_queue so let's use our commit
            # method instead of allowing sql's release to commit.
            self.commit()
        else:
            self.sql_execute(f'RELEASE "{savepoint}"')
            self.savepoints = helpers.slice_before(self.savepoints, savepoint)

    def rollback(self, savepoint=None):
        '''
        Given a savepoint, roll the database back to the moment before that
        savepoint was created. Keep in mind that a @transaction savepoint is
        always created *before* the method actually does anything.

        If no savepoint is provided then rollback the entire transaction.
        '''
        if savepoint is not None and savepoint not in self.savepoints:
            self.log.warn('Tried to restore nonexistent savepoint %s.', savepoint)
            return

        if len(self.savepoints) == 0:
            self.log.debug('Nothing to roll back.')
            return

        while len(self.on_rollback_queue) > 0:
            task = self.on_rollback_queue.pop(-1)
            if task == savepoint:
                break
            if isinstance(task, str):
                # Intermediate savepoints.
                continue
            args = task.get('args', [])
            kwargs = task.get('kwargs', {})
            task['action'](*args, **kwargs)

        if savepoint is not None:
            self.log.debug('Rolling back to %s.', savepoint)
            self.sql_execute(f'ROLLBACK TO "{savepoint}"')
            self.savepoints = helpers.slice_before(self.savepoints, savepoint)
            self.on_commit_queue = helpers.slice_before(self.on_commit_queue, savepoint)

        else:
            self.log.debug('Rolling back.')
            self.sql_execute('ROLLBACK')
            self.savepoints.clear()
            self.on_commit_queue.clear()

    def savepoint(self, message=None):
        savepoint_id = passwordy.random_hex(length=16)
        if message:
            self.log.log(5, 'Savepoint %s for %s.', savepoint_id, message)
        else:
            self.log.log(5, 'Savepoint %s.', savepoint_id)
        query = f'SAVEPOINT "{savepoint_id}"'
        self.sql_execute(query)
        self.savepoints.append(savepoint_id)
        self.on_commit_queue.append(savepoint_id)
        self.on_rollback_queue.append(savepoint_id)
        return savepoint_id

    def sql_delete(self, table, pairs):
        self.assert_table_exists(table)
        (qmarks, bindings) = sqlhelpers.delete_filler(pairs)
        query = f'DELETE FROM {table} {qmarks}'
        self.sql_execute(query, bindings)

    def sql_execute(self, query, bindings=[]):
        if bindings is None:
            bindings = []
        cur = self.sql.cursor()
        self.log.loud(f'{query} {bindings}')
        cur.execute(query, bindings)
        return cur

    def sql_executescript(self, script):
        '''
        The problem with Python's default executescript is that it executes a
        COMMIT before running your script. If I wanted a commit I'd write one!
        '''
        lines = re.split(r';(:?\n|$)', script)
        lines = (line.strip() for line in lines)
        lines = (line for line in lines if line)
        cur = self.sql.cursor()
        for line in lines:
            self.log.loud(line)
            cur.execute(line)

    def sql_insert(self, table, data):
        self.assert_table_exists(table)
        column_names = constants.SQL_COLUMNS[table]
        (qmarks, bindings) = sqlhelpers.insert_filler(column_names, data)

        query = f'INSERT INTO {table} VALUES({qmarks})'
        self.sql_execute(query, bindings)

    def sql_select(self, query, bindings=None):
        cur = self.sql_execute(query, bindings)
        while True:
            fetch = cur.fetchone()
            if fetch is None:
                break
            yield fetch

    def sql_select_one(self, query, bindings=None):
        cur = self.sql_execute(query, bindings)
        return cur.fetchone()

    def sql_update(self, table, pairs, where_key):
        self.assert_table_exists(table)
        (qmarks, bindings) = sqlhelpers.update_filler(pairs, where_key=where_key)
        query = f'UPDATE {table} {qmarks}'
        self.sql_execute(query, bindings)

####################################################################################################

class PDBTagMixin:
    def __init__(self):
        super().__init__()

    def assert_no_such_tag(self, name):
        try:
            existing_tag = self.get_tag_by_name(name)
        except exceptions.NoSuchTag:
            return
        else:
            raise exceptions.TagExists(existing_tag)

    def _get_all_tag_names(self):
        query = 'SELECT name FROM tags'
        tag_rows = self.sql_select(query)
        names = set(name for (name,) in tag_rows)
        return names

    def get_all_tag_names(self):
        '''
        Return a list containing the names of all tags as strings.
        Useful for when you don't want the overhead of actual Tag objects.
        '''
        return self.get_cached_tag_export(self._get_all_tag_names)

    def _get_all_synonyms(self):
        query = 'SELECT name, mastername FROM tag_synonyms'
        syn_rows = self.sql_select(query)
        synonyms = {syn: tag for (syn, tag) in syn_rows}
        return synonyms

    def get_all_synonyms(self):
        '''
        Return a dict mapping {synonym: mastertag} as strings.
        '''
        return self.get_cached_tag_export(self._get_all_synonyms)

    def get_root_tags(self):
        '''
        Yield Tags that have no parent.
        '''
        return self.get_root_things('tag')

    def get_tag(self, name=None, id=None):
        '''
        Redirect to get_tag_by_id or get_tag_by_name.
        '''
        if not helpers.is_xor(id, name):
            raise exceptions.NotExclusive(['id', 'name'])

        if id is not None:
            return self.get_tag_by_id(id)
        else:
            return self.get_tag_by_name(name)

    def get_tag_by_id(self, id):
        return self.get_thing_by_id('tag', thing_id=id)

    def get_tag_by_name(self, tagname):
        if isinstance(tagname, objects.Tag):
            if tagname.photodb == self:
                return tagname
            tagname = tagname.name

        try:
            # TODO: this logic is flawed because tags that were created in
            # the past may have had different normalization.
            # At the same time, I don't want to just pass the input directly
            # into the query, we should still do SOME assumed normalization
            # like whitespace strip.
            tagname = self.normalize_tagname(tagname)
        except (exceptions.TagTooShort, exceptions.TagTooLong):
            raise exceptions.NoSuchTag(tagname)

        while True:
            # Return if it's a toplevel...
            tag_row = self.sql_select_one('SELECT * FROM tags WHERE name == ?', [tagname])
            if tag_row is not None:
                break

            # ...or resolve the synonym and try again.
            query = 'SELECT mastername FROM tag_synonyms WHERE name == ?'
            bindings = [tagname]
            name_row = self.sql_select_one(query, bindings)
            if name_row is None:
                # was not a master tag or synonym
                raise exceptions.NoSuchTag(tagname)
            tagname = name_row[0]

        tag = self.get_cached_instance('tag', tag_row)
        return tag

    def get_tag_count(self):
        return self.sql_select_one('SELECT COUNT(id) FROM tags')[0]

    def get_tags(self):
        '''
        Yield all Tags in the database.
        '''
        return self.get_things(thing_type='tag')

    def get_tags_by_id(self, ids):
        return self.get_things_by_id('tag', ids)

    def get_tags_by_sql(self, query, bindings=None):
        return self.get_things_by_sql('tag', query, bindings)

    @decorators.required_feature('tag.new')
    @decorators.transaction
    def new_tag(self, tagname, description=None, *, author=None):
        '''
        Register a new tag and return the Tag object.
        '''
        # These might raise exceptions.
        tagname = self.normalize_tagname(tagname)
        self.assert_no_such_tag(name=tagname)

        description = objects.Tag.normalize_description(description)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        tag_id = self.generate_id(table='tags')
        self.log.info('New Tag: %s %s.', tag_id, tagname)

        self.caches['tag_exports'].clear()

        data = {
            'id': tag_id,
            'name': tagname,
            'description': description,
            'created': helpers.now(),
            'author_id': author_id,
        }
        self.sql_insert(table='tags', data=data)

        tag = self.get_cached_instance('tag', data)

        return tag

    def normalize_tagname(self, tagname):
        tagname = objects.Tag.normalize_name(
            tagname,
            # valid_chars=self.config['tag']['valid_chars'],
            min_length=self.config['tag']['min_length'],
            max_length=self.config['tag']['max_length'],
        )
        return tagname

####################################################################################################

class PDBUserMixin:
    def __init__(self):
        super().__init__()

    def assert_no_such_user(self, username):
        try:
            existing_user = self.get_user(username=username)
        except exceptions.NoSuchUser:
            return
        else:
            raise exceptions.UserExists(existing_user)

    def assert_valid_password(self, password):
        if not isinstance(password, bytes):
            raise TypeError(f'Password must be {bytes}, not {type(password)}.')

        if len(password) < self.config['user']['min_password_length']:
            raise exceptions.PasswordTooShort(min_length=self.config['user']['min_password_length'])

    def assert_valid_username(self, username):
        if not isinstance(username, str):
            raise TypeError(f'Username must be {str}, not {type(username)}.')

        if len(username) < self.config['user']['min_username_length']:
            raise exceptions.UsernameTooShort(
                username=username,
                min_length=self.config['user']['min_username_length']
            )

        if len(username) > self.config['user']['max_username_length']:
            raise exceptions.UsernameTooLong(
                username=username,
                max_length=self.config['user']['max_username_length']
            )

        badchars = [c for c in username if c not in self.config['user']['valid_chars']]
        if badchars:
            raise exceptions.InvalidUsernameChars(username=username, badchars=badchars)

    def generate_user_id(self):
        '''
        User IDs are randomized instead of integers like the other objects,
        so they get their own method.
        '''
        length = self.config['id_length']
        for retry in range(20):
            user_id = (random.choice(constants.USER_ID_CHARACTERS) for x in range(length))
            user_id = ''.join(user_id)

            user_exists = self.sql_select_one('SELECT 1 FROM users WHERE id == ?', [user_id])
            if user_exists is None:
                break
        else:
            raise Exception('Failed to create user id after 20 tries.')

        return user_id

    def get_user(self, username=None, id=None):
        '''
        Redirect to get_user_by_id or get_user_by_username.
        '''
        if not helpers.is_xor(id, username):
            raise exceptions.NotExclusive(['id', 'username'])

        if id:
            return self.get_user_by_id(id)
        else:
            return self.get_user_by_username(username)

    def get_user_by_id(self, id):
        return self.get_thing_by_id('user', id)

    def get_user_by_username(self, username):
        user_row = self.sql_select_one('SELECT * FROM users WHERE username == ?', [username])

        if user_row is None:
            raise exceptions.NoSuchUser(username)

        return self.get_cached_instance('user', user_row)

    def get_user_count(self):
        return self.sql_select_one('SELECT COUNT(id) FROM users')[0]

    def get_user_id_or_none(self, user_obj_or_id):
        '''
        For methods that create photos, albums, etc., we sometimes associate
        them with an author but sometimes not. The callers of those methods
        might be trying to submit a User object, or a user's ID, or maybe they
        left it None.
        This method converts those inputs into a User's ID if possible, or else
        returns None, hiding validation that those methods would otherwise have
        to duplicate.
        Exceptions like NoSuchUser can still be raised if the input appears to
        be workable but fails.
        '''
        if user_obj_or_id is None:
            return None

        elif isinstance(user_obj_or_id, objects.User):
            if user_obj_or_id.photodb != self:
                raise ValueError('That user does not belong to this photodb.')
            author_id = user_obj_or_id.id

        elif isinstance(user_obj_or_id, str):
            # Confirm that this string is a valid ID and not junk.
            author_id = self.get_user(id=user_obj_or_id).id

        else:
            raise TypeError(f'Unworkable type {type(user_obj_or_id)}.')

        return author_id

    def get_users(self):
        return self.get_things('user')

    def get_users_by_id(self, ids):
        return self.get_things_by_id('user', ids)

    def get_users_by_sql(self, query, bindings=None):
        return self.get_things_by_sql('user', query, bindings)

    @decorators.required_feature('user.login')
    def login(self, username=None, id=None, *, password):
        '''
        Return the User object for the user if the credentials are correct.
        '''
        try:
            user = self.get_user(username=username, id=id)
        except exceptions.NoSuchUser:
            raise exceptions.WrongLogin()

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        success = bcrypt.checkpw(password, user.password_hash)
        if not success:
            raise exceptions.WrongLogin()

        return user

    @decorators.required_feature('user.new')
    @decorators.transaction
    def new_user(self, username, password, *, display_name=None):
        # These might raise exceptions.
        self.assert_valid_username(username)
        self.assert_no_such_user(username=username)

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        self.assert_valid_password(password)

        display_name = objects.User.normalize_display_name(
            display_name,
            max_length=self.config['user']['max_display_name_length'],
        )

        # Ok.
        user_id = self.generate_user_id()
        self.log.info('New User: %s %s.', user_id, username)

        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        data = {
            'id': user_id,
            'username': username,
            'password': hashed_password,
            'display_name': display_name,
            'created': helpers.now(),
        }
        self.sql_insert(table='users', data=data)

        return self.get_cached_instance('user', data)

####################################################################################################

class PDBUtilMixin:
    def __init__(self):
        super().__init__()

    @decorators.transaction
    def digest_directory(
            self,
            directory,
            *,
            exclude_directories=None,
            exclude_filenames=None,
            make_albums=True,
            natural_sort=True,
            new_photo_kwargs={},
            new_photo_ratelimit=None,
            recurse=True,
            yield_albums=True,
            yield_photos=True,
        ):
        '''
        Walk the directory and create Photos for every file.

        If a Photo object already exists for a file, it will be added to the
        correct album.

        exclude_directories:
            A list of basenames or absolute paths of directories to ignore.
            This list works in addition to, not instead of, the
            digest_exclude_dirs config value.

        exclude_filenames:
            A list of basenames or absolute paths of filenames to ignore.
            This list works in addition to, not instead of, the
            digest_exclude_files config value.

        make_albums:
            If True, every directory that is digested will be turned into an
            Album, and the directory path will be added to the Album's
            associated_directories list. Child directories will become child
            albums.
            If there already exists an Album associated with the directory,
            the newly digested photos will be added to that album.
            Because album/directory relationships are not unique, there might
            be multiple albums associated with a directory, in which case they
            will all get the photos.

        natural_sort:
            If True, the list of files will be natural sorted before digest.
            This way, the `created` timestamps on every Photo correspond to the
            same order that the files are listed when natural sorted. This is
            essentially an aesthetic preference, that when you are viewing the
            photos sorted by timestamp they are also natural sorted.
            See helpers.natural_sorter.

        new_photo_kwargs:
            A dict of kwargs to pass into every call of new_photo.

        new_photo_ratelimit:
            A ratelimiter.Ratelimiter object, or an int/float number of seconds
            to wait between every photo digest.
            It is worth noting that timestamp resolution / accuracy varies by
            system. If you digest photos very quickly, you might have many with
            the exact same created timestamp. This doesn't cause any technical
            problems, but it is another somewhat aesthetic choice. If you start
            with with a reference photo and then query
            `SELECT FROM photos WHERE created > reference`, you could miss
            several photos with the exact same timestamp, unless you use >= and
            then ignore the reference photo.

        recurse:
            If True, walk the whole directory tree. If False, only digest the
            photos from the given directory and not its subdirectories.

        yield_albums:
            If True, yield Albums as they are processed, new or not.

        yield_photos:
            If True, yield Photos as they are processed, new or not.
        '''
        def _normalize_directory(directory):
            directory = pathclass.Path(directory)
            directory.assert_is_directory()
            directory.correct_case()
            return directory

        def _normalize_exclude_directories(exclude_directories):
            exclude_directories = exclude_directories or []
            exclude_directories.extend(self.config['digest_exclude_dirs'])
            return exclude_directories

        def _normalize_exclude_filenames(exclude_filenames):
            exclude_filenames = exclude_filenames or []
            exclude_filenames.extend(self.config['digest_exclude_files'])
            return exclude_filenames

        def _normalize_new_photo_kwargs(new_photo_kwargs):
            new_photo_kwargs = new_photo_kwargs.copy()
            new_photo_kwargs.pop('commit', None)
            new_photo_kwargs.pop('filepath', None)
            return new_photo_kwargs

        def _normalize_new_photo_ratelimit(new_photo_ratelimit):
            if new_photo_ratelimit is None:
                pass
            elif isinstance(new_photo_ratelimit, ratelimiter.Ratelimiter):
                pass
            elif isinstance(new_photo_ratelimit, (int, float)):
                new_photo_ratelimit = ratelimiter.Ratelimiter(allowance=1, period=new_photo_ratelimit)
            else:
                raise TypeError(new_photo_ratelimit)
            return new_photo_ratelimit

        def check_renamed_inode(filepath):
            stat = filepath.stat
            (dev, ino) = (stat.st_dev, stat.st_ino)
            if dev == 0 or ino == 0:
                return

            try:
                photo = self.get_photo_by_inode(dev, ino)
            except exceptions.NoSuchPhoto:
                return

            if photo.bytes != stat.st_size:
                return

            photo.relocate(filepath.absolute_path)
            return photo

        def create_or_fetch_photo(filepath, new_photo_kwargs):
            '''
            Given a filepath, find the corresponding Photo object if it exists,
            otherwise create it and then return it.
            '''
            try:
                photo = self.get_photo_by_path(filepath)
            except exceptions.NoSuchPhoto:
                photo = None
            if not photo:
                photo = check_renamed_inode(filepath)
            if not photo:
                photo = self.new_photo(filepath.absolute_path, **new_photo_kwargs)
                if new_photo_ratelimit is not None:
                    new_photo_ratelimit.limit()

            return photo

        def create_or_fetch_current_albums(albums_by_path, current_directory):
            current_albums = albums_by_path.get(current_directory.absolute_path, None)
            if current_albums is not None:
                return current_albums

            current_albums = list(self.get_albums_by_path(current_directory.absolute_path))
            if not current_albums:
                current_albums = [self.new_album(
                    associated_directories=current_directory.absolute_path,
                    title=current_directory.basename,
                )]

            albums_by_path[current_directory.absolute_path] = current_albums
            return current_albums

        def orphan_join_parent_albums(albums_by_path, current_albums, current_directory):
            '''
            If the current album is an orphan, let's check if there exists an
            album for the parent directory. If so, add the current album to it.
            '''
            orphans = [album for album in current_albums if not album.has_any_parent()]
            if not orphans:
                return

            parents = albums_by_path.get(current_directory.parent.absolute_path, None)
            if not parents:
                return

            for parent in parents:
                parent.add_children(orphans)

        directory = _normalize_directory(directory)
        exclude_directories = _normalize_exclude_directories(exclude_directories)
        exclude_filenames = _normalize_exclude_filenames(exclude_filenames)
        new_photo_kwargs = _normalize_new_photo_kwargs(new_photo_kwargs)
        new_photo_ratelimit = _normalize_new_photo_ratelimit(new_photo_ratelimit)

        albums_by_path = {}

        self.log.info('Digesting directory "%s".', directory.absolute_path)
        walk_generator = spinal.walk_generator(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            recurse=recurse,
            yield_style='nested',
        )

        for (current_directory, subdirectories, files) in walk_generator:
            if natural_sort:
                files = sorted(files, key=lambda f: helpers.natural_sorter(f.basename))

            photos = [create_or_fetch_photo(file, new_photo_kwargs=new_photo_kwargs) for file in files]

            if yield_photos:
                yield from photos

            if not make_albums:
                continue

            current_albums = create_or_fetch_current_albums(albums_by_path, current_directory)
            orphan_join_parent_albums(albums_by_path, current_albums, current_directory)

            for album in current_albums:
                album.add_photos(photos)

            if yield_albums:
                yield from current_albums

    @decorators.transaction
    def easybake(self, ebstring, author=None):
        '''
        Easily create tags, groups, and synonyms with a string like
        "group1.group2.tag+synonym"
        "family.parents.dad+father"
        etc
        '''
        output_notes = []

        def create_or_get(name):
            try:
                item = self.get_tag(name=name)
                note = ('existing_tag', item.name)
            except exceptions.NoSuchTag:
                item = self.new_tag(name, author=author)
                note = ('new_tag', item.name)
            output_notes.append(note)
            return item

        (tagname, synonym, rename_to) = helpers.split_easybake_string(ebstring)

        if rename_to:
            tag = self.get_tag(name=tagname)
            old_name = tag.name
            tag.rename(rename_to)
            note = ('rename_tag', f'{old_name}={tag.name}')
            output_notes.append(note)
        else:
            tag_parts = tagname.split('.')
            tags = [create_or_get(t) for t in tag_parts]
            for (higher, lower) in zip(tags, tags[1:]):
                try:
                    higher.add_child(lower)
                    note = ('join_group', f'{higher.name}.{lower.name}')
                    output_notes.append(note)
                except exceptions.GroupExists:
                    pass
            tag = tags[-1]

        if synonym:
            synonym = tag.add_synonym(synonym)
            note = ('add_synonym', f'{tag.name}+{synonym}')
            output_notes.append(note)

        return output_notes

####################################################################################################

class PhotoDB(
        PDBAlbumMixin,
        PDBBookmarkMixin,
        PDBCacheManagerMixin,
        PDBPhotoMixin,
        PDBSQLMixin,
        PDBTagMixin,
        PDBUserMixin,
        PDBUtilMixin,
    ):
    def __init__(
            self,
            data_directory=None,
            *,
            create=True,
            ephemeral=False,
            log_level=vlogging.NOTSET,
            skip_version_check=False,
        ):
        '''
        data_directory:
            This directory will contain the sql file, config file,
            generated thumbnails, etc. The directory is the database for all
            intents and purposes.

        create:
            If True, the data_directory will be created if it does not exist.
            If False, we expect that data_directory and the sql file exist.

        ephemeral:
            Use an in-memory sql database, and a temporary directory for
            everything else, so that the whole PhotoDB disappears after closing.
            Requires that data_directory=None.

        skip_version_check:
            Skip the version check so that you don't get DatabaseOutOfDate.
            Beware of modifying any data in this state.
        '''
        super().__init__()

        ephemeral = bool(ephemeral)
        if data_directory is not None and ephemeral:
            raise exceptions.NotExclusive(['data_directory', 'ephemeral'])

        self.ephemeral = ephemeral

        # DATA DIR PREP
        if data_directory is not None:
            pass
        elif self.ephemeral:
            # In addition to the data_dir as a pathclass object, keep the
            # TempDir object so we can use the cleanup method later.
            self.ephemeral_directory = tempfile.TemporaryDirectory(prefix='etiquette_ephem_')
            data_directory = self.ephemeral_directory.name
        else:
            data_directory = constants.DEFAULT_DATADIR

        if isinstance(data_directory, str):
            data_directory = helpers.remove_path_badchars(data_directory, allowed=':/\\')
        self.data_directory = pathclass.Path(data_directory)

        if self.data_directory.exists and not self.data_directory.is_dir:
            raise exceptions.BadDataDirectory(self.data_directory.absolute_path)

        # LOGGING
        self.log = vlogging.getLogger(f'{__name__}:{self.data_directory.absolute_path}')
        self.log.setLevel(log_level)

        # DATABASE
        if self.ephemeral:
            existing_database = False
            self.sql = sqlite3.connect(':memory:')
        else:
            self.database_filepath = self.data_directory.with_child(constants.DEFAULT_DBNAME)
            existing_database = self.database_filepath.exists

            if not existing_database and not create:
                msg = f'"{self.database_filepath.absolute_path}" does not exist and create is off.'
                raise FileNotFoundError(msg)

            self.data_directory.makedirs(exist_ok=True)
            self.sql = sqlite3.connect(self.database_filepath.absolute_path)

        if existing_database:
            if not skip_version_check:
                self._check_version()
            self._load_pragmas()
        else:
            self._first_time_setup()

        # THUMBNAIL DIRECTORY
        self.thumbnail_directory = self.data_directory.with_child(constants.DEFAULT_THUMBDIR)
        self.thumbnail_directory.makedirs(exist_ok=True)

        # CONFIG
        self.config_filepath = self.data_directory.with_child(constants.DEFAULT_CONFIGNAME)
        self.load_config()

        self.caches = {
            'album': cacheclass.Cache(maxlen=self.config['cache_size']['album']),
            'bookmark': cacheclass.Cache(maxlen=self.config['cache_size']['bookmark']),
            'photo': cacheclass.Cache(maxlen=self.config['cache_size']['photo']),
            'tag': cacheclass.Cache(maxlen=self.config['cache_size']['tag']),
            'tag_exports': cacheclass.Cache(maxlen=100),
            'user': cacheclass.Cache(maxlen=self.config['cache_size']['user']),
        }

    def _check_version(self):
        '''
        Compare database's user_version against constants.DATABASE_VERSION,
        raising exceptions.DatabaseOutOfDate if not correct.
        '''
        existing = self.sql_execute('PRAGMA user_version').fetchone()[0]
        if existing != constants.DATABASE_VERSION:
            raise exceptions.DatabaseOutOfDate(
                existing=existing,
                new=constants.DATABASE_VERSION,
                filepath=self.data_directory,
            )

    def _first_time_setup(self):
        self.log.info('Running first-time database setup.')
        self.sql_executescript(constants.DB_INIT)
        self.sql.commit()

    def _load_pragmas(self):
        self.log.debug('Reloading pragmas.')
        self.sql_executescript(constants.DB_PRAGMAS)
        self.sql.commit()

    def __del__(self):
        self.close()

    def __repr__(self):
        if self.ephemeral:
            return 'PhotoDB(ephemeral=True)'
        else:
            return f'PhotoDB(data_directory={self.data_directory})'

    def close(self):
        # Wrapped in hasattr because if the object fails __init__, Python will
        # still call __del__ and thus close(), even though the attributes
        # we're trying to clean up never got set.
        if hasattr(self, 'sql'):
            self.sql.close()

        if getattr(self, 'ephemeral', False):
            self.ephemeral_directory.cleanup()

    def generate_id(self, table):
        '''
        Create a new ID number that is unique to the given table.
        Note that while this method may INSERT / UPDATE, it does not commit.
        We'll wait for that to happen in whoever is calling us, so we know the
        ID is actually used.
        '''
        table = table.lower()
        if table not in ['photos', 'tags', 'albums', 'bookmarks']:
            raise ValueError(f'Invalid table requested: {table}.')

        last_id = self.sql_select_one('SELECT last_id FROM id_numbers WHERE tab == ?', [table])
        if last_id is None:
            # Register new value
            new_id_int = 1
            do_insert = True
        else:
            # Use database value
            new_id_int = int(last_id[0]) + 1
            do_insert = False

        new_id = str(new_id_int).rjust(self.config['id_length'], '0')

        pairs = {
            'tab': table,
            'last_id': new_id,
        }
        if do_insert:
            self.sql_insert(table='id_numbers', data=pairs)
        else:
            self.sql_update(table='id_numbers', pairs=pairs, where_key='tab')
        return new_id

    def load_config(self):
        (config, needs_rewrite) = configlayers.load_file(
            filepath=self.config_filepath,
            defaults=constants.DEFAULT_CONFIGURATION,
        )
        self.config = config

        if needs_rewrite:
            self.save_config()

    def save_config(self):
        with self.config_filepath.open('w', encoding='utf-8') as handle:
            handle.write(json.dumps(self.config, indent=4, sort_keys=True))
