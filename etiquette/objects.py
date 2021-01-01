'''
This file provides the data objects that should not be instantiated directly,
but are returned by the PDB accesses.
'''
import abc
import os
import PIL.Image
import re
import send2trash
import traceback

from voussoirkit import bytestring
from voussoirkit import gentools
from voussoirkit import hms
from voussoirkit import pathclass
from voussoirkit import sentinel
from voussoirkit import spinal
from voussoirkit import sqlhelpers
from voussoirkit import stringtools

from . import constants
from . import decorators
from . import exceptions
from . import helpers

BAIL = sentinel.Sentinel('BAIL')

def normalize_db_row(db_row, table):
    if isinstance(db_row, dict):
        return db_row

    if isinstance(db_row, (list, tuple)):
        return dict(zip(constants.SQL_COLUMNS[table], db_row))

    raise TypeError(f'db_row should be {dict}, {list}, or {tuple}, not {type(db_row)}.')

class ObjectBase:
    def __init__(self, photodb):
        super().__init__()
        self.photodb = photodb
        self.deleted = False

    def __eq__(self, other):
        return (
            isinstance(other, type(self)) and
            self.photodb == other.photodb and
            self.id == other.id
        )

    def __format__(self, formcode):
        if formcode == 'r':
            return repr(self)
        else:
            return str(self)

    def __hash__(self):
        return hash(self.id)

    @staticmethod
    def normalize_author_id(author_id):
        if author_id is None:
            return None

        if not isinstance(author_id, str):
            raise TypeError(f'Author ID must be {str}, not {type(author_id)}.')

        author_id = author_id.strip()
        if author_id == '':
            return None

        if not all(c in constants.USER_ID_CHARACTERS for c in author_id):
            raise ValueError(f'Author ID must consist only of {constants.USER_ID_CHARACTERS}.')

        return author_id

    def assert_not_deleted(self):
        if self.deleted:
            raise exceptions.DeletedObject(self)

    def get_author(self):
        '''
        Return the User who created this object, or None if it is unassigned.
        '''
        if self.author_id is None:
            return None
        return self.photodb.get_user(id=self.author_id)

class GroupableMixin(metaclass=abc.ABCMeta):
    group_getter_many = None
    group_table = None

    def __lift_children(self):
        '''
        If this object has parents, the parents adopt all of its children.
        Otherwise, this object is at the root level, so the parental
        relationship is simply deleted and the children become root level.
        '''
        children = self.get_children()
        if not children:
            return

        self.photodb.sql_delete(table=self.group_table, pairs={'parentid': self.id})

        parents = self.get_parents()
        for parent in parents:
            parent.add_children(children)

    def __add_child(self, member):
        self.assert_same_type(member)

        if member == self:
            raise exceptions.CantGroupSelf(self)

        if self.has_child(member):
            return BAIL

        self.photodb.log.info('Adding child %s to %s.', member, self)

        for my_ancestor in self.walk_parents():
            if my_ancestor == member:
                raise exceptions.RecursiveGrouping(member=member, group=self)

        data = {
            'parentid': self.id,
            'memberid': member.id,
        }
        self.photodb.sql_insert(table=self.group_table, data=data)

    @abc.abstractmethod
    def add_child(self, member):
        return self.__add_child(member)

    @abc.abstractmethod
    def add_children(self, members):
        bail = True
        for member in members:
            bail = (self.__add_child(member) is BAIL) and bail
        if bail:
            return BAIL

    def assert_same_type(self, other):
        if not isinstance(other, type(self)):
            raise TypeError(f'Object must be of type {type(self)}, not {type(other)}.')
        if self.photodb != other.photodb:
            raise TypeError(f'Objects must belong to the same PhotoDB.')

    @abc.abstractmethod
    def delete(self, *, delete_children=False):
        '''
        Delete this object's relationships to other groupables.
        Any unique / specific deletion methods should be written within the
        inheriting class.

        For example, Tag.delete calls here to remove the group links, but then
        does the rest of the tag deletion process on its own.

        delete_children:
            If True, all children will be deleted.
            Otherwise they'll just be raised up one level.
        '''
        if delete_children:
            for child in self.get_children():
                child.delete(delete_children=True)
        else:
            self.__lift_children()

        # Note that this part comes after the deletion of children to prevent
        # issues of recursion.
        self.photodb.sql_delete(table=self.group_table, pairs={'memberid': self.id})
        self._uncache()
        self.deleted = True

    def get_children(self):
        child_rows = self.photodb.sql_select(
            f'SELECT memberid FROM {self.group_table} WHERE parentid == ?',
            [self.id]
        )
        child_ids = (child_id for (child_id,) in child_rows)
        children = set(self.group_getter_many(child_ids))
        return children

    def get_parents(self):
        query = f'SELECT parentid FROM {self.group_table} WHERE memberid == ?'
        parent_rows = self.photodb.sql_select(query, [self.id])
        parent_ids = (parent_id for (parent_id,) in parent_rows)
        parents = set(self.group_getter_many(parent_ids))
        return parents

    def has_ancestor(self, ancestor):
        return ancestor in self.walk_parents()

    def has_any_child(self):
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? LIMIT 1'
        row = self.photodb.sql_select_one(query, [self.id])
        return row is not None

    def has_any_parent(self):
        query = f'SELECT 1 FROM {self.group_table} WHERE memberid == ? LIMIT 1'
        row = self.photodb.sql_select_one(query, [self.id])
        return row is not None

    def has_child(self, member):
        self.assert_same_type(member)
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? AND memberid == ?'
        row = self.photodb.sql_select_one(query, [self.id, member.id])
        return row is not None

    def has_descendant(self, descendant):
        return self in descendant.walk_parents()

    def has_parent(self, parent):
        self.assert_same_type(parent)
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? AND memberid == ?'
        row = self.photodb.sql_select_one(query, [parent.id, self.id])
        return row is not None

    def __remove_child(self, member):
        if not self.has_child(member):
            return BAIL

        self.photodb.log.info('Removing child %s from %s.', member, self)

        pairs = {
            'parentid': self.id,
            'memberid': member.id,
        }
        self.photodb.sql_delete(table=self.group_table, pairs=pairs)
    @abc.abstractmethod
    def remove_child(self, member):
        return self.__remove_child(member)

    @abc.abstractmethod
    def remove_children(self, members):
        bail = True
        for member in members:
            bail = (self.__remove_child(member) is BAIL) and bail
        if bail:
            return BAIL

    def walk_children(self):
        '''
        Yield self and all descendants.
        '''
        yield self
        for child in self.get_children():
            yield from child.walk_children()

    def walk_parents(self):
        '''
        Yield all ancestors, but not self, in no particular order.
        '''
        parents = self.get_parents()
        seen = set(parents)
        todo = list(parents)
        while len(todo) > 0:
            parent = todo.pop(-1)
            yield parent
            seen.add(parent)
            more_parents = set(parent.get_parents())
            more_parents = more_parents.difference(seen)
            todo.extend(more_parents)

