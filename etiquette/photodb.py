import bcrypt
import copy
import json
import logging
import os
import random
import sqlite3
import string
import tempfile
import time

from . import constants
from . import decorators
from . import exceptions
from . import helpers
from . import objects
from . import searchhelpers
from . import tag_export

from voussoirkit import cacheclass
from voussoirkit import expressionmatch
from voussoirkit import pathclass
from voussoirkit import ratelimiter
from voussoirkit import spinal
from voussoirkit import sqlhelpers


logging.basicConfig()


####################################################################################################
####################################################################################################


class PDBAlbumMixin:
    def __init__(self):
        super().__init__()

    def get_album(self, id=None, path=None):
        if not helpers.is_xor(id, path):
            raise exceptions.NotExclusive(['id', 'path'])

        if id is not None:
            return self.get_album_by_id(id)
        else:
            return self.get_album_by_path(path)

    def get_album_by_id(self, id):
        return self.get_thing_by_id('album', id)

    def get_album_by_path(self, filepath):
        '''
        Return the album with the `associated_directory` of this value,
        NOT case-sensitive.
        '''
        filepath = pathclass.Path(filepath).absolute_path
        query = 'SELECT albumid FROM album_associated_directories WHERE directory == ?'
        bindings = [filepath]
        album_row = self.sql_select_one(query, bindings)
        if album_row is None:
            raise exceptions.NoSuchAlbum(filepath)
        album_id = album_row[0]
        return self.get_album(album_id)

    def get_albums(self):
        yield from self.get_things(thing_type='album')

    def get_albums_by_id(self, ids):
        return self.get_things_by_id('album', ids)

    def get_root_albums(self):
        '''
        Yield Albums that have no parent.
        '''
        yield from self.get_root_things('album')

    @decorators.required_feature('album.new')
    @decorators.transaction
    def new_album(
            self,
            title=None,
            description=None,
            *,
            associated_directory=None,
            author=None,
            commit=True,
            photos=None,
        ):
        '''
        Create a new album. Photos can be added now or later.
        '''
        title = objects.Album.normalize_title(title)
        description = objects.Album.normalize_description(description)

        album_id = self.generate_id('albums')

        self.log.debug('New Album: %s %s', album_id, title)

        author_id = self.get_user_id_or_none(author)

        data = {
            'id': album_id,
            'title': title,
            'description': description,
            'author_id': author_id,
        }
        self.sql_insert(table='albums', data=data)

        album = self.get_cached_instance('album', data)

        if associated_directory is not None:
            album.add_associated_directory(associated_directory, commit=False)

        if photos is not None:
            photos = [self.get_photo(photo) for photo in photos]
            album.add_photos(photos, commit=False)

        if commit:
            self.log.debug('Committing - new Album')
            self.commit()
        return album


