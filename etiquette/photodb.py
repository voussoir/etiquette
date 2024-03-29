import bcrypt
import hashlib
import json
import os
import random
import tempfile
import types
import typing

from . import constants
from . import decorators
from . import exceptions
from . import helpers
from . import objects
from . import tag_export

from voussoirkit import cacheclass
from voussoirkit import configlayers
from voussoirkit import pathclass
from voussoirkit import progressbars
from voussoirkit import ratelimiter
from voussoirkit import spinal
from voussoirkit import sqlhelpers
from voussoirkit import stringtools
from voussoirkit import timetools
from voussoirkit import vlogging
from voussoirkit import worms

log = vlogging.getLogger(__name__)

RNG = random.SystemRandom()

####################################################################################################

class PDBAlbumMixin:
    def __init__(self):
        super().__init__()

    def get_album(self, id) -> objects.Album:
        return self.get_object_by_id(objects.Album, id)

    def get_album_count(self) -> int:
        return self.select_one_value('SELECT COUNT(*) FROM albums')

    def get_albums(self) -> typing.Iterable[objects.Album]:
        return self.get_objects(objects.Album)

    def get_albums_by_id(self, ids) -> typing.Iterable[objects.Album]:
        return self.get_objects_by_id(objects.Album, ids)

    def get_albums_by_path(self, directory) -> typing.Iterable[objects.Album]:
        '''
        Yield Albums with the `associated_directory` of this value,
        NOT case-sensitive.
        '''
        directory = pathclass.Path(directory)
        query = 'SELECT albumid FROM album_associated_directories WHERE directory == ?'
        bindings = [directory.absolute_path]
        album_ids = self.select_column(query, bindings)
        return self.get_albums_by_id(album_ids)

    def get_albums_by_sql(self, query, bindings=None) -> typing.Iterable[objects.Album]:
        return self.get_objects_by_sql(objects.Album, query, bindings)

    def get_albums_within_directory(self, directory) -> typing.Iterable[objects.Album]:
        # This function is something of a stopgap measure since `search` only
        # searches for photos and then yields their containing albums. Thus it
        # is not possible for search to find albums that contain no photos.
        # I'd like to find a better solution than this separate method.
        directory = pathclass.Path(directory)
        directory.assert_is_directory()
        pattern = directory.absolute_path.rstrip(os.sep)
        pattern = f'{pattern}{os.sep}%'
        album_ids = self.select_column(
            'SELECT DISTINCT albumid FROM album_associated_directories WHERE directory LIKE ?',
            [pattern]
        )
        albums = self.get_albums_by_id(album_ids)
        return albums

    def get_root_albums(self) -> typing.Iterable[objects.Album]:
        '''
        Yield Albums that have no parent.
        '''
        return self.get_root_objects(objects.Album)

    @decorators.required_feature('album.new')
    @worms.atomic
    def new_album(
            self,
            title=None,
            description=None,
            *,
            associated_directories=None,
            author=None,
            photos=None,
        ) -> objects.Album:
        '''
        Create a new album. Photos can be added now or later.
        '''
        # These might raise exceptions.
        title = objects.Album.normalize_title(title)
        description = objects.Album.normalize_description(description)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        album_id = self.generate_id(objects.Album)
        log.info('New Album: %s %s.', album_id, title)

        data = {
            'id': album_id,
            'title': title,
            'description': description,
            'created': timetools.now().timestamp(),
            'thumbnail_photo': None,
            'author_id': author_id,
        }
        self.insert(table=objects.Album, pairs=data)

        album = self.get_cached_instance(objects.Album, data)

        associated_directories = associated_directories or ()
        if isinstance(associated_directories, str):
            associated_directories = [associated_directories]
        album.add_associated_directories(associated_directories)

        if photos is not None:
            photos = [self.get_photo(photo) for photo in photos]
            album.add_photos(photos)

        return album

    @worms.atomic
    def purge_deleted_associated_directories(self, albums=None) -> typing.Iterable[pathclass.Path]:
        query = 'SELECT DISTINCT directory FROM album_associated_directories'
        directories = self.select_column(query)
        directories = (pathclass.Path(d) for d in directories)
        directories = [d for d in directories if not d.is_dir]
        if not directories:
            return
        log.info('Purging associated directories %s.', directories)

        d_query = sqlhelpers.listify(d.absolute_path for d in directories)
        query = f'DELETE FROM album_associated_directories WHERE directory in {d_query}'
        if albums is not None:
            album_ids = sqlhelpers.listify(a.id for a in albums)
            query += f' AND albumid IN {album_ids}'
        self.execute(query)
        yield from directories

    @worms.atomic
    def purge_empty_albums(self, albums=None) -> typing.Iterable[objects.Album]:
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

    def get_bookmark(self, id) -> objects.Bookmark:
        return self.get_object_by_id(objects.Bookmark, id)

    def get_bookmark_count(self) -> int:
        return self.select_one_value('SELECT COUNT(*) FROM bookmarks')

    def get_bookmarks(self) -> typing.Iterable[objects.Bookmark]:
        return self.get_objects(objects.Bookmark)

    def get_bookmarks_by_id(self, ids) -> typing.Iterable[objects.Bookmark]:
        return self.get_objects_by_id(objects.Bookmark, ids)

    def get_bookmarks_by_sql(self, query, bindings=None) -> typing.Iterable[objects.Bookmark]:
        return self.get_objects_by_sql(objects.Bookmark, query, bindings)

    @decorators.required_feature('bookmark.new')
    @worms.atomic
    def new_bookmark(self, url, title=None, *, author=None) -> objects.Bookmark:
        # These might raise exceptions.
        title = objects.Bookmark.normalize_title(title)
        url = objects.Bookmark.normalize_url(url)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        bookmark_id = self.generate_id(objects.Bookmark)
        log.info('New Bookmark: %s %s %s.', bookmark_id, title, url)

        data = {
            'id': bookmark_id,
            'title': title,
            'url': url,
            'created': timetools.now().timestamp(),
            'author_id': author_id,
        }
        self.insert(table=objects.Bookmark, pairs=data)

        bookmark = self.get_cached_instance(objects.Bookmark, data)

        return bookmark