class Album(ObjectBase, GroupableMixin):
    table = 'albums'
    group_table = 'album_group_rel'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        db_row = normalize_db_row(db_row, self.table)

        self.id = db_row['id']
        self.title = self.normalize_title(db_row['title'])
        self.description = self.normalize_description(db_row['description'])
        self.author_id = self.normalize_author_id(db_row['author_id'])

        self.group_getter_many = self.photodb.get_albums_by_id

        self._sum_bytes_local = None
        self._sum_bytes_recursive = None
        self._sum_photos_recursive = None

    def __repr__(self):
        return f'Album:{self.id}'

    def __str__(self):
        if self.title:
            return f'Album:{self.id}:{self.title}'
        else:
            return f'Album:{self.id}'

    @staticmethod
    def normalize_description(description):
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError(f'Description must be {str}, not {type(description)}.')

        description = description.strip()

        return description

    @staticmethod
    def normalize_title(title):
        if title is None:
            return ''

        if not isinstance(title, str):
            raise TypeError(f'Title must be {str}, not {type(title)}.')

        title = stringtools.collapse_whitespace(title)

        return title

    def _uncache(self):
        self.photodb.caches['album'].remove(self.id)

    def _add_associated_directory(self, path):
        path = pathclass.Path(path)

        if not path.is_dir:
            raise ValueError(f'{path} is not a directory.')

        if self.has_associated_directory(path):
            return

        self.photodb.log.info('Adding directory "%s" to %s.', path.absolute_path, self)
        data = {'albumid': self.id, 'directory': path.absolute_path}
        self.photodb.sql_insert(table='album_associated_directories', data=data)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_associated_directory(self, path):
        '''
        Add a directory from which this album will pull files during rescans.
        These relationships are not unique and multiple albums can associate
        with the same directory if desired.
        '''
        self._add_associated_directory(path)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_associated_directories(self, paths):
        for path in paths:
            self._add_associated_directory(path)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_child(self, *args, **kwargs):
        return super().add_child(*args, **kwargs)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_children(self, *args, **kwargs):
        return super().add_children(*args, **kwargs)

    def _add_photo(self, photo):
        self.photodb.log.info('Adding photo %s to %s.', photo, self)
        data = {'albumid': self.id, 'photoid': photo.id}
        self.photodb.sql_insert(table='album_photo_rel', data=data)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_photo(self, photo):
        if self.has_photo(photo):
            return

        self._add_photo(photo)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_photos(self, photos):
        existing_photos = set(self.get_photos())
        photos = set(photos)
        photos = photos.difference(existing_photos)

        for photo in photos:
            self._add_photo(photo)

    # Photo.add_tag already has @required_feature
    @decorators.transaction
    def add_tag_to_all(self, tag, *, nested_children=True):
        '''
        Add this tag to every photo in the album. Saves you from having to
        write the for-loop yourself.

        nested_children:
            If True, add the tag to photos contained in sub-albums.
            Otherwise, only local photos.
        '''
        tag = self.photodb.get_tag(name=tag)
        if nested_children:
            photos = self.walk_photos()
        else:
            photos = self.get_photos()

        for photo in photos:
            photo.add_tag(tag)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def delete(self, *, delete_children=False):
        self.photodb.log.info('Deleting %s.', self)
        GroupableMixin.delete(self, delete_children=delete_children)
        self.photodb.sql_delete(table='album_associated_directories', pairs={'albumid': self.id})
        self.photodb.sql_delete(table='album_photo_rel', pairs={'albumid': self.id})
        self.photodb.sql_delete(table='albums', pairs={'id': self.id})
        self._uncache()
        self.deleted = True

    @property
    def display_name(self):
        if self.title:
            return self.title
        else:
            return self.id

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def edit(self, title=None, description=None):
        '''
        Change the title or description. Leave None to keep current value.
        '''
        if title is None and description is None:
            return

        if title is not None:
            title = self.normalize_title(title)

        if description is not None:
            description = self.normalize_description(description)

        data = {
            'id': self.id,
            'title': title,
            'description': description,
        }
        self.photodb.sql_update(table='albums', pairs=data, where_key='id')
        self.title = title
        self.description = description

    @property
    def full_name(self):
        if self.title:
            return f'{self.id} - {self.title}'
        else:
            return self.id

    def get_associated_directories(self):
        directory_rows = self.photodb.sql_select(
            'SELECT directory FROM album_associated_directories WHERE albumid == ?',
            [self.id]
        )
        directories = set(pathclass.Path(directory) for (directory,) in directory_rows)
        return directories

    def get_photos(self):
        photos = []
        photo_rows = self.photodb.sql_select(
            'SELECT photoid FROM album_photo_rel WHERE albumid == ?',
            [self.id]
        )
        photo_ids = (photo_id for (photo_id,) in photo_rows)
        photos = set(self.photodb.get_photos_by_id(photo_ids))
        return photos

    def has_any_associated_directory(self):
        '''
        Return True if this album has at least 1 associated directory.
        '''
        row = self.photodb.sql_select_one(
            'SELECT 1 FROM album_associated_directories WHERE albumid == ?',
            [self.id]
        )
        return row is not None

    def has_any_photo(self, recurse=False):
        '''
        Return True if this album contains at least 1 photo.

        recurse:
            If True, photos in child albums satisfy.
            If False, only consider this album.
        '''
        row = self.photodb.sql_select_one(
            'SELECT 1 FROM album_photo_rel WHERE albumid == ? LIMIT 1',
            [self.id]
        )
        if row is not None:
            return True
        if recurse:
            return self.has_any_subalbum_photo()
        return False

    def has_any_subalbum_photo(self):
        '''
        Return True if any descendent album has any photo, ignoring whether
        this particular album itself has photos.
        '''
        return any(child.has_any_photo(recurse=True) for child in self.get_children())

    def has_associated_directory(self, path):
        path = pathclass.Path(path)
        row = self.photodb.sql_select_one(
            'SELECT 1 FROM album_associated_directories WHERE albumid == ? AND directory == ?',
            [self.id, path.absolute_path]
        )
        return row is not None

    def has_photo(self, photo):
        row = self.photodb.sql_select_one(
            'SELECT 1 FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        return row is not None

    def jsonify(self, minimal=False):
        j = {
            'type': 'album',
            'id': self.id,
            'description': self.description,
            'title': self.title,
            'author': self.get_author().jsonify() if self.author_id else None,
        }
        if not minimal:
            j['photos'] = [photo.jsonify(include_albums=False) for photo in self.get_photos()]
            j['parents'] = [parent.jsonify(minimal=True) for parent in self.get_parents()]
            j['sub_albums'] = [child.jsonify(minimal=True) for child in self.get_children()]

        return j

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def remove_child(self, *args, **kwargs):
        return super().remove_child(*args, **kwargs)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def remove_children(self, *args, **kwargs):
        return super().remove_children(*args, **kwargs)

    def _remove_photo(self, photo):
        self.photodb.log.info('Removing photo %s from %s.', photo, self)
        pairs = {'albumid': self.id, 'photoid': photo.id}
        self.photodb.sql_delete(table='album_photo_rel', pairs=pairs)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def remove_photo(self, photo):
        self._remove_photo(photo)

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def remove_photos(self, photos):
        existing_photos = set(self.get_photos())
        photos = set(photos)
        photos = photos.intersection(existing_photos)

        for photo in photos:
            self._remove_photo(photo)

    def sum_bytes(self, recurse=True):
        query = '''
        SELECT SUM(bytes) FROM photos
        WHERE photos.id IN (
            SELECT photoid FROM album_photo_rel WHERE
            albumid IN {albumids}
        )
        '''
        if recurse:
            albumids = [child.id for child in self.walk_children()]
        else:
            albumids = [self.id]

        albumids = sqlhelpers.listify(albumids)
        query = query.format(albumids=albumids)
        total = self.photodb.sql_select_one(query)[0]
        return total

    def sum_photos(self, recurse=True):
        '''
        If all you need is the number of photos in the album, this method is
        preferable to len(album.get_photos()) because it performs the counting
        in the database instead of creating the Photo objects.
        '''
        query = '''
        SELECT COUNT(photoid)
        FROM album_photo_rel
        WHERE albumid IN {albumids}
        '''
        if recurse:
            albumids = [child.id for child in self.walk_children()]
        else:
            albumids = [self.id]

        albumids = sqlhelpers.listify(albumids)
        query = query.format(albumids=albumids)
        total = self.photodb.sql_select_one(query)[0]
        return total

    def walk_photos(self):
        yield from self.get_photos()
        children = self.walk_children()
        # The first yield is itself
        next(children)
        for child in children:
            yield from child.walk_photos()

class Bookmark(ObjectBase):
    table = 'bookmarks'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        db_row = normalize_db_row(db_row, self.table)

        self.id = db_row['id']
        self.title = self.normalize_title(db_row['title'])
        self.url = self.normalize_url(db_row['url'])
        self.author_id = self.normalize_author_id(db_row['author_id'])

    def __repr__(self):
        return f'Bookmark:{self.id}'

    @staticmethod
    def normalize_title(title):
        if title is None:
            return ''

        if not isinstance(title, str):
            raise TypeError(f'Title must be {str}, not {type(title)}.')

        title = stringtools.collapse_whitespace(title)

        return title

    @staticmethod
    def normalize_url(url):
        if url is None:
            return ''

        if not isinstance(url, str):
            raise TypeError(f'URL must be {str}, not {type(url)}.')

        url = url.strip()

        if not url:
            raise ValueError(f'URL can not be blank.')

        return url

    def _uncache(self):
        self.photodb.caches['bookmark'].remove(self.id)

    @decorators.required_feature('bookmark.edit')
    @decorators.transaction
    def delete(self):
        self.photodb.sql_delete(table='bookmarks', pairs={'id': self.id})
        self._uncache()
        self.deleted = True

    @property
    def display_name(self):
        if self.title:
            return self.title
        else:
            return self.id

    @decorators.required_feature('bookmark.edit')
    @decorators.transaction
    def edit(self, title=None, url=None):
        '''
        Change the title or URL. Leave None to keep current.
        '''
        if title is None and url is None:
            return

        if title is not None:
            title = self.normalize_title(title)

        if url is not None:
            url = self.normalize_url(url)

        data = {
            'id': self.id,
            'title': title,
            'url': url,
        }
        self.photodb.sql_update(table='bookmarks', pairs=data, where_key='id')
        self.title = title
        self.url = url

    def jsonify(self):
        j = {
            'type': 'bookmark',
            'id': self.id,
            'author': self.get_author().jsonify() if self.author_id else None,
            'url': self.url,
            'title': self.title,
        }
        return j

class Photo(ObjectBase):
    '''
    A PhotoDB entry containing information about an image file.
    Photo objects cannot exist without a corresponding PhotoDB object, because
    Photos are not the actual image data, just the database entry.
    '''
    table = 'photos'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        db_row = normalize_db_row(db_row, self.table)

        self.real_path = db_row['filepath']
        self.real_path = helpers.remove_path_badchars(self.real_path, allowed=':\\/')
        self.real_path = pathclass.Path(self.real_path)

        self.id = db_row['id']
        self.created = db_row['created']
        self.author_id = self.normalize_author_id(db_row['author_id'])
        self.override_filename = db_row['override_filename']
        self.extension = db_row['extension']
        self.tagged_at = db_row['tagged_at']

        if self.extension == '':
            self.dot_extension = ''
        else:
            self.dot_extension = '.' + self.extension

        self.area = db_row['area']
        self.bytes = db_row['bytes']
        self.duration = db_row['duration']
        self.width = db_row['width']
        self.height = db_row['height']
        self.ratio = db_row['ratio']

        if db_row['thumbnail'] is not None:
            self.thumbnail = self.photodb.thumbnail_directory.join(db_row['thumbnail'])
        else:
            self.thumbnail = None

        self.searchhidden = db_row['searchhidden']

        self.mimetype = helpers.get_mimetype(self.real_path.basename)
        if self.mimetype is None:
            self.simple_mimetype = None
        else:
            self.simple_mimetype = self.mimetype.split('/')[0]

    def __reinit__(self):
        '''
        Reload the row from the database and do __init__ with them.
        '''
        row = self.photodb.sql_select_one('SELECT * FROM photos WHERE id == ?', [self.id])
        self.__init__(self.photodb, row)

    def __repr__(self):
        return f'Photo:{self.id}'

    def __str__(self):
        return f'Photo:{self.id}:{self.basename}'

    @staticmethod
    def normalize_override_filename(override_filename):
        if override_filename is None:
            return None

        cleaned = helpers.remove_path_badchars(override_filename)
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError(f'"{override_filename}" is not valid.')

        return cleaned

    def _uncache(self):
        self.photodb.caches['photo'].remove(self.id)

    @decorators.required_feature('photo.add_remove_tag')
    @decorators.transaction
    def add_tag(self, tag):
        tag = self.photodb.get_tag(name=tag)

        existing = self.has_tag(tag, check_children=False)
        if existing:
            return existing

        # If the new tag is less specific than one we already have,
        # keep our current one.
        existing = self.has_tag(tag, check_children=True)
        if existing:
            self.photodb.log.debug('Preferring existing %s over %s.', existing, tag)
            return existing

        # If the new tag is more specific, remove our current one for it.
        for parent in tag.walk_parents():
            if self.has_tag(parent, check_children=False):
                self.photodb.log.debug('Preferring new %s over %s.', tag, parent)
                self.remove_tag(parent)

        self.photodb.log.info('Applying %s to %s.', tag, self)

        data = {
            'photoid': self.id,
            'tagid': tag.id
        }
        self.photodb.sql_insert(table='photo_tag_rel', data=data)
        data = {
            'id': self.id,
            'tagged_at': helpers.now(),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        return tag

    @property
    def basename(self):
        return self.override_filename or self.real_path.basename

    @property
    def bitrate(self):
        if self.duration and self.bytes is not None:
            return (self.bytes / 128) / self.duration
        else:
            return None

    @property
    def bytestring(self):
        if self.bytes is not None:
            return bytestring.bytestring(self.bytes)
        return '??? b'

    # Photo.add_tag already has @required_feature add_remove_tag
    @decorators.transaction
    def copy_tags(self, other_photo):
        '''
        Take all of the tags owned by other_photo and apply them to this photo.
        '''
        for tag in other_photo.get_tags():
            self.add_tag(tag)

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def delete(self, *, delete_file=False):
        '''
        Delete the Photo and its relation to any tags and albums.
        '''
        self.photodb.log.info('Deleting %s.', self)
        self.photodb.sql_delete(table='photo_tag_rel', pairs={'photoid': self.id})
        self.photodb.sql_delete(table='album_photo_rel', pairs={'photoid': self.id})
        self.photodb.sql_delete(table='photos', pairs={'id': self.id})

        if delete_file:
            path = self.real_path.absolute_path
            if self.photodb.config['recycle_instead_of_delete']:
                self.photodb.log.debug('Recycling %s.', path)
                action = send2trash.send2trash
            else:
                self.photodb.log.debug('Deleting %s.', path)
                action = os.remove

            self.photodb.on_commit_queue.append({
                'action': action,
                'args': [path],
            })
            if self.thumbnail and self.thumbnail.is_file:
                self.photodb.on_commit_queue.append({
                    'action': action,
                    'args': [self.thumbnail.absolute_path],
                })

        self._uncache()
        self.deleted = True

    @property
    def duration_string(self):
        if self.duration is None:
            return None
        return hms.seconds_to_hms(self.duration)

    #@decorators.time_me
    @decorators.required_feature('photo.generate_thumbnail')
    @decorators.transaction
    def generate_thumbnail(self, **special):
        '''
        special:
            For videos, you can provide a `timestamp` to take the thumbnail at.
        '''
        hopeful_filepath = self.make_thumbnail_filepath()
        return_filepath = None

        if self.simple_mimetype == 'image':
            self.photodb.log.info('Thumbnailing %s.', self.real_path.absolute_path)
            try:
                image = helpers.generate_image_thumbnail(
                    self.real_path.absolute_path,
                    width=self.photodb.config['thumbnail_width'],
                    height=self.photodb.config['thumbnail_height'],
                )
            except (OSError, ValueError):
                traceback.print_exc()
            else:
                image.save(hopeful_filepath.absolute_path, quality=50)
                return_filepath = hopeful_filepath

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            self.photodb.log.info('Thumbnailing %s.', self.real_path.absolute_path)
            try:
                success = helpers.generate_video_thumbnail(
                    self.real_path.absolute_path,
                    outfile=hopeful_filepath.absolute_path,
                    width=self.photodb.config['thumbnail_width'],
                    height=self.photodb.config['thumbnail_height'],
                    **special
                )
            except Exception:
                traceback.print_exc()
            else:
                if success:
                    return_filepath = hopeful_filepath

        if return_filepath != self.thumbnail:
            if return_filepath is not None:
                return_filepath = return_filepath.absolute_path
            data = {
                'id': self.id,
                'thumbnail': return_filepath,
            }
            self.photodb.sql_update(table='photos', pairs=data, where_key='id')
            self.thumbnail = return_filepath

        self._uncache()

        self.__reinit__()
        return self.thumbnail

    def get_containing_albums(self):
        '''
        Return the albums of which this photo is a member.
        '''
        album_rows = self.photodb.sql_select(
            'SELECT albumid FROM album_photo_rel WHERE photoid == ?',
            [self.id]
        )
        album_ids = (album_id for (album_id,) in album_rows)
        albums = set(self.photodb.get_albums_by_id(album_ids))
        return albums

    def get_tags(self):
        '''
        Return the tags assigned to this Photo.
        '''
        tag_rows = self.photodb.sql_select(
            'SELECT tagid FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        )
        tag_ids = (tag_id for (tag_id,) in tag_rows)
        tags = set(self.photodb.get_tags_by_id(tag_ids))
        return tags

    def has_tag(self, tag, *, check_children=True):
        '''
        Return the Tag object if this photo contains that tag.
        Otherwise return False.

        check_children:
            If True, children of the requested tag are accepted.
        '''
        tag = self.photodb.get_tag(name=tag)

        if check_children:
            tag_options = tag.walk_children()
        else:
            tag_options = [tag]

        tag_by_id = {t.id: t for t in tag_options}
        tag_option_ids = sqlhelpers.listify(tag_by_id)
        rel_row = self.photodb.sql_select_one(
            f'SELECT tagid FROM photo_tag_rel WHERE photoid == ? AND tagid IN {tag_option_ids}',
            [self.id]
        )

        if rel_row is None:
            return False

        return tag_by_id[rel_row[0]]

    def jsonify(self, include_albums=True, include_tags=True):
        j = {
            'type': 'photo',
            'id': self.id,
            'author': self.get_author().jsonify() if self.author_id else None,
            'extension': self.extension,
            'width': self.width,
            'height': self.height,
            'ratio': self.ratio,
            'area': self.area,
            'bytes': self.bytes,
            'duration_str': self.duration_string,
            'duration': self.duration,
            'bytes_str': self.bytestring,
            'has_thumbnail': bool(self.thumbnail),
            'created': self.created,
            'filename': self.basename,
            'mimetype': self.mimetype,
            'searchhidden': bool(self.searchhidden),
        }
        if include_albums:
            j['albums'] = [album.jsonify(minimal=True) for album in self.get_containing_albums()]

        if include_tags:
            j['tags'] = [tag.jsonify(minimal=True) for tag in self.get_tags()]

        return j

    def make_thumbnail_filepath(self):
        '''
        Create the filepath that should be the location of our thumbnail.
        '''
        chunked_id = [''.join(chunk) for chunk in gentools.chunk_generator(self.id, 3)]
        (folder, basename) = (chunked_id[:-1], chunked_id[-1])
        folder = os.sep.join(folder)
        folder = self.photodb.thumbnail_directory.join(folder)
        if folder:
            folder.makedirs(exist_ok=True)
        hopeful_filepath = folder.with_child(basename + '.jpg')
        return hopeful_filepath

    # Photo.rename_file already has @required_feature
    @decorators.transaction
    def move_file(self, directory):
        directory = pathclass.Path(directory)
        directory.assert_is_directory()
        new_path = directory.with_child(self.real_path.basename)
        new_path.assert_not_exists()
        self.rename_file(new_path.absolute_path, move=True)

    def _reload_image_metadata(self):
        try:
            image = PIL.Image.open(self.real_path.absolute_path)
        except (OSError, ValueError):
            traceback.print_exc()
            return

        (self.width, self.height) = image.size
        image.close()

    def _reload_video_metadata(self):
        if not constants.ffmpeg:
            return

        try:
            probe = constants.ffmpeg.probe(self.real_path.absolute_path)
        except Exception:
            traceback.print_exc()
            return

        if not probe or not probe.video:
            return

        self.width = probe.video.video_width
        self.height = probe.video.video_height
        self.duration = probe.format.duration or probe.video.duration

    def _reload_audio_metadata(self):
        if not constants.ffmpeg:
            return

        try:
            probe = constants.ffmpeg.probe(self.real_path.absolute_path)
        except Exception:
            traceback.print_exc()
            return

        if not probe or not probe.audio:
            return

        self.duration = probe.audio.duration

    #@decorators.time_me
    @decorators.required_feature('photo.reload_metadata')
    @decorators.transaction
    def reload_metadata(self):
        '''
        Load the file's height, width, etc as appropriate for this type of file.
        '''
        self.photodb.log.info('Reloading metadata for %s.', self)

        self.bytes = None
        self.dev_ino = None
        self.width = None
        self.height = None
        self.area = None
        self.ratio = None
        self.duration = None

        if self.real_path.is_file:
            stat = self.real_path.stat
            self.bytes = stat.st_size
            (dev, ino) = (stat.st_dev, stat.st_ino)
            if dev and ino:
                self.dev_ino = f'{dev},{ino}'

        if self.bytes is None:
            pass

        elif self.simple_mimetype == 'image':
            self._reload_image_metadata()

        elif self.simple_mimetype == 'video':
            self._reload_video_metadata()

        elif self.simple_mimetype == 'audio':
            self._reload_audio_metadata()

        if self.width and self.height:
            self.area = self.width * self.height
            self.ratio = round(self.width / self.height, 2)

        data = {
            'id': self.id,
            'width': self.width,
            'height': self.height,
            'area': self.area,
            'ratio': self.ratio,
            'duration': self.duration,
            'bytes': self.bytes,
            'dev_ino': self.dev_ino,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        self._uncache()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def relocate(self, new_filepath):
        '''
        Point the Photo object to a different filepath.

        DOES NOT MOVE THE FILE, only acknowledges a move that was performed
        outside of the system.
        To rename or move the file, use `rename_file`.
        '''
        new_filepath = pathclass.Path(new_filepath)
        if not new_filepath.is_file:
            raise FileNotFoundError(new_filepath.absolute_path)

        self.photodb.assert_no_such_photo_by_path(filepath=new_filepath)

        self.photodb.log.info('Relocating %s to "%s".', self, new_filepath.absolute_path)
        data = {
            'id': self.id,
            'filepath': new_filepath.absolute_path,
            'basename': new_filepath.basename,
            'extension': new_filepath.extension.no_dot,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')
        self.real_path = new_filepath
        self._uncache()

    @decorators.required_feature('photo.add_remove_tag')
    @decorators.transaction
    def remove_tag(self, tag):
        tag = self.photodb.get_tag(name=tag)

        self.photodb.log.info('Removing %s from %s.', tag, self)
        pairs = {'photoid': self.id, 'tagid': tag.id}
        self.photodb.sql_delete(table='photo_tag_rel', pairs=pairs)

        data = {
            'id': self.id,
            'tagged_at': helpers.now(),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

    @decorators.required_feature('photo.add_remove_tag')
    @decorators.transaction
    def remove_tags(self, tags):
        tags = [self.photodb.get_tag(name=tag) for tag in tags]

        self.photodb.log.info('Removing %s from %s.', tags, self)
        query = f'''
        DELETE FROM photo_tag_rel
        WHERE tagid IN {sqlhelpers.listify(tag.id for tag in tags)}
        '''
        self.photodb.sql_execute(query)

        data = {
            'id': self.id,
            'tagged_at': helpers.now(),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def rename_file(self, new_filename, *, move=False):
        '''
        Rename the file on the disk as well as in the database.

        move:
            If True, allow the file to be moved into another directory.
            Otherwise, the rename must be local.
        '''
        old_path = self.real_path
        old_path.correct_case()

        new_filename = helpers.remove_path_badchars(new_filename, allowed=':\\/')
        if os.path.dirname(new_filename) == '':
            new_path = old_path.parent.with_child(new_filename)
        else:
            new_path = pathclass.Path(new_filename)
        #new_path.correct_case()
        if (new_path.parent != old_path.parent) and not move:
            raise ValueError('Cannot move the file without param move=True.')

        if new_path.absolute_path == old_path.absolute_path:
            raise ValueError('The new and old names are the same.')

        new_path.assert_not_exists()

        self.photodb.log.info('Renaming file "%s" -> "%s".', old_path.absolute_path, new_path.absolute_path)

        new_path.parent.makedirs(exist_ok=True)

        # The plan is to make a hardlink now, then delete the original file
        # during commit. This only applies to normcase != normcase, because on
        # case-insensitive systems (Windows), if we're trying to rename "AFILE"
        # to "afile", we will not be able to hardlink nor copy the file to the
        # new name, we'll just want to do an os.rename during commit.
        if new_path.normcase != old_path.normcase:
            # If we're on the same partition, make a hardlink.
            # Otherwise make a copy.
            try:
                os.link(old_path.absolute_path, new_path.absolute_path)
            except OSError:
                spinal.copy_file(old_path, new_path)

        data = {
            'id': self.id,
            'filepath': new_path.absolute_path,
            'basename': new_path.basename,
            'extension': new_path.extension.no_dot,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')
        self.real_path = new_path

        if new_path.normcase == old_path.normcase:
            # If they are equivalent but differently cased, just rename.
            self.photodb.on_commit_queue.append({
                'action': os.rename,
                'args': [old_path.absolute_path, new_path.absolute_path],
            })
        else:
            # Delete the original, leaving only the new copy / hardlink.
            self.photodb.on_commit_queue.append({
                'action': os.remove,
                'args': [old_path.absolute_path],
            })
            self.photodb.on_rollback_queue.append({
                'action': os.remove,
                'args': [new_path.absolute_path],
            })

        self._uncache()

        self.__reinit__()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def set_override_filename(self, new_filename):
        new_filename = self.normalize_override_filename(new_filename)

        data = {
            'id': self.id,
            'override_filename': new_filename,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')
        self.override_filename = new_filename

        self.__reinit__()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def set_searchhidden(self, searchhidden):
        data = {
            'id': self.id,
            'searchhidden': bool(searchhidden),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')
        self.searchhidden = searchhidden

class Tag(ObjectBase, GroupableMixin):
    '''
    A Tag, which can be applied to Photos for organization.
    '''
    table = 'tags'
    group_table = 'tag_group_rel'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        db_row = normalize_db_row(db_row, self.table)

        self.id = db_row['id']
        # Do not pass the name through the normalizer. It may be grandfathered
        # from previous character / length rules.
        self.name = db_row['name']
        self.description = self.normalize_description(db_row['description'])
        self.author_id = self.normalize_author_id(db_row['author_id'])

        self.group_getter_many = self.photodb.get_tags_by_id

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return f'Tag:{self.id}:{self.name}'

    def __str__(self):
        return f'Tag:{self.name}'

    @staticmethod
    def normalize_description(description):
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError(f'Description must be {str}, not {type(description)}.')

        description = description.strip()

        return description

    @staticmethod
    def normalize_name(name, min_length=None, max_length=None):
        original_name = name
        # if valid_chars is None:
        #     valid_chars = constants.DEFAULT_CONFIGURATION['tag']['valid_chars']

        name = name.lower()
        name = stringtools.remove_control_characters(name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip(' .+')
        name = name.split('+')[0].split('.')[-1]
        name = name.replace('-', '_')
        name = name.replace(' ', '_')
        name = name.replace('=', '')
        # name = ''.join(c for c in name if c in valid_chars)

        if min_length is not None and len(name) < min_length:
            raise exceptions.TagTooShort(original_name)

        if max_length is not None and len(name) > max_length:
            raise exceptions.TagTooLong(name)

        return name

    def _uncache(self):
        self.photodb.caches['tag'].remove(self.id)

    def _add_child(self, member):
        ret = super()._add_child(member)
        if ret is BAIL:
            return BAIL

        # Suppose a photo has tags A and B. Then, B is added as a child of A.
        # We should remove A from the photo leaving only the more specific B.
        # We must walk all ancestors, not just the immediate parent, because
        # the same situation could apply to a photo that has tag A, where A
        # already has children B.C.D, and then E is added as a child of D,
        # obsoleting A.
        # I expect that this method, which calls `search`, will be inefficient
        # when used in a large `add_children` loop. I would consider batching
        # up all the ancestors and doing it all at once. Just need to make sure
        # I don't cause any collateral damage e.g. removing A from a photo that
        # only has A because some other photo with A and B thinks A is obsolete.
        # This technique is nice and simple to understand for now.
        ancestors = list(member.walk_parents())
        photos = self.photodb.search(tag_musts=[member], is_searchhidden=None, yield_albums=False)
        for photo in photos:
            photo.remove_tags(ancestors)

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def add_child(self, *args, **kwargs):
        ret = super().add_child(*args, **kwargs)
        if ret is BAIL:
            return
        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def add_children(self, *args, **kwargs):
        ret = super().add_children(*args, **kwargs)
        if ret is BAIL:
            return
        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def add_synonym(self, synname):
        synname = self.photodb.normalize_tagname(synname)

        if synname == self.name:
            raise exceptions.CantSynonymSelf(self)

        self.photodb.assert_no_such_tag(name=synname)

        self.photodb.log.info('New synonym %s of %s.', synname, self.name)

        self.photodb.caches['tag_exports'].clear()

        data = {
            'name': synname,
            'mastername': self.name,
        }
        self.photodb.sql_insert(table='tag_synonyms', data=data)

        return synname

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def convert_to_synonym(self, mastertag):
        '''
        Convert this tag into a synonym for a different tag.
        All photos which possess the current tag will have it replaced with the
        new master tag.
        All synonyms of the old tag will point to the new tag.

        Good for when two tags need to be merged under a single name.
        '''
        mastertag = self.photodb.get_tag(name=mastertag)

        self.photodb.caches['tag_exports'].clear()

        # Migrate the old tag's synonyms to the new one
        # UPDATE is safe for this operation because there is no chance of duplicates.
        data = {
            'mastername': (self.name, mastertag.name),
        }
        self.photodb.sql_update(table='tag_synonyms', pairs=data, where_key='mastername')

        # Because these were two separate tags, perhaps in separate trees, it
        # is possible for a photo to have both at the moment.
        #
        # If they already have both, the deletion of the syn rel will happen
        #    when the syn tag is deleted.
        # If they only have the syn, we will UPDATE it to the master.
        # If they only have the master, nothing needs to happen.

        # Find photos that have the old tag and DON'T already have the new one.
        query = '''
        SELECT photoid FROM photo_tag_rel p1
        WHERE tagid == ?
        AND NOT EXISTS (
            SELECT 1 FROM photo_tag_rel p2
            WHERE p1.photoid == p2.photoid
            AND tagid == ?
        )
        '''
        bindings = [self.id, mastertag.id]
        photo_rows = self.photodb.sql_execute(query, bindings)
        replace_photoids = [photo_id for (photo_id,) in photo_rows]

        # For those photos that only had the syn, simply replace with master.
        if replace_photoids:
            query = f'''
            UPDATE photo_tag_rel
            SET tagid = ?
            WHERE tagid == ?
            AND photoid IN {sqlhelpers.listify(replace_photoids)}
            '''
            bindings = [mastertag.id, self.id]
            self.photodb.sql_execute(query, bindings)

        # For photos that have the old tag and DO already have the new one,
        # don't worry because the old rels will be deleted when the tag is
        # deleted.
        self.delete()

        # Enjoy your new life as a monk.
        mastertag.add_synonym(self.name)

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def delete(self, *, delete_children=False):
        self.photodb.log.info('Deleting %s.', self)
        super().delete(delete_children=delete_children)
        self.photodb.sql_delete(table='photo_tag_rel', pairs={'tagid': self.id})
        self.photodb.sql_delete(table='tag_synonyms', pairs={'mastername': self.name})
        self.photodb.sql_delete(table='tags', pairs={'id': self.id})
        self.photodb.caches['tag_exports'].clear()
        self._uncache()
        self.deleted = True

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def edit(self, description=None):
        '''
        Change the description. Leave None to keep current value.
        '''
        if description is None:
            return

        description = self.normalize_description(description)

        data = {
            'id': self.id,
            'description': description,
        }
        self.photodb.sql_update(table='tags', pairs=data, where_key='id')
        self.description = description

        self._uncache()

    def get_synonyms(self):
        syn_rows = self.photodb.sql_select(
            'SELECT name FROM tag_synonyms WHERE mastername == ?',
            [self.name]
        )
        synonyms = set(name for (name,) in syn_rows)
        return synonyms

    def jsonify(self, include_synonyms=False, minimal=False):
        j = {
            'type': 'tag',
            'id': self.id,
            'name': self.name,
        }
        if not minimal:
            j['author'] = self.get_author().jsonify() if self.author_id else None,
            j['description'] = self.description
            j['children'] = [child.jsonify(minimal=True) for child in self.get_children()]

        if include_synonyms:
            j['synonyms'] = list(self.get_synonyms())

        return j

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def remove_child(self, *args, **kwargs):
        ret = super().remove_child(*args, **kwargs)
        if ret is BAIL:
            return
        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def remove_children(self, *args, **kwargs):
        ret = super().remove_children(*args, **kwargs)
        if ret is BAIL:
            return
        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def remove_synonym(self, synname):
        '''
        Delete a synonym.
        This will have no effect on photos or other synonyms because
        they always resolve to the master tag before application.
        '''
        synname = self.photodb.normalize_tagname(synname)
        if synname == self.name:
            raise exceptions.NoSuchSynonym(synname)

        syn_exists = self.photodb.sql_select_one(
            'SELECT 1 FROM tag_synonyms WHERE mastername == ? AND name == ?',
            [self.name, synname]
        )

        if syn_exists is None:
            raise exceptions.NoSuchSynonym(synname)

        self.photodb.caches['tag_exports'].clear()
        self.photodb.sql_delete(table='tag_synonyms', pairs={'name': synname})

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def rename(self, new_name, *, apply_to_synonyms=True):
        '''
        Rename the tag. Does not affect its relation to Photos or tag groups.
        '''
        new_name = self.photodb.normalize_tagname(new_name)
        old_name = self.name
        if new_name == old_name:
            return

        try:
            self.photodb.get_tag(name=new_name)
        except exceptions.NoSuchTag:
            pass
        else:
            raise exceptions.TagExists(new_name)

        self.photodb.caches['tag_exports'].clear()

        data = {
            'id': self.id,
            'name': new_name,
        }
        self.photodb.sql_update(table='tags', pairs=data, where_key='id')

        if apply_to_synonyms:
            data = {
                'mastername': (old_name, new_name),
            }
            self.photodb.sql_update(table='tag_synonyms', pairs=data, where_key='mastername')

        self.name = new_name
        self._uncache()

class User(ObjectBase):
    '''
    A dear friend of ours.
    '''
    table = 'users'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        db_row = normalize_db_row(db_row, self.table)

        self.id = db_row['id']
        self.username = db_row['username']
        self.created = db_row['created']
        self.password_hash = db_row['password']
        # Do not enforce maxlen here, they may be grandfathered in.
        self._display_name = self.normalize_display_name(db_row['display_name'])

    def __repr__(self):
        return f'User:{self.id}:{self.username}'

    def __str__(self):
        return f'User:{self.username}'

    @staticmethod
    def normalize_display_name(display_name, max_length=None):
        if display_name is None:
            return None

        if not isinstance(display_name, str):
            raise TypeError(f'Display name must be string, not {type(display_name)}.')

        display_name = stringtools.collapse_whitespace(display_name)

        if display_name == '':
            return None

        if max_length is not None and len(display_name) > max_length:
            raise exceptions.DisplayNameTooLong(display_name=display_name, max_length=max_length)

        return display_name

    @property
    def display_name(self):
        if self._display_name is None:
            return self.username
        else:
            return self._display_name

    def jsonify(self):
        j = {
            'type': 'user',
            'id': self.id,
            'username': self.username,
            'created': self.created,
            'display_name': self.display_name,
        }
        return j

    @decorators.required_feature('user.edit')
    @decorators.transaction
    def set_display_name(self, display_name):
        display_name = self.normalize_display_name(
            display_name,
            max_length=self.photodb.config['user']['max_display_name_length'],
        )

        data = {
            'id': self.id,
            'display_name': display_name,
        }
        self.photodb.sql_update(table='users', pairs=data, where_key='id')
        self._display_name = display_name

class WarningBag:
    def __init__(self):
        self.warnings = set()

    def add(self, warning):
        self.warnings.add(warning)