class PDBBookmarkMixin:
    def __init__(self):
        super().__init__()

    def get_bookmark(self, id):
        return self.get_thing_by_id('bookmark', id)

    def get_bookmarks(self):
        yield from self.get_things(thing_type='bookmark')

    def get_bookmarks_by_id(self, ids):
        return self.get_things_by_id('bookmark', ids)

    @decorators.required_feature('bookmark.new')
    @decorators.transaction
    def new_bookmark(self, url, title=None, *, author=None, commit=True):
        title = objects.Bookmark.normalize_title(title)
        url = objects.Bookmark.normalize_url(url)

        bookmark_id = self.generate_id('bookmarks')
        author_id = self.get_user_id_or_none(author)

        data = {
            'author_id': author_id,
            'id': bookmark_id,
            'title': title,
            'url': url,
        }
        self.sql_insert(table='bookmarks', data=data)

        bookmark = self.get_cached_instance('bookmark', data)
        if commit:
            self.log.debug('Committing - new Bookmark')
            self.commit()
        return bookmark


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

    def get_photo_by_path(self, filepath):
        filepath = pathclass.Path(filepath)
        query = 'SELECT * FROM photos WHERE filepath == ?'
        bindings = [filepath.absolute_path]
        photo_row = self.sql_select_one(query, bindings)
        if photo_row is None:
            raise exceptions.NoSuchPhoto(filepath)
        photo = self.get_cached_instance('photo', photo_row)
        return photo

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

    @decorators.required_feature('photo.new')
    @decorators.transaction
    def new_photo(
            self,
            filepath,
            *,
            allow_duplicates=False,
            author=None,
            commit=True,
            do_metadata=True,
            do_thumbnail=True,
            tags=None,
        ):
        '''
        Given a filepath, determine its attributes and create a new Photo object
        in the database. Tags may be applied now or later.

        If `allow_duplicates` is False, we will first check the database for any
        files with the same path and raise exceptions.PhotoExists if found.

        Returns the Photo object.
        '''
        filepath = pathclass.Path(filepath)
        if not filepath.is_file:
            raise FileNotFoundError(filepath.absolute_path)

        if not allow_duplicates:
            self.assert_no_such_photo_by_path(filepath=filepath)

        self.log.debug('New Photo: %s', filepath.absolute_path)
        author_id = self.get_user_id_or_none(author)

        created = helpers.now()
        photo_id = self.generate_id('photos')

        data = {
            'id': photo_id,
            'filepath': filepath.absolute_path,
            'override_filename': None,
            'extension': filepath.extension,
            'created': created,
            'tagged_at': None,
            'author_id': author_id,
            'searchhidden': False,
            # These will be filled in during the metadata stage.
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
            photo.reload_metadata(commit=False)
        if do_thumbnail:
            photo.generate_thumbnail(commit=False)

        tags = tags or []
        tags = [self.get_tag(name=tag) for tag in tags]
        for tag in tags:
            photo.add_tag(tag, commit=False)

        if commit:
            self.log.debug('Committing - new_photo')
            self.commit()
        return photo

    @decorators.transaction
    def purge_deleted_files(self, photos=None, *, commit=True):
        '''
        Remove Photo entries if their corresponding file is no longer found.

        photos: An iterable of Photo objects to check.
        If not provided, everything is checked.
        '''
        if photos is None:
            photos = self.get_photos_by_recent()

        for photo in photos:
            if photo.real_path.exists:
                continue
            photo.delete(commit=False)

        if commit:
            self.log.debug('Committing - purge deleted photos')
            self.commit()

    @decorators.transaction
    def purge_empty_albums(self, albums=None, *, commit=True):
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

        if has_tags is False:
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
            frozen_children = self.get_cached_frozen_children()
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

        giveback_orderby = [
            '%s-%s' % (column.replace('RANDOM()', 'random'), direction)
            for (column, direction) in orderby
        ]

        if not orderby:
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
                'limit': limit,
                'offset': offset or None,
                'orderby': giveback_orderby,
            }
            yield parameters

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
            wheres.append('author_id IN %s' % helpers.sql_listify(author_ids))

        if extension:
            if '*' in extension:
                wheres.append('extension != ""')
            else:
                qmarks = ', '.join('?' * len(extension))
                wheres.append('extension IN (%s)' % qmarks)
                bindings.extend(extension)

        if extension_not:
            if '*' in extension_not:
                wheres.append('extension == ""')
            else:
                qmarks = ', '.join('?' * len(extension_not))
                wheres.append('extension NOT IN (%s)' % qmarks)
                bindings.extend(extension_not)

        if mimetype:
            notnulls.add('extension')

        if has_tags is True:
            wheres.append('EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')
        if has_tags is False:
            wheres.append('NOT EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')

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
            orderby = ['%s %s' % (column, direction) for (column, direction) in orderby]
            orderby = ', '.join(orderby)
            orderby = 'ORDER BY ' + orderby
            query.append(orderby)

        query = ' '.join(query)

        query = f'{"-" * 80}\n{query}\n{"-" * 80}'

        print(query, bindings)
        #explain = self.sql_execute('EXPLAIN QUERY PLAN ' + query, bindings)
        #print('\n'.join(str(x) for x in explain.fetchall()))
        generator = self.sql_select(query, bindings)
        photos_received = 0
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

            if limit is not None and photos_received >= limit:
                break

            photos_received += 1
            yield photo

        if warning_bag and warning_bag.warnings:
            yield warning_bag

        end_time = time.time()
        print('Search took:', end_time - start_time)