####################################################################################################

class PDBGroupableMixin:
    def __init__(self):
        super().__init__()

    def get_root_objects(self, object_class):
        '''
        For Groupable types, yield objects which have no parent.
        '''
        object_table = object_class.table
        group_table = object_class.group_table

        query = f'''
        SELECT * FROM {object_table}
        WHERE NOT EXISTS (
            SELECT 1 FROM {group_table}
            WHERE memberid == {object_table}.id
        )
        '''

        rows = self.select(query)
        for row in rows:
            instance = self.get_cached_instance(object_class, row)
            yield instance

####################################################################################################

class PDBPhotoMixin:
    def __init__(self):
        super().__init__()

    def assert_no_such_photo_by_path(self, filepath) -> None:
        try:
            existing = self.get_photo_by_path(filepath)
        except exceptions.NoSuchPhoto:
            return
        else:
            raise exceptions.PhotoExists(existing)

    def get_photo(self, id) -> objects.Photo:
        return self.get_object_by_id(objects.Photo, id)

    def get_photo_by_path(self, filepath) -> objects.Photo:
        filepath = pathclass.Path(filepath)
        query = 'SELECT * FROM photos WHERE filepath == ?'
        bindings = [filepath.absolute_path]
        photo_row = self.select_one(query, bindings)
        if photo_row is None:
            raise exceptions.NoSuchPhoto(filepath)
        photo = self.get_cached_instance(objects.Photo, photo_row)
        return photo

    def get_photo_count(self) -> int:
        return self.select_one_value('SELECT COUNT(*) FROM photos')

    def get_photos(self) -> typing.Iterable[objects.Photo]:
        return self.get_objects(objects.Photo)

    def get_photos_by_id(self, ids) -> typing.Iterable[objects.Photo]:
        return self.get_objects_by_id(objects.Photo, ids)

    def get_photos_by_recent(self, count=None) -> typing.Iterable[objects.Photo]:
        '''
        Yield photo objects in order of creation time.
        '''
        if count is not None and count <= 0:
            return

        query = 'SELECT * FROM photos ORDER BY created DESC'
        photo_rows = self.select(query)
        for photo_row in photo_rows:
            photo = self.get_cached_instance(objects.Photo, photo_row)
            yield photo

            if count is None:
                continue
            count -= 1
            if count <= 0:
                break

    def get_photos_by_hash(self, sha256) -> typing.Iterable[objects.Photo]:
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise TypeError(f'sha256 shoulbe the 64-character hexdigest string.')

        query = 'SELECT * FROM photos WHERE sha256 == ?'
        bindings = [sha256]
        yield from self.get_photos_by_sql(query, bindings)

    def get_photos_by_sql(self, query, bindings=None) -> typing.Iterable[objects.Photo]:
        return self.get_objects_by_sql(objects.Photo, query, bindings)

    @decorators.required_feature('photo.new')
    @worms.atomic
    def new_photo(
            self,
            filepath,
            *,
            author=None,
            do_metadata=True,
            do_thumbnail=True,
            hash_kwargs=None,
            known_hash=None,
            searchhidden=False,
            tags=None,
            trusted_file=False,
        ) -> objects.Photo:
        '''
        Given a filepath, determine its attributes and create a new Photo object
        in the database. Tags may be applied now or later.

        hash_kwargs:
            Additional kwargs passed into spinal.hash_file. Notably, you may
            wish to set bytes_per_second to keep system load low.

        known_hash:
            If the sha256 of the file is already known, you may provide it here
            so it does not need to be recalculated. This is primarily intended
            for digest_directory since it will look for hash matches first
            before creating new photos and thus can provide the known hash.

        Returns the Photo object.
        '''
        # These might raise exceptions
        filepath = pathclass.Path(filepath)
        if not filepath.is_file:
            raise FileNotFoundError(filepath.absolute_path)

        self.assert_no_such_photo_by_path(filepath=filepath)

        author_id = self.get_user_id_or_none(author)

        if known_hash is None:
            pass
        elif not isinstance(known_hash, str) or len(known_hash) != 64:
            raise TypeError(f'known_hash should be the 64-character sha256 hexdigest string.')

        # Ok.
        photo_id = self.generate_id(objects.Photo)
        log.info('New Photo: %s %s.', photo_id, filepath.absolute_path)

        data = {
            'id': photo_id,
            'filepath': filepath.absolute_path,
            'override_filename': None,
            'created': timetools.now().timestamp(),
            'tagged_at': None,
            'author_id': author_id,
            'searchhidden': searchhidden,
            # These will be filled in during the metadata stage.
            'mtime': None,
            'sha256': known_hash,
            'bytes': None,
            'width': None,
            'height': None,
            'duration': None,
        }
        self.insert(table=objects.Photo, pairs=data)

        photo = self.get_photo(photo_id)

        if do_metadata:
            hash_kwargs = hash_kwargs or {}
            photo.reload_metadata(hash_kwargs=hash_kwargs, trusted_file=trusted_file)
        if do_thumbnail:
            photo.generate_thumbnail(trusted_file=trusted_file)

        tags = tags or []
        tags = [self.get_tag(name=tag) for tag in tags]
        for tag in tags:
            photo.add_tag(tag)

        return photo

    @worms.atomic
    def purge_deleted_files(self, photos=None) -> typing.Iterable[objects.Photo]:
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

    def search(self, **kwargs):
        return objects.Search(photodb=self, kwargs=kwargs)