class PDBSQLMixin:
    def __init__(self):
        super().__init__()
        self.on_commit_queue = []
        self.savepoints = []

    def commit(self):
        while len(self.on_commit_queue) > 0:
            task = self.on_commit_queue.pop()
            if isinstance(task, str):
                continue
            args = task.get('args', [])
            kwargs = task.get('kwargs', {})
            task['action'](*args, **kwargs)
        self.savepoints.clear()
        self.sql.commit()

    def rollback(self, savepoint=None):
        '''
        Given a savepoint, roll the database back to the moment before that
        savepoint was created. Keep in mind that a @transaction savepoint is
        always created *before* the method actually does anything.

        If no savepoint is provided then just roll back the most recent save.
        '''
        if savepoint is None:
            try:
                savepoint = self.savepoints.pop(-1)
            except IndexError:
                self.log.debug('Nothing to roll back.')
                return
        else:
            try:
                # Will reassign after everything goes well.
                _savepoints = helpers.slice_before(self.savepoints, savepoint)
            except ValueError:
                self.log.warn('Tried to restore nonexistent savepoint %s.', savepoint)
                return

        self.log.debug('Rolling back to %s', savepoint)
        query = 'ROLLBACK TO "%s"' % savepoint
        self.sql_execute(query)
        self.savepoints = _savepoints
        self.on_commit_queue = helpers.slice_before(self.on_commit_queue, savepoint)

    def savepoint(self, message=None):
        savepoint_id = helpers.random_hex(length=16)
        if message:
            self.log.debug('Savepoint %s for %s.', savepoint_id, message)
        else:
            self.log.debug('Savepoint %s.', savepoint_id)
        query = 'SAVEPOINT "%s"' % savepoint_id
        self.sql.execute(query)
        self.savepoints.append(savepoint_id)
        self.on_commit_queue.append(savepoint_id)
        return savepoint_id

    def sql_delete(self, table, pairs):
        (qmarks, bindings) = sqlhelpers.delete_filler(pairs)
        query = 'DELETE FROM %s %s' % (table, qmarks)
        self.sql_execute(query, bindings)

    def sql_execute(self, query, bindings=[]):
        if bindings is None:
            bindings = []
        cur = self.sql.cursor()
        cur.execute(query, bindings)
        return cur

    def sql_insert(self, table, data):
        column_names = constants.SQL_COLUMNS[table]
        (qmarks, bindings) = sqlhelpers.insert_filler(column_names, data)

        query = 'INSERT INTO %s VALUES(%s)' % (table, qmarks)
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
        (qmarks, bindings) = sqlhelpers.update_filler(pairs, where_key=where_key)
        query = 'UPDATE %s %s' % (table, qmarks)
        self.sql_execute(query, bindings)


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

    def get_all_tag_names(self):
        '''
        Return a list containing the names of all tags as strings.
        Useful for when you don't want the overhead of actual Tag objects.
        '''
        query = 'SELECT name FROM tags'
        rows = self.sql_select(query)
        names = [row[0] for row in rows]
        return names

    def get_all_synonyms(self):
        '''
        Return a dict mapping {synonym: mastertag} as strings.
        '''
        query = 'SELECT name, mastername FROM tag_synonyms'
        rows = self.sql_select(query)
        synonyms = {syn: tag for (syn, tag) in rows}
        return synonyms

    def get_root_tags(self):
        '''
        Yield Tags that have no parent.
        '''
        yield from self.get_root_things('tag')

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
            tagname = tagname.tagname

        try:
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

    def get_tags(self):
        '''
        Yield all Tags in the database.
        '''
        yield from self.get_things(thing_type='tag')

    def get_tags_by_id(self, ids):
        return self.get_things_by_id('tag', ids)

    @decorators.required_feature('tag.new')
    @decorators.transaction
    def new_tag(self, tagname, description=None, *, author=None, commit=True):
        '''
        Register a new tag and return the Tag object.
        '''
        tagname = self.normalize_tagname(tagname)
        self.assert_no_such_tag(name=tagname)

        description = objects.Tag.normalize_description(description)

        self.log.debug('New Tag: %s', tagname)

        tagid = self.generate_id('tags')
        self._uncache()
        author_id = self.get_user_id_or_none(author)
        data = {
            'id': tagid,
            'name': tagname,
            'description': description,
            'author_id': author_id,
        }
        self.sql_insert(table='tags', data=data)

        if commit:
            self.log.debug('Committing - new_tag')
            self.commit()
        tag = self.get_cached_instance('tag', data)
        return tag

    def normalize_tagname(self, tagname):
        tagname = objects.Tag.normalize_name(
            tagname,
            valid_chars=self.config['tag']['valid_chars'],
            min_length=self.config['tag']['min_length'],
            max_length=self.config['tag']['max_length'],
        )
        return tagname


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
        if len(password) < self.config['user']['min_password_length']:
            raise exceptions.PasswordTooShort(min_length=self.config['user']['min_password_length'])

    def assert_valid_username(self, username):
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
        possible = string.digits + string.ascii_uppercase
        for retry in range(20):
            user_id = [random.choice(possible) for x in range(self.config['id_length'])]
            user_id = ''.join(user_id)

            user_exists = self.sql_select_one('SELECT 1 FROM users WHERE id == ?', [user_id])
            if user_exists is None:
                break
        else:
            raise Exception('Failed to create user id after 20 tries.')

        return user_id

    def get_user(self, username=None, id=None):
        if not helpers.is_xor(id, username):
            raise exceptions.NotExclusive(['id', 'username'])

        if username is not None:
            user_row = self.sql_select_one('SELECT * FROM users WHERE username == ?', [username])
        else:
            user_row = self.sql_select_one('SELECT * FROM users WHERE id == ?', [id])

        if user_row is not None:
            return self.get_cached_instance('user', user_row)
        else:
            raise exceptions.NoSuchUser(username or id)

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
            author_id = None

        elif isinstance(user_obj_or_id, objects.User):
            if user_obj_or_id.photodb != self:
                raise ValueError('That user does not belong to this photodb')
            author_id = user_obj_or_id.id

        elif isinstance(user_obj_or_id, str):
            # Confirm that this string is a valid ID and not junk.
            author_id = self.get_user(id=user_obj_or_id).id

        else:
            raise TypeError('Unworkable type %s' % type(user_obj_or_id))

        return author_id

    def get_users(self):
        yield from self.get_things('user')

    @decorators.required_feature('user.login')
    def login(self, user_id, password):
        '''
        Return the User object for the user if the credentials are correct.
        '''
        user_row = self.sql_select_one('SELECT * FROM users WHERE id == ?', [user_id])

        if user_row is None:
            raise exceptions.WrongLogin()

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        user = self.get_cached_instance('user', user_row)

        success = bcrypt.checkpw(password, user.password_hash)
        if not success:
            raise exceptions.WrongLogin()

        return user

    @decorators.required_feature('user.new')
    @decorators.transaction
    def register_user(self, username, password, *, display_name=None, commit=True):
        self.assert_valid_username(username)

        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        self.assert_valid_password(password)
        self.assert_no_such_user(username=username)

        display_name = objects.User.normalize_display_name(
            display_name,
            max_length=self.config['user']['max_display_name_length'],
        )

        self.log.debug('New User: %s', username)

        user_id = self.generate_user_id()
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        created = helpers.now()

        data = {
            'id': user_id,
            'username': username,
            'password': hashed_password,
            'created': created,
            'display_name': display_name,
        }
        self.sql_insert(table='users', data=data)

        if commit:
            self.log.debug('Committing - register user')
            self.commit()

        return self.get_cached_instance('user', data)


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
            new_photo_kwargs={},
            new_photo_ratelimit=None,
            recurse=True,
            commit=True,
        ):
        '''
        Create an album, and add the directory's contents to it recursively.

        If a Photo object already exists for a file, it will be added to the
        correct album.
        '''
        def _normalize_directory(directory):
            directory = pathclass.Path(directory)
            if not directory.is_dir:
                raise ValueError('Not a directory: %s' % directory)
            directory.correct_case()
            return directory

        def _normalize_exclude_directories(exclude_directories):
            if exclude_directories is None:
                exclude_directories = self.config['digest_exclude_dirs']
            return exclude_directories

        def _normalize_exclude_filenames(exclude_filenames):
            if exclude_filenames is None:
                exclude_filenames = self.config['digest_exclude_files']
            return exclude_filenames

        def _normalize_new_photo_kwargs(new_photo_kwargs):
            new_photo_kwargs = new_photo_kwargs.copy()
            new_photo_kwargs.pop('commit', None)
            new_photo_kwargs.pop('filepath', None)
            return new_photo_kwargs

        def _normalize_new_photo_ratelimit(new_photo_ratelimit):
            if isinstance(new_photo_ratelimit, ratelimiter.Ratelimiter):
                pass
            elif new_photo_ratelimit is None:
                pass
            elif isinstance(new_photo_ratelimit, (int, float)):
                new_photo_ratelimit = ratelimiter.Ratelimiter(allowance=1, period=new_photo_ratelimit)
            else:
                raise TypeError(new_photo_ratelimit)
            return new_photo_ratelimit

        def create_or_fetch_photos(filepaths, new_photo_kwargs):
            '''
            Given an iterable of filepaths, find the corresponding Photo object
            if it exists, otherwise create it and then return it.
            '''
            photos = []
            for filepath in filepaths:
                try:
                    photo = self.get_photo_by_path(filepath)
                except exceptions.NoSuchPhoto:
                    photo = self.new_photo(filepath.absolute_path, commit=False, **new_photo_kwargs)
                    if new_photo_ratelimit is not None:
                        new_photo_ratelimit.limit()

                photos.append(photo)
            return photos

        def create_or_fetch_current_album(albums_by_path, current_directory):
            current_album = albums_by_path.get(current_directory.absolute_path, None)
            if current_album is not None:
                return current_album

            try:
                current_album = self.get_album_by_path(current_directory.absolute_path)
            except exceptions.NoSuchAlbum:
                current_album = self.new_album(
                    associated_directory=current_directory.absolute_path,
                    commit=False,
                    title=current_directory.basename,
                )
            albums_by_path[current_directory.absolute_path] = current_album
            return current_album

        def orphan_join_parent_album(albums_by_path, current_album, current_directory):
            '''
            If the current album is an orphan, let's check if there exists an
            album for the parent directory. If so, add the current album to it.
            '''
            if not current_album.has_any_parent():
                parent = albums_by_path.get(current_directory.parent.absolute_path, None)
                if parent is not None:
                    parent.add_child(current_album, commit=False)

        directory = _normalize_directory(directory)
        exclude_directories = _normalize_exclude_directories(exclude_directories)
        exclude_filenames = _normalize_exclude_filenames(exclude_filenames)
        new_photo_kwargs = _normalize_new_photo_kwargs(new_photo_kwargs)
        new_photo_ratelimit = _normalize_new_photo_ratelimit(new_photo_ratelimit)

        if make_albums:
            albums_by_path = {}
            main_album = create_or_fetch_current_album(albums_by_path, directory)

        walk_generator = spinal.walk_generator(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            recurse=recurse,
            yield_style='nested',
        )

        for (current_directory, subdirectories, files) in walk_generator:
            photos = create_or_fetch_photos(files, new_photo_kwargs=new_photo_kwargs)

            if not make_albums:
                continue

            current_album = create_or_fetch_current_album(albums_by_path, current_directory)
            orphan_join_parent_album(albums_by_path, current_album, current_directory)

            current_album.add_photos(photos, commit=False)

        if commit:
            self.log.debug('Committing - digest_directory')
            self.commit()

        if make_albums:
            return main_album
        else:
            return None

    def easybake(self, ebstring, author=None, *, commit=True):
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
                item = self.new_tag(name, author=author, commit=False)
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
                    higher.add_child(lower, commit=False)
                    note = ('join_group', f'{higher.name}.{lower.name}')
                    output_notes.append(note)
                except exceptions.GroupExists:
                    pass
            tag = tags[-1]

        if synonym:
            synonym = tag.add_synonym(synonym)
            note = ('new_synonym', f'{tag.name}+{synonym}')
            output_notes.append(note)

        if commit:
            self.log.debug('Committing - easybake')
            self.commit()
        return output_notes