####################################################################################################

class PDBTagMixin:
    def __init__(self):
        super().__init__()

    def assert_no_such_tag(self, name) -> None:
        try:
            existing_tag = self.get_tag_by_name(name)
        except exceptions.NoSuchTag:
            return
        else:
            raise exceptions.TagExists(existing_tag)

    def _get_all_tag_names(self):
        query = 'SELECT name FROM tags'
        names = set(self.select_column(query))
        return names

    def get_all_tag_names(self) -> set[str]:
        '''
        Return a set containing the names of all tags as strings.
        Useful for when you don't want the overhead of actual Tag objects.
        '''
        return self.get_cached_tag_export(self._get_all_tag_names)

    def _get_all_synonyms(self):
        query = 'SELECT name, mastername FROM tag_synonyms'
        syn_rows = self.select(query)
        synonyms = {syn: tag for (syn, tag) in syn_rows}
        return synonyms

    def get_all_synonyms(self) -> dict:
        '''
        Return a dict mapping {synonym: mastertag} as strings.
        '''
        return self.get_cached_tag_export(self._get_all_synonyms)

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

    def get_root_tags(self) -> typing.Iterable[objects.Tag]:
        '''
        Yield Tags that have no parent.
        '''
        return self.get_root_objects(objects.Tag)

    def get_tag(self, name=None, id=None) -> objects.Tag:
        '''
        Redirect to get_tag_by_id or get_tag_by_name.
        '''
        if not helpers.is_xor(id, name):
            raise exceptions.NotExclusive(['id', 'name'])

        if id is not None:
            return self.get_tag_by_id(id)
        else:
            return self.get_tag_by_name(name)

    def get_tag_by_id(self, id) -> objects.Tag:
        return self.get_object_by_id(objects.Tag, id)

    def get_tag_by_name(self, tagname) -> objects.Tag:
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
            tag_row = self.select_one('SELECT * FROM tags WHERE name == ?', [tagname])
            if tag_row is not None:
                break

            # ...or resolve the synonym and try again.
            query = 'SELECT mastername FROM tag_synonyms WHERE name == ?'
            bindings = [tagname]
            mastername = self.select_one_value(query, bindings)
            if mastername is None:
                # was not a master tag or synonym
                raise exceptions.NoSuchTag(tagname)
            tagname = mastername

        tag = self.get_cached_instance(objects.Tag, tag_row)
        return tag

    def get_tag_count(self) -> int:
        return self.select_one_value('SELECT COUNT(*) FROM tags')

    def get_tags(self) -> typing.Iterable[objects.Tag]:
        '''
        Yield all Tags in the database.
        '''
        return self.get_objects(objects.Tag)

    def get_tags_by_id(self, ids) -> typing.Iterable[objects.Tag]:
        return self.get_objects_by_id(objects.Tag, ids)

    def get_tags_by_sql(self, query, bindings=None) -> typing.Iterable[objects.Tag]:
        return self.get_objects_by_sql(objects.Tag, query, bindings)

    @decorators.required_feature('tag.new')
    @worms.atomic
    def new_tag(self, tagname, description=None, *, author=None) -> objects.Tag:
        '''
        Register a new tag and return the Tag object.
        '''
        # These might raise exceptions.
        tagname = self.normalize_tagname(tagname)
        self.assert_no_such_tag(name=tagname)

        description = objects.Tag.normalize_description(description)
        author_id = self.get_user_id_or_none(author)

        # Ok.
        tag_id = self.generate_id(objects.Tag)
        log.info('New Tag: %s %s.', tag_id, tagname)

        self.caches['tag_exports'].clear()

        data = {
            'id': tag_id,
            'name': tagname,
            'description': description,
            'created': timetools.now().timestamp(),
            'author_id': author_id,
        }
        self.insert(table=objects.Tag, pairs=data)

        tag = self.get_cached_instance(objects.Tag, data)

        return tag

    def normalize_tagname(self, tagname) -> str:
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

    def assert_no_such_user(self, username) -> None:
        try:
            existing_user = self.get_user(username=username)
        except exceptions.NoSuchUser:
            return
        else:
            raise exceptions.UserExists(existing_user)

    def assert_valid_password(self, password) -> None:
        if not isinstance(password, bytes):
            raise TypeError(f'Password must be {bytes}, not {type(password)}.')

        if len(password) < self.config['user']['min_password_length']:
            raise exceptions.PasswordTooShort(min_length=self.config['user']['min_password_length'])

    def assert_valid_username(self, username) -> None:
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

    def get_user(self, username=None, id=None) -> objects.User:
        '''
        Redirect to get_user_by_id or get_user_by_username.
        '''
        if not helpers.is_xor(id, username):
            raise exceptions.NotExclusive(['id', 'username'])

        if id:
            return self.get_user_by_id(id)
        else:
            return self.get_user_by_username(username)

    def get_user_by_id(self, id) -> objects.User:
        return self.get_object_by_id(objects.User, id)

    def get_user_by_username(self, username) -> objects.User:
        user_row = self.select_one('SELECT * FROM users WHERE username == ?', [username])

        if user_row is None:
            raise exceptions.NoSuchUser(username)

        return self.get_cached_instance(objects.User, user_row)

    def get_user_count(self) -> int:
        return self.select_one_value('SELECT COUNT(*) FROM users')

    def get_user_id_or_none(self, user_obj_or_id) -> typing.Optional[str]:
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

    def get_users(self) -> typing.Iterable[objects.User]:
        return self.get_objects(objects.User)

    def get_users_by_id(self, ids) -> typing.Iterable[objects.User]:
        return self.get_objects_by_id(objects.User, ids)

    def get_users_by_sql(self, query, bindings=None) -> typing.Iterable[objects.User]:
        return self.get_objects_by_sql(objects.User, query, bindings)

    @decorators.required_feature('user.new')
    @worms.atomic
    def new_user(self, username, password, *, display_name=None) -> objects.User:
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
        user_id = self.generate_id(objects.User)
        log.info('New User: %s %s.', user_id, username)

        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        data = {
            'id': user_id,
            'username': username,
            'password': hashed_password,
            'display_name': display_name,
            'created': timetools.now().timestamp(),
        }
        self.insert(table=objects.User, pairs=data)

        return self.get_cached_instance(objects.User, data)

####################################################################################################

class PDBUtilMixin:
    def __init__(self):
        super().__init__()

    @worms.atomic
    def digest_directory(
            self,
            directory,
            *,
            exclude_directories=None,
            exclude_filenames=None,
            glob_directories=None,
            glob_filenames=None,
            hash_kwargs=None,
            make_albums=True,
            natural_sort=True,
            new_photo_kwargs=None,
            new_photo_ratelimit=None,
            recurse=True,
            yield_albums=True,
            yield_new_photos=True,
            yield_old_photos=True,
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

        hash_kwargs:
            Additional kwargs passed into spinal.hash_file. Notably, you may
            wish to set bytes_per_second to keep system load low.

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
            See stringtools.natural_sorter.

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
            if new_photo_kwargs is None:
                new_photo_kwargs = {}
            else:
                new_photo_kwargs = new_photo_kwargs.copy()
                new_photo_kwargs.pop('commit', None)
                new_photo_kwargs.pop('filepath', None)

            new_photo_kwargs.setdefault('hash_kwargs', hash_kwargs)
            return new_photo_kwargs

        def _normalize_new_photo_ratelimit(new_photo_ratelimit):
            if new_photo_ratelimit is None:
                return new_photo_ratelimit
            elif isinstance(new_photo_ratelimit, ratelimiter.Ratelimiter):
                return new_photo_ratelimit
            elif isinstance(new_photo_ratelimit, (int, float)):
                new_photo_ratelimit = ratelimiter.Ratelimiter(allowance=1, period=new_photo_ratelimit)
                return new_photo_ratelimit
            raise TypeError(new_photo_ratelimit)

        def check_renamed(filepath):
            '''
            We'll do our best to determine if this file is actually a rename of
            a file that's already in the database.
            '''
            same_meta = self.get_photos_by_sql(
                'SELECT * FROM photos WHERE mtime != 0 AND mtime == ? AND bytes == ?',
                [filepath.stat.st_mtime, filepath.stat.st_size]
            )
            same_meta = [photo for photo in same_meta if not photo.real_path.is_file]
            if len(same_meta) == 1:
                photo = same_meta[0]
                log.debug('Found mtime+bytesize match %s.', photo)
                return photo

            log.loud('Hashing file %s to check for rename.', filepath)

            if filepath.size > 100 * (2 ** 20):
                progressbar = progressbars.bar1_bytestring()
            else:
                progressbar = None

            sha256 = spinal.hash_file(
                filepath,
                hash_class=hashlib.sha256, **hash_kwargs,
                progressbar=progressbar,
            ).hexdigest()

            same_hash = self.get_photos_by_hash(sha256)
            same_hash = [photo for photo in same_hash if not photo.real_path.is_file]

            # fwiw, I'm not checking byte size since it's a hash match.
            if len(same_hash) > 1:
                same_hash = [photo for photo in same_hash if photo.mtime == filepath.stat.st_mtime]
            if len(same_hash) == 1:
                return same_hash[0]

            # Although we did not find a match, we can still benefit from our
            # hash work by passing this as the known_hash to new_photo.
            return {'sha256': sha256}

        def create_or_fetch_photo(filepath):
            '''
            Given a filepath, find the corresponding Photo object if it exists,
            otherwise create it and then return it.
            '''
            try:
                return (self.get_photo_by_path(filepath), False)
            except exceptions.NoSuchPhoto:
                pass

            result = check_renamed(filepath)
            if isinstance(result, objects.Photo):
                result.relocate(filepath.absolute_path)
                return (result, False)
            elif isinstance(result, dict) and 'sha256' in result:
                sha256 = result['sha256']
            else:
                sha256 = None

            photo = self.new_photo(filepath, known_hash=sha256, **new_photo_kwargs)
            if new_photo_ratelimit is not None:
                new_photo_ratelimit.limit()

            return (photo, True)

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
        hash_kwargs = hash_kwargs or {}
        new_photo_kwargs = _normalize_new_photo_kwargs(new_photo_kwargs)
        new_photo_ratelimit = _normalize_new_photo_ratelimit(new_photo_ratelimit)

        albums_by_path = {}

        log.info('Digesting directory "%s".', directory.absolute_path)
        walk_generator = spinal.walk(
            directory,
            exclude_directories=exclude_directories,
            exclude_filenames=exclude_filenames,
            glob_directories=glob_directories,
            glob_filenames=glob_filenames,
            recurse=recurse,
            yield_style='nested',
        )

        for (current_directory, subdirectories, files) in walk_generator:
            if natural_sort:
                files = sorted(files, key=lambda f: stringtools.natural_sorter(f.basename))

            photos = [create_or_fetch_photo(file) for file in files]

            # Note, this means that empty folders will not get an Album.
            # At this time this behavior is intentional. Furthermore, due to
            # the glob/exclude rules, we don't want albums being created if
            # they don't contain any files of interest, even if they do contain
            # other files.
            if not photos:
                continue

            for (photo, is_new) in photos:
                if (is_new and yield_new_photos) or (not is_new and yield_old_photos):
                    yield photo

            if not make_albums:
                continue

            current_albums = create_or_fetch_current_albums(albums_by_path, current_directory)
            orphan_join_parent_albums(albums_by_path, current_albums, current_directory)

            for album in current_albums:
                album.add_photos(photo for (photo, is_new) in photos)

            if yield_albums:
                yield from current_albums

    @worms.atomic
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
        PDBGroupableMixin,
        PDBPhotoMixin,
        PDBTagMixin,
        PDBUserMixin,
        PDBUtilMixin,
        worms.DatabaseWithCaching,
    ):
    def __init__(
            self,
            data_directory=None,
            *,
            create=False,
            ephemeral=False,
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
        # Used by decorators.required_feature.
        self._photodb = self

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
            data_directory = pathclass.cwd().with_child(constants.DEFAULT_DATADIR)

        if isinstance(data_directory, str):
            data_directory = helpers.remove_path_badchars(data_directory, allowed=':/\\')
        self.data_directory = pathclass.Path(data_directory)

        if self.data_directory.exists and not self.data_directory.is_dir:
            raise exceptions.BadDataDirectory(self.data_directory.absolute_path)

        # DATABASE / WORMS
        self._init_sql(create=create, skip_version_check=skip_version_check)

        # THUMBNAIL DIRECTORY
        self.thumbnail_directory = self.data_directory.with_child(constants.DEFAULT_THUMBDIR)
        self.thumbnail_directory.makedirs(exist_ok=True)

        # CONFIG
        self.config_filepath = self.data_directory.with_child(constants.DEFAULT_CONFIGNAME)
        self.load_config()

        # WORMS
        self._init_column_index()
        self._init_caches()

    def _check_version(self):
        '''
        Compare database's user_version against constants.DATABASE_VERSION,
        raising exceptions.DatabaseOutOfDate if not correct.
        '''
        existing = self.pragma_read('user_version')
        if existing != constants.DATABASE_VERSION:
            raise exceptions.DatabaseOutOfDate(
                existing=existing,
                new=constants.DATABASE_VERSION,
                filepath=self.data_directory,
            )

    def _first_time_setup(self):
        log.info('Running first-time database setup.')
        with self.transaction:
            self._load_pragmas()
            self.pragma_write('user_version', constants.DATABASE_VERSION)
            self.executescript(constants.DB_INIT)

    def _init_caches(self):
        self.caches = {
            objects.Album: cacheclass.Cache(maxlen=self.config['cache_size']['album']),
            objects.Bookmark: cacheclass.Cache(maxlen=self.config['cache_size']['bookmark']),
            objects.Photo: cacheclass.Cache(maxlen=self.config['cache_size']['photo']),
            objects.Tag: cacheclass.Cache(maxlen=self.config['cache_size']['tag']),
            objects.User: cacheclass.Cache(maxlen=self.config['cache_size']['user']),
            'tag_exports': cacheclass.Cache(maxlen=100),
        }

    def _init_column_index(self):
        self.COLUMNS = constants.SQL_COLUMNS
        self.COLUMN_INDEX = constants.SQL_INDEX

    def _init_sql(self, create=False, skip_version_check=False):
        if self.ephemeral:
            existing_database = False
            self.sql_write = self._make_sqlite_write_connection(':memory:')
            self.sql_read = self._make_sqlite_read_connection(':memory:')
            self._first_time_setup()
            return

        self.database_filepath = self.data_directory.with_child(constants.DEFAULT_DBNAME)
        existing_database = self.database_filepath.exists

        if not existing_database and not create:
            msg = f'"{self.database_filepath.absolute_path}" does not exist and create is off.'
            raise FileNotFoundError(msg)

        self.data_directory.makedirs(exist_ok=True)
        self.sql_write = self._make_sqlite_write_connection(self.database_filepath)
        self.sql_read = self._make_sqlite_read_connection(self.database_filepath)

        if existing_database:
            if not skip_version_check:
                self._check_version()
            with self.transaction:
                self._load_pragmas()
        else:
            self._first_time_setup()

    def _load_pragmas(self):
        log.debug('Reloading pragmas.')
        self.pragma_write('cache_size', 10000)
        self.pragma_write('foreign_keys', 'on')

    # Will add -> PhotoDB when forward references are supported
    @classmethod
    def closest_photodb(cls, path='.', *args, **kwargs):
        '''
        Starting from the given path and climbing upwards towards the filesystem
        root, look for an existing Etiquette data directory and return the
        PhotoDB object. If none exists, raise exceptions.NoClosestPhotoDB.
        '''
        path = pathclass.Path(path)
        starting = path

        while True:
            possible = path.with_child(constants.DEFAULT_DATADIR)
            if possible.is_dir:
                break
            parent = path.parent
            if path == parent:
                raise exceptions.NoClosestPhotoDB(starting.absolute_path)
            path = parent

        path = possible
        log.debug('Found closest PhotoDB at "%s".', path.absolute_path)

        try:
            photodb = cls(
                data_directory=path,
                create=False,
                *args,
                **kwargs,
            )
        except FileNotFoundError:
            raise exceptions.NoClosestPhotoDB(starting.absolute_path)

        return photodb

    def __del__(self):
        self.close()

    def __repr__(self):
        if self.ephemeral:
            return 'PhotoDB(ephemeral=True)'
        else:
            return f'PhotoDB(data_directory={self.data_directory})'

    def close(self) -> None:
        log.debug('Closing PhotoDB.')
        super().close()

        if getattr(self, 'ephemeral', False):
            self.ephemeral_directory.cleanup()

    def generate_id(self, thing_class) -> int:
        '''
        Create a new ID number that is unique to the given table.
        '''
        if not issubclass(thing_class, objects.ObjectBase):
            raise TypeError(thing_class)

        table = thing_class.table

        length = self.config['id_bits']
        for retry in range(10):
            id = RNG.getrandbits(length)
            if not self.exists(f'SELECT 1 FROM {table} WHERE id == ?', [id]):
                return id
        raise exceptions.GenerateIDFailed(table=table)

    def load_config(self) -> None:
        log.debug('Loading config file.')
        (config, needs_rewrite) = configlayers.load_file(
            filepath=self.config_filepath,
            default_config=constants.DEFAULT_CONFIGURATION,
        )
        self.config = config

        if needs_rewrite:
            self.save_config()

    def save_config(self) -> None:
        log.debug('Saving config file.')
        with self.config_filepath.open('w', encoding='utf-8') as handle:
            handle.write(json.dumps(self.config, indent=4, sort_keys=True))