class PhotoDB(
        PDBAlbumMixin,
        PDBBookmarkMixin,
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
            skip_version_check=False,
        ):
        super().__init__()

        self.ephemeral = ephemeral

        # DATA DIR PREP
        if data_directory is None:
            if self.ephemeral:
                # In addition to the data_dir as a pathclass object, keep the
                # TempDir object so we can use the cleanup method later.
                self.ephemeral_directory = tempfile.TemporaryDirectory(prefix='etiquette_ephem_')
                data_directory = self.ephemeral_directory.name
            else:
                data_directory = constants.DEFAULT_DATADIR
        elif self.ephemeral:
            raise exceptions.NotExclusive(['data_directory', 'ephemeral'])

        data_directory = helpers.remove_path_badchars(data_directory, allowed=':/\\')
        self.data_directory = pathclass.Path(data_directory)

        if self.data_directory.exists and not self.data_directory.is_dir:
            raise exceptions.BadDataDirectory(self.data_directory.absolute_path)

        self.log = logging.getLogger('etiquette:%s' % self.data_directory.absolute_path)
        self.log.setLevel(logging.DEBUG)

        # DATABASE
        if self.ephemeral:
            self.sql = sqlite3.connect(':memory:')
            existing_database = False
        else:
            self.database_filepath = self.data_directory.with_child(constants.DEFAULT_DBNAME)
            existing_database = self.database_filepath.exists

        if not create and not self.ephemeral and not existing_database:
            raise FileNotFoundError('"%s" does not exist and create is off.' % self.data_directory)

        if not self.ephemeral:
            os.makedirs(self.data_directory.absolute_path, exist_ok=True)
            self.sql = sqlite3.connect(self.database_filepath.absolute_path)

        if existing_database:
            if not skip_version_check:
                self._check_version()
            self._load_pragmas()
        else:
            self._first_time_setup()

        # THUMBNAIL DIRECTORY
        self.thumbnail_directory = self.data_directory.with_child(constants.DEFAULT_THUMBDIR)
        os.makedirs(self.thumbnail_directory.absolute_path, exist_ok=True)

        # CONFIG
        self.config_filepath = self.data_directory.with_child(constants.DEFAULT_CONFIGNAME)
        self.config = self.load_config()
        self.log.setLevel(self.config['log_level'])

        # OTHER

        self._cached_frozen_children = None

        self.caches = {
            'album': cacheclass.Cache(maxlen=self.config['cache_size']['album']),
            'bookmark': cacheclass.Cache(maxlen=self.config['cache_size']['bookmark']),
            'photo': cacheclass.Cache(maxlen=self.config['cache_size']['photo']),
            'tag': cacheclass.Cache(maxlen=self.config['cache_size']['tag']),
            'user': cacheclass.Cache(maxlen=self.config['cache_size']['user']),
        }

    def _check_version(self):
        '''
        Compare database's user_version against constants.DATABASE_VERSION,
        raising exceptions.DatabaseOutOfDate if not correct.
        '''
        existing_version = self.sql_execute('PRAGMA user_version').fetchone()[0]
        if existing_version != constants.DATABASE_VERSION:
            exc = exceptions.DatabaseOutOfDate(
                current=existing_version,
                new=constants.DATABASE_VERSION,
            )
            raise exc

    def _first_time_setup(self):
        self.log.debug('Running first-time setup.')
        cur = self.sql.cursor()
        cur.executescript(constants.DB_INIT)
        self.sql.commit()

    def _load_pragmas(self):
        cur = self.sql.cursor()
        cur.executescript(constants.DB_PRAGMAS)
        self.sql.commit()

    def __del__(self):
        self.close()

    def __repr__(self):
        if self.ephemeral:
            return 'PhotoDB(ephemeral=True)'
        else:
            return f'PhotoDB(data_directory={self.data_directory})'

    def _uncache(self):
        self._cached_frozen_children = None

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
            raise ValueError('Invalid table requested: %s.', table)

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

    def get_cached_frozen_children(self):
        if self._cached_frozen_children is None:
            self._cached_frozen_children = tag_export.flat_dict(self.get_tags())
        return self._cached_frozen_children

    def get_cached_instance(self, thing_type, db_row):
        thing_map = _THING_CLASSES[thing_type]

        thing_table = thing_map['table']
        thing_class = thing_map['class']
        thing_cache = self.caches[thing_type]
        thing_index = constants.SQL_INDEX[thing_table]

        if isinstance(db_row, dict):
            thing_id = db_row['id']
        else:
            thing_id = db_row[thing_index['id']]

        try:
            thing = thing_cache[thing_id]
        except KeyError:
            thing = thing_class(self, db_row)
            thing_cache[thing_id] = thing
        return thing

    def get_root_things(self, thing_type):
        '''
        For Groupable types, yield things which have no parent.
        '''
        thing_map = _THING_CLASSES[thing_type]

        thing_class = thing_map['class']
        thing_table = thing_map['table']
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
        thing_map = _THING_CLASSES[thing_type]

        thing_class = thing_map['class']
        if isinstance(thing_id, thing_class):
            thing_id = thing_id.id

        thing_cache = self.caches[thing_type]
        try:
            return thing_cache[thing_id]
        except KeyError:
            pass

        query = 'SELECT * FROM %s WHERE id == ?' % thing_map['table']
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
        thing_map = _THING_CLASSES[thing_type]

        query = 'SELECT * FROM %s' % thing_map['table']

        things = self.sql_select(query)
        for thing_row in things:
            thing = self.get_cached_instance(thing_type, thing_row)
            yield thing

    def get_things_by_id(self, thing_type, thing_ids):
        thing_map = _THING_CLASSES[thing_type]
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

        ids_needed = list(ids_needed)
        while ids_needed:
            # SQLite3 has a limit of 999 ? in a query, so we must batch them.
            id_batch = ids_needed[:999]
            ids_needed = ids_needed[999:]

            qmarks = ','.join('?' * len(id_batch))
            qmarks = '(%s)' % qmarks
            query = 'SELECT * FROM %s WHERE id IN %s' % (thing_map['table'], qmarks)
            more_things = self.sql_select(query, id_batch)
            for thing_row in more_things:
                # Normally we would call `get_cached_instance` instead of
                # constructing here. But we already know for a fact that this
                # object is not in the cache because it made it past the
                # previous loop.
                thing = thing_class(self, db_row=thing_row)
                thing_cache[thing.id] = thing
                yield thing

    def load_config(self):
        config = copy.deepcopy(constants.DEFAULT_CONFIGURATION)
        user_config_exists = self.config_filepath.is_file
        needs_dump = False
        if user_config_exists:
            with open(self.config_filepath.absolute_path, 'r', encoding='utf-8') as handle:
                user_config = json.load(handle)
            my_keys = helpers.recursive_dict_keys(config)
            stored_keys = helpers.recursive_dict_keys(user_config)
            needs_dump = not my_keys.issubset(stored_keys)
            helpers.recursive_dict_update(target=config, supply=user_config)
        else:
            needs_dump = True

        self.config = config

        if needs_dump:
            self.save_config()

        return config

    def save_config(self):
        with open(self.config_filepath.absolute_path, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(self.config, indent=4, sort_keys=True))


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
