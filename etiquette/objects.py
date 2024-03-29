'''
This file provides the data objects that should not be instantiated directly,
but are returned by the PDB accesses.
'''
import abc
import bcrypt
import bs4
import datetime
import hashlib
import os
import PIL.Image
import re
import send2trash
import time
import traceback
import typing

from voussoirkit import bytestring
from voussoirkit import dotdict
from voussoirkit import expressionmatch
from voussoirkit import gentools
from voussoirkit import hms
from voussoirkit import imagetools
from voussoirkit import pathclass
from voussoirkit import sentinel
from voussoirkit import spinal
from voussoirkit import sqlhelpers
from voussoirkit import stringtools
from voussoirkit import timetools
from voussoirkit import vlogging
from voussoirkit import worms

log = vlogging.getLogger(__name__)

from . import constants
from . import decorators
from . import exceptions
from . import helpers
from . import searchhelpers

BAIL = sentinel.Sentinel('BAIL')

class ObjectBase(worms.Object):
    def __init__(self, photodb):
        super().__init__(photodb)
        self.photodb = photodb
        # Used by decorators.required_feature.
        self._photodb = photodb
        # To be lazily retrieved by @property author.
        self._author = None
        # To be lazily retrieved by @property created.
        self._created_dt = None

    @staticmethod
    def normalize_author_id(author_id) -> typing.Optional[int]:
        '''
        Raises TypeError if author_id is not the right type.

        Raises ValueError if author_id contains invalid characters.
        '''
        if author_id is None:
            return None

        if not isinstance(author_id, int):
            raise TypeError(f'Author ID must be {int}, not {type(author_id)}.')

        if author_id < 1:
            raise ValueError(f'Author ID should be positive, not {author_id}.')

        return author_id

    # Will add -> User when forward references are supported by Python.
    @property
    def author(self):
        '''
        Return the User who created this object, or None if it is unassigned.
        '''
        if self._author_id is None:
            return None
        if self._author is not None:
            return self._author
        user = self.photodb.get_user(id=self._author_id)
        self._author = user
        return user

    @property
    def created(self) -> datetime.datetime:
        if self._created_dt is not None:
            return self._created_dt
        self._created_dt = helpers.utcfromtimestamp(self.created_unix)
        return self._created_dt

class GroupableMixin(metaclass=abc.ABCMeta):
    group_getter_many = None
    group_table = None

    def _lift_children(self):
        '''
        If this object has parents, the parents adopt all of its children.
        Otherwise, this object is at the root level, so the parental
        relationship is simply deleted and the children become root level.
        '''
        children = self.get_children()
        if not children:
            return

        self.photodb.delete(table=self.group_table, pairs={'parentid': self.id})

        parents = self.get_parents()
        for parent in parents:
            parent.add_children(children)

    def _add_child(self, member):
        self.assert_same_type(member)

        if member == self:
            raise exceptions.CantGroupSelf(self)

        if self.has_child(member):
            return BAIL

        log.info('Adding child %s to %s.', member, self)

        for my_ancestor in self.walk_parents():
            if my_ancestor == member:
                raise exceptions.RecursiveGrouping(member=member, group=self)

        data = {
            'parentid': self.id,
            'memberid': member.id,
            'created': timetools.now().timestamp(),
        }
        self.photodb.insert(table=self.group_table, pairs=data)

    @abc.abstractmethod
    def add_child(self, member):
        return self._add_child(member)

    @abc.abstractmethod
    def add_children(self, members):
        bail = True
        for member in members:
            bail = (self._add_child(member) is BAIL) and bail
        if bail:
            return BAIL

    def assert_same_type(self, other) -> None:
        '''
        Raise TypeError if other is not the same type as self, or if other is
        associated with a different etiquette.PhotoDB object.
        '''
        if not isinstance(other, type(self)):
            raise TypeError(f'Object must be of type {type(self)}, not {type(other)}.')
        if self.photodb != other.photodb:
            raise TypeError(f'Objects must belong to the same PhotoDB.')

    @abc.abstractmethod
    def delete(self, *, delete_children=False) -> None:
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
            self._lift_children()

        # Note that this part comes after the deletion of children to prevent
        # issues of recursion.
        self.photodb.delete(table=self.group_table, pairs={'memberid': self.id})
        self._uncache()
        self.deleted = True

    def get_children(self) -> set:
        child_ids = self.photodb.select_column(
            f'SELECT memberid FROM {self.group_table} WHERE parentid == ?',
            [self.id]
        )
        children = set(self.group_getter_many(child_ids))
        return children

    def get_parents(self) -> set:
        query = f'SELECT parentid FROM {self.group_table} WHERE memberid == ?'
        parent_ids = self.photodb.select_column(query, [self.id])
        parents = set(self.group_getter_many(parent_ids))
        return parents

    def has_ancestor(self, ancestor) -> bool:
        return ancestor in self.walk_parents()

    def has_any_child(self) -> bool:
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def has_any_parent(self) -> bool:
        query = f'SELECT 1 FROM {self.group_table} WHERE memberid == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def has_child(self, member) -> bool:
        self.assert_same_type(member)
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? AND memberid == ?'
        exists = self.photodb.select_one_value(query, [self.id, member.id])
        return exists is not None

    def has_descendant(self, descendant) -> bool:
        return self in descendant.walk_parents()

    def has_parent(self, parent) -> bool:
        self.assert_same_type(parent)
        query = f'SELECT 1 FROM {self.group_table} WHERE parentid == ? AND memberid == ?'
        exists = self.photodb.select_one_value(query, [parent.id, self.id])
        return exists is not None

    def _remove_child(self, member):
        if not self.has_child(member):
            return BAIL

        log.info('Removing child %s from %s.', member, self)

        pairs = {
            'parentid': self.id,
            'memberid': member.id,
        }
        self.photodb.delete(table=self.group_table, pairs=pairs)

    @abc.abstractmethod
    def remove_child(self, member):
        return self._remove_child(member)

    @abc.abstractmethod
    def remove_children(self, members):
        bail = True
        for member in members:
            bail = (self._remove_child(member) is BAIL) and bail
        if bail:
            return BAIL

    def walk_children(self) -> typing.Iterable:
        '''
        Yield self and all descendants.
        '''
        yield self
        for child in self.get_children():
            yield from child.walk_children()

    def walk_parents(self) -> typing.Iterable:
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
    no_such_exception = exceptions.NoSuchAlbum

    def __init__(self, photodb, db_row):
        super().__init__(photodb)

        self.id = db_row['id']
        self.title = self.normalize_title(db_row['title'])
        self.description = self.normalize_description(db_row['description'])
        self.created_unix = db_row['created']
        # To be lazily retrieved by @property thumbnail_photo.
        self._thumbnail_photo = db_row['thumbnail_photo']
        self._author_id = self.normalize_author_id(db_row['author_id'])

        self.group_getter_many = self.photodb.get_albums_by_id

    def __repr__(self):
        return f'Album:{self.id}'

    def __str__(self):
        if self.title:
            return f'Album:{self.id}:{self.title}'
        else:
            return f'Album:{self.id}'

    @staticmethod
    def normalize_description(description) -> str:
        '''
        Raises TypeError if description is not a string or None.
        '''
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError(f'Description must be {str}, not {type(description)}.')

        description = description.strip()

        return description

    @staticmethod
    def normalize_title(title) -> str:
        '''
        Raises TypeError if title is not a string or None.
        '''
        if title is None:
            return ''

        if not isinstance(title, str):
            raise TypeError(f'Title must be {str}, not {type(title)}.')

        title = stringtools.collapse_whitespace(title)

        return title

    def _uncache(self):
        self.photodb.caches[Album].remove(self.id)

    def _add_associated_directory(self, path):
        path = pathclass.Path(path)

        if not path.is_dir:
            raise ValueError(f'{path} is not a directory.')

        if self.has_associated_directory(path):
            return

        log.info('Adding directory "%s" to %s.', path.absolute_path, self)
        data = {
            'albumid': self.id,
            'directory': path.absolute_path,
            'created': timetools.now().timestamp(),
        }
        self.photodb.insert(table='album_associated_directories', pairs=data)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_associated_directory(self, path) -> None:
        '''
        Add a directory from which this album will pull files during rescans.
        These relationships are not unique and multiple albums can associate
        with the same directory if desired.

        Raises ValueError if path is not a directory.
        '''
        self._add_associated_directory(path)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_associated_directories(self, paths) -> None:
        '''
        Add multiple associated directories.

        Raises ValueError if any path is not a directory.
        '''
        for path in paths:
            self._add_associated_directory(path)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_child(self, member):
        '''
        Raises exceptions.CantGroupSelf if member is self.

        Raises exceptions.RecursiveGrouping if member is an ancestor of self.
        '''
        return super().add_child(member)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_children(self, *args, **kwargs):
        return super().add_children(*args, **kwargs)

    def _add_photo(self, photo):
        log.info('Adding photo %s to %s.', photo, self)
        data = {
            'albumid': self.id,
            'photoid': photo.id,
            'created': timetools.now().timestamp(),
        }
        self.photodb.insert(table='album_photo_rel', pairs=data)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_photo(self, photo) -> None:
        if self.has_photo(photo):
            return

        self._add_photo(photo)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def add_photos(self, photos) -> None:
        existing_photos = set(self.get_photos())
        photos = set(photos)
        new_photos = photos.difference(existing_photos)

        if not new_photos:
            return

        for photo in new_photos:
            self._add_photo(photo)

    # Photo.add_tag already has @required_feature
    @worms.atomic
    def add_tag_to_all(self, tag, *, nested_children=True) -> None:
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

    def atomify(self, web_root='') -> bs4.BeautifulSoup:
        web_root = web_root.rstrip('/')
        soup = bs4.BeautifulSoup('', 'xml')
        entry = soup.new_tag('entry')
        soup.append(entry)

        id_element = soup.new_tag('id')
        id_element.string = str(self.id)
        entry.append(id_element)

        title = soup.new_tag('title')
        title.string = self.display_name
        entry.append(title)

        link = soup.new_tag('link')
        link['rel'] = 'alternate'
        link['type'] = 'text/html'
        link['href'] = f'{web_root}/album/{self.id}'
        entry.append(link)

        published = soup.new_tag('published')
        published.string = self.created.isoformat()
        entry.append(published)

        content = soup.new_tag('content')
        # content.string = bs4.CData(f'<img src="/thumbnail/{self.id}.jpg"/>')
        entry.append(content)

        typ = soup.new_tag('etiquette:type')
        typ.string = 'album'
        entry.append(typ)

        return soup

    @decorators.required_feature('album.edit')
    @worms.atomic
    def delete(self, *, delete_children=False) -> None:
        log.info('Deleting %s.', self)
        GroupableMixin.delete(self, delete_children=delete_children)
        self.photodb.delete(table='album_associated_directories', pairs={'albumid': self.id})
        self.photodb.delete(table='album_photo_rel', pairs={'albumid': self.id})
        self.photodb.delete(table=Album, pairs={'id': self.id})
        self._uncache()
        self.deleted = True

    @property
    def display_name(self) -> str:
        if self.title:
            return self.title
        else:
            return str(self.id)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def edit(self, title=None, description=None) -> None:
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
        self.photodb.update(table=Album, pairs=data, where_key='id')
        self.title = title
        self.description = description

    @property
    def full_name(self) -> str:
        if self.title:
            return f'{self.id} - {self.title}'
        else:
            return self.id

    def get_associated_directories(self) -> set[pathclass.Path]:
        directories = self.photodb.select_column(
            'SELECT directory FROM album_associated_directories WHERE albumid == ?',
            [self.id]
        )
        directories = set(pathclass.Path(d) for d in directories)
        return directories

    def get_photos(self) -> set:
        photo_ids = self.photodb.select_column(
            'SELECT photoid FROM album_photo_rel WHERE albumid == ?',
            [self.id]
        )
        photos = set(self.photodb.get_photos_by_id(photo_ids))
        return photos

    def has_any_associated_directory(self) -> bool:
        '''
        Return True if this album has at least 1 associated directory.
        '''
        exists = self.photodb.select_one_value(
            'SELECT 1 FROM album_associated_directories WHERE albumid == ?',
            [self.id]
        )
        return exists is not None

    def has_any_photo(self, recurse=False) -> bool:
        '''
        Return True if this album contains at least 1 photo.

        recurse:
            If True, photos in child albums satisfy.
            If False, only consider this album.
        '''
        exists = self.photodb.select_one_value(
            'SELECT 1 FROM album_photo_rel WHERE albumid == ? LIMIT 1',
            [self.id]
        )
        if exists is not None:
            return True
        if recurse:
            return self.has_any_subalbum_photo()
        return False

    def has_any_subalbum_photo(self) -> bool:
        '''
        Return True if any descendent album has any photo, ignoring whether
        this particular album itself has photos.
        '''
        return any(child.has_any_photo(recurse=True) for child in self.get_children())

    def has_associated_directory(self, path) -> bool:
        path = pathclass.Path(path)
        exists = self.photodb.select_one_value(
            'SELECT 1 FROM album_associated_directories WHERE albumid == ? AND directory == ?',
            [self.id, path.absolute_path]
        )
        return exists is not None

    def has_photo(self, photo) -> bool:
        exists = self.photodb.select_one_value(
            'SELECT 1 FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        return exists is not None

    def jsonify(
            self,
            include_photos=True,
            include_parents=True,
            include_children=True,
            count_children=False,
            count_photos=False,
        ) -> dict:
        j = {
            'type': 'album',
            'id': self.id,
            'description': self.description,
            'title': self.title,
            'created': self.created_unix,
            'display_name': self.display_name,
            'thumbnail_photo': self.thumbnail_photo.id if self._thumbnail_photo else None,
            'author': self.author.jsonify() if self._author_id else None,
        }
        if self.deleted:
            j['deleted'] = True

        if include_parents:
            j['parents'] = [parent.id for parent in self.get_parents()]

        if include_children:
            j['children'] = [child.id for child in self.get_children()]

        if include_photos:
            j['photos'] = [photo.id for photo in self.get_photos()]

        if count_children:
            j['children_count'] = self.sum_children(recurse=False)

        if count_photos:
            j['photos_count'] = self.sum_photos(recurse=False)

        return j

    @decorators.required_feature('album.edit')
    @worms.atomic
    def remove_child(self, *args, **kwargs):
        return super().remove_child(*args, **kwargs)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def remove_children(self, *args, **kwargs):
        return super().remove_children(*args, **kwargs)

    def _remove_photo(self, photo):
        log.info('Removing photo %s from %s.', photo, self)
        pairs = {'albumid': self.id, 'photoid': photo.id}
        self.photodb.delete(table='album_photo_rel', pairs=pairs)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def remove_photo(self, photo) -> None:
        self._remove_photo(photo)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def remove_photos(self, photos) -> None:
        existing_photos = set(self.get_photos())
        photos = set(photos)
        remove_photos = photos.intersection(existing_photos)

        if not remove_photos:
            return

        for photo in remove_photos:
            self._remove_photo(photo)

    @decorators.required_feature('album.edit')
    @worms.atomic
    def set_thumbnail_photo(self, photo) -> None:
        '''
        Raises TypeError if photo is not a Photo.

        Raises worms.DeletedObject if self.deleted.
        '''
        if photo is None:
            photo_id = None
        elif isinstance(photo, str):
            photo = self.photodb.get_photo(photo)
            photo_id = photo.id
        elif isinstance(photo, Photo):
            photo.__reinit__()
            photo.assert_not_deleted()
            photo_id = photo.id
        else:
            raise TypeError(f'Must be {Photo}, not {type(photo)}.')

        pairs = {
            'id': self.id,
            'thumbnail_photo': photo_id,
        }
        self.photodb.update(table=Album, pairs=pairs, where_key='id')
        self._thumbnail_photo = photo

    def sum_bytes(self, recurse=True) -> int:
        '''
        Return the total number of bytes of all photos in this album.
        '''
        query = stringtools.collapse_whitespace('''
        SELECT SUM(bytes) FROM photos
        WHERE photos.id IN (
            SELECT photoid FROM album_photo_rel WHERE
            albumid IN {albumids}
        )
        ''')
        if recurse:
            albumids = [child.id for child in self.walk_children()]
        else:
            albumids = [self.id]

        albumids = sqlhelpers.listify(albumids)
        query = query.format(albumids=albumids)
        total = self.photodb.select_one_value(query)
        return total

    def sum_children(self, recurse=True) -> int:
        '''
        Return the total number of child albums in this album.

        This method may be preferable to len(album.get_children()) because it
        performs the counting in the database instead of creating Album objects.
        '''
        if recurse:
            walker = self.walk_children()
            # First yield is itself.
            next(walker)
            return sum(1 for child in walker)

        query = stringtools.collapse_whitespace('''
        SELECT COUNT(*)
        FROM album_group_rel
        WHERE parentid == ?
        ''')
        bindings = [self.id]
        total = self.photodb.select_one_value(query, bindings)
        return total

    def sum_photos(self, recurse=True) -> int:
        '''
        Return the total number of photos in this album.

        This method may be preferable to len(album.get_photos()) because it
        performs the counting in the database instead of creating Photo objects.
        '''
        query = stringtools.collapse_whitespace('''
        SELECT COUNT(*)
        FROM album_photo_rel
        WHERE albumid IN {albumids}
        ''')
        if recurse:
            albumids = [child.id for child in self.walk_children()]
        else:
            albumids = [self.id]

        albumids = sqlhelpers.listify(albumids)
        query = query.format(albumids=albumids)
        total = self.photodb.select_one_value(query)
        return total

    # Will add -> Photo when forward references are supported by Python.
    @property
    def thumbnail_photo(self):
        # When the object is instantiated, the _thumbnail_photo that comes out
        # of the db_row is just the ID string. We lazily convert it to a real
        # Photo object here.
        if self._thumbnail_photo is None:
            return None
        if isinstance(self._thumbnail_photo, Photo):
            return self._thumbnail_photo
        try:
            photo = self.photodb.get_photo(self._thumbnail_photo)
        except exceptions.NoSuchPhoto:
            self._thumbnail_photo = None
            return None
        self._thumbnail_photo = photo
        return photo

    def walk_photos(self) -> typing.Iterable:
        yield from self.get_photos()
        children = self.walk_children()
        # The first yield is itself
        next(children)
        for child in children:
            yield from child.walk_photos()

class Bookmark(ObjectBase):
    table = 'bookmarks'
    no_such_exception = exceptions.NoSuchBookmark

    def __init__(self, photodb, db_row):
        super().__init__(photodb)

        self.id = db_row['id']
        self.title = self.normalize_title(db_row['title'])
        self.url = self.normalize_url(db_row['url'])
        self.created_unix = db_row['created']
        self._author_id = self.normalize_author_id(db_row['author_id'])

    def __repr__(self):
        return f'Bookmark:{self.id}'

    @staticmethod
    def normalize_title(title) -> str:
        '''
        Raises TypeError if title is not a string or None.
        '''
        if title is None:
            return ''

        if not isinstance(title, str):
            raise TypeError(f'Title must be {str}, not {type(title)}.')

        title = stringtools.collapse_whitespace(title)

        return title

    @staticmethod
    def normalize_url(url) -> str:
        '''
        Raises TypeError if url is not a string or None.

        Raises ValueError if url is invalid.
        '''
        if url is None:
            return ''

        if not isinstance(url, str):
            raise TypeError(f'URL must be {str}, not {type(url)}.')

        url = url.strip()

        if not url:
            raise ValueError(f'URL can not be blank.')

        return url

    def _uncache(self):
        self.photodb.caches[Bookmark].remove(self.id)

    def atomify(self, web_root='') -> bs4.BeautifulSoup:
        web_root = web_root.rstrip('/')
        soup = bs4.BeautifulSoup('', 'xml')
        entry = soup.new_tag('entry')
        soup.append(entry)

        id_element = soup.new_tag('id')
        id_element.string = str(self.id)
        entry.append(id_element)

        title = soup.new_tag('title')
        title.string = self.title
        entry.append(title)

        link = soup.new_tag('link')
        link['href'] = self.url
        entry.append(link)

        published = soup.new_tag('published')
        published.string = self.created.isoformat()
        entry.append(published)

        typ = soup.new_tag('etiquette:type')
        typ.string = 'bookmark'
        entry.append(typ)

        return soup

    @decorators.required_feature('bookmark.edit')
    @worms.atomic
    def delete(self) -> None:
        self.photodb.delete(table=Bookmark, pairs={'id': self.id})
        self._uncache()
        self.deleted = True

    @property
    def display_name(self) -> str:
        if self.title:
            return self.title
        else:
            return self.id

    @decorators.required_feature('bookmark.edit')
    @worms.atomic
    def edit(self, title=None, url=None) -> None:
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
        self.photodb.update(table=Bookmark, pairs=data, where_key='id')
        self.title = title
        self.url = url

    def jsonify(self) -> dict:
        j = {
            'type': 'bookmark',
            'id': self.id,
            'author': self.author.jsonify() if self._author_id else None,
            'url': self.url,
            'created': self.created_unix,
            'title': self.title,
            'display_name': self.display_name,
        }
        if self.deleted:
            j['deleted'] = True

        return j

class Photo(ObjectBase):
    '''
    A PhotoDB entry containing information about an image file.
    Photo objects cannot exist without a corresponding PhotoDB object, because
    Photos are not the actual image data, just the database entry.
    '''
    table = 'photos'
    no_such_exception = exceptions.NoSuchPhoto

    def __init__(self, photodb, db_row):
        super().__init__(photodb)

        self.real_path = db_row['filepath']
        self.real_path = pathclass.Path(self.real_path)
        self.basename = db_row['basename']

        self.id = db_row['id']
        self.created_unix = db_row['created']
        self._author_id = self.normalize_author_id(db_row['author_id'])
        self.extension = self.real_path.extension.no_dot
        self.mtime = db_row['mtime']
        self.sha256 = db_row['sha256']

        if self.extension == '':
            self.dot_extension = ''
        else:
            self.dot_extension = '.' + self.extension

        self.bytes = db_row['bytes']
        self.duration = db_row['duration']
        self.width = db_row['width']
        self.height = db_row['height']
        self.area = db_row['area']
        self.aspectratio = db_row['aspectratio']
        self.bitrate = db_row['bitrate']

        # self.thumbnail = db_row['thumbnail_image']
        self._has_thumbnail = None
        self.tagged_at_unix = db_row['tagged_at']
        self._tagged_at_dt = None
        self.searchhidden = db_row['searchhidden']

        self._assign_mimetype()

    def __repr__(self):
        return f'Photo:{self.id}'

    def __str__(self):
        return f'Photo:{self.id}:{self.basename}'

    @staticmethod
    def normalize_override_filename(override_filename) -> typing.Optional[str]:
        '''
        Raises TypeError if override_filename is not a string or None.

        Raises ValueError if override_filename does not contain any valid
        characters remaining after invalid path chars are removed.
        '''
        if override_filename is None:
            return None

        if not isinstance(override_filename, str):
            raise TypeError(f'URL must be {str}, not {type(override_filename)}.')

        cleaned = helpers.remove_path_badchars(override_filename)
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError(f'"{override_filename}" is not valid.')

        return cleaned

    def _assign_mimetype(self):
        # This method is defined separately because it is a derivative
        # property of the file's basename and needs to be recalculated after
        # file renames. However, I decided not to write it as a @property
        # because that would require either wasted computation or using private
        # self._mimetype vars to help memoize, which needs to be None-capable.
        # So although I normally like using @property, this is less lines of
        # code and less indirection really.
        mime = helpers.get_mimetype(self.real_path.extension.no_dot)

        if mime is None:
            self.simple_mimetype = None
            self.mimetype = None
        else:
            self.simple_mimetype = mime[0]
            self.mimetype = '/'.join(mime)

    def _uncache(self):
        self.photodb.caches[Photo].remove(self.id)

    # Will add -> PhotoTagRel when forward references are supported by Python.
    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def add_tag(self, tag, timestamp=None):
        tag = self.photodb.get_tag(name=tag)

        existing = self.has_tag(tag, check_children=False, match_timestamp=timestamp)
        if existing:
            return existing

        log.info('Applying %s to %s.', tag, self)

        data = {
            'id': self.photodb.generate_id(PhotoTagRel),
            'photoid': self.id,
            'tagid': tag.id,
            'created': timetools.now().timestamp(),
            'timestamp': PhotoTagRel.normalize_timestamp(timestamp)
        }
        self.photodb.insert(table=PhotoTagRel, pairs=data)
        photo_tag = PhotoTagRel(self.photodb, data)

        data = {
            'id': self.id,
            'tagged_at': timetools.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

        return photo_tag

    def atomify(self, web_root='') -> bs4.BeautifulSoup:
        web_root = web_root.rstrip('/')
        soup = bs4.BeautifulSoup('', 'xml')
        entry = soup.new_tag('entry')
        soup.append(entry)

        id_element = soup.new_tag('id')
        id_element.string = str(self.id)
        entry.append(id_element)

        title = soup.new_tag('title')
        title.string = self.basename
        entry.append(title)

        link = soup.new_tag('link')
        link['rel'] = 'alternate'
        link['type'] = 'text/html'
        link['href'] = f'{web_root}/photo/{self.id}'
        entry.append(link)

        published = soup.new_tag('published')
        published.string = self.created.isoformat()
        entry.append(published)

        content = soup.new_tag('content')
        content.string = bs4.CData(f'<img src="{web_root}/thumbnail/{self.id}.jpg"/>')
        entry.append(content)

        typ = soup.new_tag('etiquette:type')
        typ.string = 'photo'
        entry.append(typ)

        return soup

    @property
    def bytes_string(self) -> str:
        if self.bytes is not None:
            return bytestring.bytestring(self.bytes)
        return '??? b'

    # Photo.add_tag already has @required_feature add_remove_tag
    @worms.atomic
    def copy_tags(self, other_photo) -> None:
        '''
        Take all of the tags owned by other_photo and apply them to this photo.
        '''
        for tag in other_photo.get_tags():
            self.add_tag(tag)

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def delete(self, *, delete_file=False) -> None:
        '''
        Delete the Photo and its relation to any tags and albums.
        '''
        log.info('Deleting %s.', self)
        self.photodb.delete(table='photo_tag_rel', pairs={'photoid': self.id})
        self.photodb.delete(table='album_photo_rel', pairs={'photoid': self.id})
        self.photodb.delete(table='photo_thumbnails', pairs={'photoid': self.id})
        self.photodb.delete(table=Photo, pairs={'id': self.id})

        if delete_file and self.real_path.exists:
            if self.photodb.config['recycle_instead_of_delete']:
                log.debug('Recycling %s.', self.real_path.absolute_path)
                action = send2trash.send2trash
            else:
                log.debug('Deleting %s.', self.real_path.absolute_path)
                action = os.remove

            self.photodb.on_commit_queue.append({
                'action': action,
                'args': [self.real_path],
            })

        self._uncache()
        self.deleted = True

    @property
    def duration_string(self) -> typing.Optional[str]:
        if self.duration is None:
            return None
        return hms.seconds_to_hms(self.duration, force_minutes=True)

    @decorators.required_feature('photo.generate_thumbnail')
    @worms.atomic
    def generate_thumbnail(self, trusted_file=False, **special):
        '''
        special:
            For images, you can provide `max_width` and/or `max_height` to
            override the config file.
            For videos, you can provide a `timestamp` to take the thumbnail at.
        '''
        image = None

        if self.simple_mimetype == 'image':
            log.info('Thumbnailing %s.', self.real_path.absolute_path)
            try:
                image = helpers.generate_image_thumbnail(
                    self.real_path.absolute_path,
                    max_width=special.get('max_width', self.photodb.config['thumbnail_width']),
                    max_height=special.get('max_height', self.photodb.config['thumbnail_height']),
                    trusted_file=trusted_file,
                )
            except (OSError, ValueError):
                log.warning(traceback.format_exc())
                return

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            log.info('Thumbnailing %s.', self.real_path.absolute_path)
            try:
                image = helpers.generate_video_thumbnail(
                    self.real_path.absolute_path,
                    width=self.photodb.config['thumbnail_width'],
                    height=self.photodb.config['thumbnail_height'],
                    **special
                )
            except Exception:
                log.warning(traceback.format_exc())
                return

        if image is None:
            return

        self.set_thumbnail(image)
        return image

    @decorators.cache_until_commit
    def get_containing_albums(self) -> set[Album]:
        '''
        Return the albums of which this photo is a member.
        '''
        album_ids = self.photodb.select_column(
            'SELECT albumid FROM album_photo_rel WHERE photoid == ?',
            [self.id]
        )
        albums = frozenset(self.photodb.get_albums_by_id(album_ids))
        return albums

    @decorators.cache_until_commit
    def get_tags(self) -> set:
        '''
        Return the tags assigned to this Photo.
        '''
        photo_tags = frozenset(self.photodb.get_objects_by_sql(
            PhotoTagRel,
            'SELECT * FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        ))
        return photo_tags

    @decorators.cache_until_commit
    def get_tag_names(self) -> set:
        return set(photo_tag.tag.name for photo_tag in self.get_tags())

    def get_thumbnail(self):
        query = 'SELECT thumbnail FROM photo_thumbnails WHERE photoid = ?'
        blob = self.photodb.select_one_value(query, [self.id])
        return blob

    # Will add -> Tag/False when forward references are supported.
    def has_tag(self, tag, *, check_children=True, match_timestamp=False):
        '''
        Return the PhotoTagRel object if this photo contains that tag.
        Otherwise return False.

        check_children:
            If True, children of the requested tag are accepted. That is,
            a photo with family.parents can be said to have the 'family' tag.
        '''
        tag = self.photodb.get_tag(name=tag)

        if check_children:
            tag_options = tag.walk_children()
        else:
            tag_options = [tag]

        tag_by_id = {t.id: t for t in tag_options}
        tag_option_ids = sqlhelpers.listify(tag_by_id)

        if match_timestamp is False or match_timestamp is None:
            query = f'SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid IN {tag_option_ids}'
            bindings = [self.id]
        else:
            query = f'SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid IN {tag_option_ids} AND timestamp == ?'
            bindings = [self.id, match_timestamp]

        results = list(self.photodb.get_objects_by_sql(PhotoTagRel, query, bindings))
        if not results:
            return False

        return results[0]

    def has_thumbnail(self) -> bool:
        if self._has_thumbnail is not None:
            return self._has_thumbnail
        self._has_thumbnail = self.photodb.exists('SELECT 1 FROM photo_thumbnails WHERE photoid = ?', [self.id])
        return self._has_thumbnail

    def jsonify(self, include_albums=True, include_tags=True) -> dict:
        j = {
            'type': 'photo',
            'id': self.id,
            'aspectratio': self.aspectratio,
            'author': self.author.jsonify() if self._author_id else None,
            'extension': self.extension,
            'width': self.width,
            'height': self.height,
            'area': self.area,
            'bytes': self.bytes,
            'duration_string': self.duration_string,
            'duration': self.duration,
            'bytes_string': self.bytes_string,
            'has_thumbnail': self.has_thumbnail(),
            'created': self.created_unix,
            'filename': self.basename,
            'mimetype': self.mimetype,
            'searchhidden': bool(self.searchhidden),
            'simple_mimetype': self.simple_mimetype,
        }
        if self.deleted:
            j['deleted'] = True

        if include_albums:
            j['albums'] = [album.id for album in self.get_containing_albums()]

        if include_tags:
            j['tags'] = [photo_tag.jsonify() for photo_tag in self.get_tags()]

        return j

    def make_thumbnail_filepath(self) -> pathclass.Path:
        '''
        Create the filepath that should be the location of our thumbnail.
        '''
        chunked_id = [''.join(chunk) for chunk in gentools.chunk_generator(str(self.id), 3)]
        folder = chunked_id[:-1]
        folder = os.sep.join(folder)
        folder = self.photodb.thumbnail_directory.join(folder)
        hopeful_filepath = folder.with_child(f'{self.id}.jpg')
        return hopeful_filepath

    # Photo.rename_file already has @required_feature
    @worms.atomic
    def move_file(self, directory) -> None:
        directory = pathclass.Path(directory)
        directory.assert_is_directory()
        new_path = directory.with_child(self.real_path.basename)
        new_path.assert_not_exists()
        self.rename_file(new_path.absolute_path, move=True)

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

    def _reload_image_metadata(self, trusted_file=False):
        _max_pixels = PIL.Image.MAX_IMAGE_PIXELS
        if trusted_file:
            PIL.Image.MAX_IMAGE_PIXELS = None
        try:
            image = PIL.Image.open(self.real_path.absolute_path)
        except (OSError, ValueError):
            traceback.print_exc()
            return
        finally:
            PIL.Image.MAX_IMAGE_PIXELS = _max_pixels

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

    @decorators.required_feature('photo.reload_metadata')
    @worms.atomic
    def reload_metadata(self, hash_kwargs=None, trusted_file=False) -> None:
        '''
        Load the file's height, width, etc as appropriate for this type of file.

        trusted_file:
            If True, we can disable certain safeguards for file parsing,
            depending on the file format.
        '''
        log.info('Reloading metadata for %s.', self)

        self.mtime = None
        self.sha256 = None
        self.bytes = None
        self.width = None
        self.height = None
        self.duration = None

        if self.real_path.is_file:
            stat = self.real_path.stat
            self.mtime = stat.st_mtime
            self.bytes = stat.st_size

        if self.bytes is None:
            pass

        elif self.simple_mimetype == 'image':
            self._reload_image_metadata(trusted_file=trusted_file)

        elif self.simple_mimetype == 'video':
            self._reload_video_metadata()

        elif self.simple_mimetype == 'audio':
            self._reload_audio_metadata()

        hash_kwargs = hash_kwargs or {}
        sha256 = spinal.hash_file(self.real_path, hash_class=hashlib.sha256, **hash_kwargs)
        self.sha256 = sha256.hexdigest()

        data = {
            'id': self.id,
            'mtime': self.mtime,
            'sha256': self.sha256,
            'width': self.width,
            'height': self.height,
            'duration': self.duration,
            'bytes': self.bytes,
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def relocate(self, new_filepath) -> None:
        '''
        Point the Photo object to a different filepath.

        This method DOES NOT MOVE THE FILE. It updates the database to reflect
        a move that was performed outside of the system.

        To rename or move the file, use `rename_file`.

        Raises FileNotFoundError if the supposed new_filepath is not actually
        a file.

        Raises exceptions.PhotoExists if new_filepath is already associated
        with another photo in the database.
        '''
        new_filepath = pathclass.Path(new_filepath)
        if not new_filepath.is_file:
            raise FileNotFoundError(new_filepath.absolute_path)

        self.photodb.assert_no_such_photo_by_path(filepath=new_filepath)

        log.info('Relocating %s to "%s".', self, new_filepath.absolute_path)
        data = {
            'id': self.id,
            'filepath': new_filepath.absolute_path,
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')
        self.real_path = new_filepath
        self._assign_mimetype()
        self._uncache()

    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def remove_tag(self, tag) -> None:
        '''
        This method removes all PhotoTagRel between this photo and tag.
        If you just want to remove one timestamped instance, get the PhotoTagRel
        object and call its delete method.
        '''
        tag = self.photodb.get_tag(name=tag)

        log.info('Removing %s from %s.', tag, self)
        pairs = {
            'photoid': self.id,
            'tagid': tag.id,
        }

        self.photodb.delete(table='photo_tag_rel', pairs=pairs)

        data = {
            'id': self.id,
            'tagged_at': timetools.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def remove_tags(self, tags) -> None:
        '''
        This method removes all PhotoTagRel between this photo and
        multiple tags.
        '''
        tags = [self.photodb.get_tag(name=tag) for tag in tags]

        log.info('Removing %s from %s.', tags, self)
        query = f'''
        DELETE FROM photo_tag_rel
        WHERE photoid == "{self.id}"
        AND tagid IN {sqlhelpers.listify(tag.id for tag in tags)}
        '''
        self.photodb.execute(query)

        data = {
            'id': self.id,
            'tagged_at': timetools.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def remove_thumbnail(self) -> None:
        self.photodb.delete(table='photo_thumbnails', pairs={'photoid': self.id})
        self._has_thumbnail = False

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def rename_file(self, new_filename, *, move=False) -> None:
        '''
        Rename the file on the disk as well as in the database.

        move:
            If True, allow the file to be moved into another directory.
            Otherwise, the rename must be local.

        Raises ValueError if new_filename includes a path to a directory that
        is not the file's current directory, and move is False.

        Raises ValueError if new_filename is the same as the current path.

        Raises pathclass.Exists if new_filename leads to a file that already
        exists.
        '''
        old_path = self.real_path
        old_path.correct_case()

        new_filename = helpers.remove_path_badchars(new_filename, allowed=':\\/')
        if os.path.dirname(new_filename) == '':
            new_path = old_path.parent.with_child(new_filename)
        else:
            new_path = pathclass.Path(new_filename)

        if (new_path.parent != old_path.parent) and not move:
            raise ValueError('Cannot move the file without param move=True.')

        if new_path.absolute_path == old_path.absolute_path:
            raise ValueError('The new and old names are the same.')

        new_path.assert_not_exists()

        log.info(
            'Renaming file "%s" -> "%s".',
            old_path.absolute_path,
            new_path.absolute_path,
        )

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
                os.link(old_path, new_path)
            except OSError:
                spinal.copy_file(old_path, new_path)

        data = {
            'id': self.id,
            'filepath': new_path.absolute_path,
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')
        self.real_path = new_path
        self._assign_mimetype()

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
    @worms.atomic
    def set_override_filename(self, new_filename) -> None:
        new_filename = self.normalize_override_filename(new_filename)

        data = {
            'id': self.id,
            'override_filename': new_filename,
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

        self.__reinit__()

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def set_searchhidden(self, searchhidden) -> None:
        data = {
            'id': self.id,
            'searchhidden': bool(searchhidden),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')
        self.searchhidden = searchhidden

    @decorators.required_feature('photo.edit')
    @worms.atomic
    def set_thumbnail(self, image):
        if not isinstance(image, PIL.Image.Image):
            raise TypeError(image)

        blob = imagetools.save_to_bytes(image, format='jpeg', quality=50)
        pairs = {
            'photoid': self.id,
            'thumbnail': blob,
            'created': timetools.now().timestamp(),
        }
        if self.photodb.exists('SELECT 1 FROM photo_thumbnails WHERE photoid = ?', [self.id]):
            self.photodb.update(table='photo_thumbnails', pairs=pairs, where_key='photoid')
        else:
            self.photodb.insert(table='photo_thumbnails', pairs=pairs)
        self._has_thumbnail = True
        return blob

    @property
    def tagged_at(self) -> datetime.datetime:
        if self._tagged_at_dt is not None:
            return self._tagged_at_dt
        self._tagged_at_dt = helpers.utcfromtimestamp(self.tagged_at_unix)
        return self._tagged_at_dt

class PhotoTagRel(ObjectBase):
    table = 'photo_tag_rel'

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        self.photodb = photodb
        self.id = db_row['id']
        self.photo_id = db_row['photoid']
        self.photo = photodb.get_photo(self.photo_id)
        self.tag_id = db_row['tagid']
        self.tag = photodb.get_tag_by_id(self.tag_id)
        self.created_unix = db_row['created']
        self.timestamp = db_row['timestamp']

    def __hash__(self):
        return hash(f'{self.photo_id}.{self.tag_id}')

    def __lt__(self, other):
        my_tuple = (self.photo_id, self.tag.name, (self.timestamp or 0))
        other_tuple = (other.photo_id, other.tag.name, (other.timestamp or 0))
        return my_tuple < other_tuple

    @staticmethod
    def normalize_timestamp(timestamp) -> float:
        if timestamp is None:
            return timestamp

        if timestamp == '':
            return None

        if isinstance(timestamp, str):
            return float(timestamp)

        if isinstance(timestamp, (int, float)):
            return timestamp

        else:
            raise TypeError(f'timestamp should be {float}, not {type(timestamp)}.')

    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def delete(self) -> None:
        log.info('Removing %s from %s.', self.tag.name, self.photo.id)
        self.photodb.delete(table=PhotoTagRel, pairs={'id': self.id})
        self.deleted = True

    def jsonify(self):
        j = {
            'type': 'photo_tag_rel',
            'id': self.id,
            'photo_id': self.photo_id,
            'tag_id': self.tag_id,
            'tag_name': self.tag.name,
            'created': self.created_unix,
            'timestamp': self.timestamp,
        }
        if self.deleted:
            j['deleted'] = True

        return j

class Search:
    '''
    FILE METADATA
    =============
    area, aspectratio, width, height, bytes, duration, bitrate:
        A dotdot_range string representing min and max. Or just a number
        for lower bound.

    extension:
        A string or list of strings of acceptable file extensions.

    extension_not:
        A string or list of strings of unacceptable file extensions.
        Including '*' will forbid all extensions, thus returning only
        extensionless files.

    filename:
        A string or list of strings in the form of an expression.
        Match is CASE-INSENSITIVE.
        Examples:
        '.pdf AND (programming OR "survival guide")'
        '.pdf programming python' (implicitly AND each term)

    sha256:
        A string or list of strings of exact SHA256 hashes to match.

    within_directory:
        A string or list of strings or pathclass Paths of directories.
        Photos MUST have a `filepath` that is a child of one of these
        directories.

    OBJECT METADATA
    ===============
    author:
        A list of User objects or usernames, or a string of comma-separated
        usernames.

    created:
        A dotdot_range string respresenting min and max. Or just a number
        for lower bound.

    has_albums:
        If True, require that the Photo belongs to >=1 album.
        If False, require that the Photo belongs to no albums.
        If None, either is okay.

    has_tags:
        If True, require that the Photo has >=1 tag.
        If False, require that the Photo has no tags.
        If None, any amount is okay.

    has_thumbnail:
        Require a thumbnail?
        If None, anything is okay.

    is_searchhidden:
        If True, find *only* searchhidden photos.
        If False, find *only* nonhidden photos.
        If None, either is okay.

    mimetype:
        A string or list of strings of acceptable mimetypes.
        'image', 'video', ...
        Note we are only interested in the simple "video", "audio" etc.
        For exact mimetypes you might as well use an extension search.

    TAGS
    ====
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
    =============
    limit:
        The maximum number of *successful* results to yield.

    offset:
        How many *successful* results to skip before we start yielding.

    orderby:
        A list of strings like ['aspectratio DESC', 'created ASC'] to sort
        and subsort the results.
        Descending is assumed if not provided.

    yield_albums:
        If True, albums which contain photos matching the search
        will be yielded.

    yield_photos:
        If True, photos matching the search will be yielded.
    '''
    def __init__(self, photodb, kwargs, *, raise_errors=True):
        self.photodb = photodb
        self.created = timetools.now()
        self.raise_errors = raise_errors
        if isinstance(kwargs, dict):
            kwargs = dotdict.DotDict(kwargs, default=None)
        self.kwargs = kwargs
        self.generator_started = False
        self.generator_exhausted = False
        self.more_after_limit = None
        self.query = None
        self.bindings = None
        self.explain = None
        self.start_time = None
        self.end_time = None
        self.start_commit_id = None
        self.warning_bag = WarningBag()
        self.results = self._generator()
        self.results_received = 0

    def atomify(self):
        raise NotImplementedError

    def jsonify(self):
        # The search has converted many arguments into sets or other types.
        # Convert them back into something that will display nicely on the search form.
        kwargs = self.kwargs._to_dict()
        join_helper = lambda x: ', '.join(x) if x else None
        kwargs['extension'] = join_helper(kwargs['extension'])
        kwargs['extension_not'] = join_helper(kwargs['extension_not'])
        kwargs['mimetype'] = join_helper(kwargs['mimetype'])
        kwargs['sha256'] = join_helper(kwargs['sha256'])

        author_helper = lambda users: ', '.join(user.username for user in users) if users else None
        kwargs['author'] = author_helper(kwargs['author'])

        tagname_helper = lambda tags: [tag.name for tag in tags] if tags else None
        kwargs['tag_musts'] = tagname_helper(kwargs['tag_musts'])
        kwargs['tag_mays'] = tagname_helper(kwargs['tag_mays'])
        kwargs['tag_forbids'] = tagname_helper(kwargs['tag_forbids'])

        results = [
            result.jsonify(include_albums=False)
            if isinstance(result, Photo) else
            result.jsonify(
                include_photos=False,
                include_parents=False,
                include_children=False,
            )
            for result in self.results
        ]

        j = {
            'type': 'search',
            'kwargs': kwargs,
            'results': results,
            'more_after_limit': self.more_after_limit,
        }
        return j

    def _generator(self):
        self.start_time = time.perf_counter()
        self.generator_started = True
        self.start_commit_id = self.photodb.last_commit_id

        kwargs = self.kwargs

        maximums = {}
        minimums = {}
        searchhelpers.minmax('area', kwargs.area, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('created', kwargs.created, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('width', kwargs.width, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('height', kwargs.height, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('aspectratio', kwargs.aspectratio, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('bytes', kwargs.bytes, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('duration', kwargs.duration, minimums, maximums, warning_bag=self.warning_bag)
        searchhelpers.minmax('bitrate', kwargs.bitrate, minimums, maximums, warning_bag=self.warning_bag)

        kwargs.author = searchhelpers.normalize_author(kwargs.author, photodb=self.photodb, warning_bag=self.warning_bag)
        kwargs.extension = searchhelpers.normalize_extension(kwargs.extension)
        kwargs.extension_not = searchhelpers.normalize_extension(kwargs.extension_not)
        kwargs.filename = searchhelpers.normalize_filename(kwargs.filename)
        kwargs.has_albums = searchhelpers.normalize_has_tags(kwargs.has_albums)
        kwargs.has_tags = searchhelpers.normalize_has_tags(kwargs.has_tags)
        kwargs.has_thumbnail = searchhelpers.normalize_has_thumbnail(kwargs.has_thumbnail)
        kwargs.is_searchhidden = searchhelpers.normalize_is_searchhidden(kwargs.is_searchhidden)
        kwargs.sha256 = searchhelpers.normalize_sha256(kwargs.sha256)
        kwargs.mimetype = searchhelpers.normalize_extension(kwargs.mimetype)
        kwargs.sha256 = searchhelpers.normalize_extension(kwargs.sha256)
        kwargs.within_directory = searchhelpers.normalize_within_directory(kwargs.within_directory, warning_bag=self.warning_bag)
        kwargs.yield_albums = searchhelpers.normalize_yield_albums(kwargs.yield_albums)
        kwargs.yield_photos = searchhelpers.normalize_yield_photos(kwargs.yield_photos)

        if kwargs.has_tags is False:
            if (kwargs.tag_musts or kwargs.tag_mays or kwargs.tag_forbids or kwargs.tag_expression):
                self.warning_bag.add("has_tags=False so all tag requests are ignored.")
            kwargs.tag_musts = None
            kwargs.tag_mays = None
            kwargs.tag_forbids = None
            kwargs.tag_expression = None
        else:
            kwargs.tag_musts = searchhelpers.normalize_tagset(self.photodb, kwargs.tag_musts, warning_bag=self.warning_bag)
            kwargs.tag_mays = searchhelpers.normalize_tagset(self.photodb, kwargs.tag_mays, warning_bag=self.warning_bag)
            kwargs.tag_forbids = searchhelpers.normalize_tagset(self.photodb, kwargs.tag_forbids, warning_bag=self.warning_bag)
            kwargs.tag_expression = searchhelpers.normalize_tag_expression(kwargs.tag_expression)

        if kwargs.extension is not None and kwargs.extension_not is not None:
            kwargs.extension = kwargs.extension.difference(kwargs.extension_not)

        tags_fixed = searchhelpers.normalize_mmf_vs_expression_conflict(
            kwargs.tag_musts,
            kwargs.tag_mays,
            kwargs.tag_forbids,
            kwargs.tag_expression,
            self.warning_bag,
        )
        (kwargs.tag_musts, kwargs.tag_mays, kwargs.tag_forbids, kwargs.tag_expression) = tags_fixed

        if kwargs.tag_expression:
            tag_expression_tree = searchhelpers.tag_expression_tree_builder(
                tag_expression=kwargs.tag_expression,
                photodb=self.photodb,
                warning_bag=self.warning_bag,
            )
            if tag_expression_tree is None:
                kwargs.tag_expression = None
                kwargs.tag_expression = None
            else:
                kwargs.tag_expression = str(tag_expression_tree)
                frozen_children = self.photodb.get_cached_tag_export('flat_dict', tags=self.get_root_tags())
                tag_match_function = searchhelpers.tag_expression_matcher_builder(frozen_children)
        else:
            tag_expression_tree = None
            kwargs.tag_expression = None

        if kwargs.has_tags is True and (kwargs.tag_musts or kwargs.tag_mays):
            # has_tags check is redundant then, so disable it.
            kwargs.has_tags = None

        kwargs.limit = searchhelpers.normalize_limit(kwargs.limit, warning_bag=self.warning_bag)
        kwargs.offset = searchhelpers.normalize_offset(kwargs.offset, warning_bag=self.warning_bag)
        kwargs.orderby = searchhelpers.normalize_orderby(kwargs.orderby, warning_bag=self.warning_bag)

        if kwargs.filename:
            try:
                filename_tree = expressionmatch.ExpressionTree.parse(kwargs.filename)
                filename_tree.map(lambda x: x.lower())
            except expressionmatch.NoTokens:
                filename_tree = None
        else:
            filename_tree = None

        if kwargs.orderby:
            orderby = [(expanded, direction) for (friendly, expanded, direction) in kwargs.orderby]
            kwargs.orderby = [
                f'{friendly}-{direction}'
                for (friendly, expanded, direction) in kwargs.orderby
            ]
        else:
            orderby = [('created', 'desc')]
            kwargs.orderby = None

        if not kwargs.yield_albums and not kwargs.yield_photos:
            exc = exceptions.NoYields(['yield_albums', 'yield_photos'])
            self.warning_bag.add(exc)
            if self.raise_errors:
                raise exceptions.NoYields(['yield_albums', 'yield_photos'])
            else:
                return

        photo_tag_rel_exist_clauses = searchhelpers.photo_tag_rel_exist_clauses(
            kwargs.tag_musts,
            kwargs.tag_mays,
            kwargs.tag_forbids,
        )

        notnulls = set()
        yesnulls = set()
        wheres = []
        bindings = []

        if photo_tag_rel_exist_clauses:
            wheres.extend(photo_tag_rel_exist_clauses)

        if kwargs.author:
            author_ids = [user.id for user in kwargs.author]
            wheres.append(f'author_id IN {sqlhelpers.listify(author_ids)}')

        if kwargs.extension:
            if '*' in kwargs.extension:
                wheres.append('extension != ""')
            else:
                qmarks = ', '.join('?' * len(kwargs.extension))
                wheres.append(f'extension IN ({qmarks})')
                bindings.extend(kwargs.extension)

        if kwargs.extension_not:
            if '*' in kwargs.extension_not:
                wheres.append('extension == ""')
            else:
                qmarks = ', '.join('?' * len(kwargs.extension_not))
                wheres.append(f'extension NOT IN ({qmarks})')
                bindings.extend(kwargs.extension_not)

        if kwargs.mimetype:
            extensions = {
                extension
                for (extension, (typ, subtyp)) in constants.MIMETYPES.items()
                if typ in kwargs.mimetype
            }
            wheres.append(f'extension IN {sqlhelpers.listify(extensions)} COLLATE NOCASE')

        if kwargs.within_directory:
            patterns = {d.absolute_path.rstrip(os.sep) for d in kwargs.within_directory}
            patterns = {f'{d}{os.sep}%' for d in patterns}
            clauses = ['filepath LIKE ?'] * len(patterns)
            if len(clauses) > 1:
                clauses = ' OR '.join(clauses)
                clauses = f'({clauses})'
            else:
                clauses = clauses.pop()
            wheres.append(clauses)
            bindings.extend(patterns)

        if kwargs.has_albums is True or (kwargs.yield_albums and not kwargs.yield_photos):
            wheres.append('EXISTS (SELECT 1 FROM album_photo_rel WHERE photoid == photos.id)')
        elif kwargs.has_albums is False:
            wheres.append('NOT EXISTS (SELECT 1 FROM album_photo_rel WHERE photoid == photos.id)')

        if kwargs.has_tags is True:
            wheres.append('EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')
        elif kwargs.has_tags is False:
            wheres.append('NOT EXISTS (SELECT 1 FROM photo_tag_rel WHERE photoid == photos.id)')

        if kwargs.has_thumbnail is True:
            notnulls.add('thumbnail')
        elif kwargs.has_thumbnail is False:
            yesnulls.add('thumbnail')

        for (column, direction) in orderby:
            if column != 'RANDOM()':
                notnulls.add(column)

        if kwargs.is_searchhidden is True:
            wheres.append('searchhidden == 1')
        elif kwargs.is_searchhidden is False:
            wheres.append('searchhidden == 0')

        if kwargs.sha256:
            wheres.append(f'sha256 IN {sqlhelpers.listify(kwargs.sha256)}')

        for column in notnulls:
            wheres.append(column + ' IS NOT NULL')
        for column in yesnulls:
            wheres.append(column + ' IS NULL')

        for (column, value) in minimums.items():
            wheres.append(column + ' >= ' + str(value))

        for (column, value) in maximums.items():
            wheres.append(column + ' <= ' + str(value))

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

        self.query = query
        self.bindings = bindings
        self.explain = self.photodb.explain(query, bindings)

        log.loud(self.explain)
        generator = self.photodb.select(self.query, self.bindings)
        seen_albums = set()
        offset = kwargs.offset
        for row in generator:
            photo = self.photodb.get_cached_instance(Photo, row)

            if filename_tree and not filename_tree.evaluate(photo.basename.lower()):
                continue

            if tag_expression_tree:
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

            if kwargs.yield_albums:
                new_albums = photo.get_containing_albums().difference(seen_albums)
                yield from new_albums
                self.results_received += len(new_albums)
                seen_albums.update(new_albums)

            if kwargs.yield_photos:
                yield photo
                self.results_received += 1

            if kwargs.limit is not None and self.results_received >= kwargs.limit:
                break

        try:
            next(generator)
        except StopIteration:
            self.more_after_limit = False
        else:
            self.more_after_limit = True

        self.generator_exhausted = True
        self.end_time = time.perf_counter()
        log.debug('Search took %s.', self.end_time - self.start_time)

class Tag(ObjectBase, GroupableMixin):
    '''
    A Tag, which can be applied to Photos for organization.
    '''
    table = 'tags'
    group_table = 'tag_group_rel'
    no_such_exception = exceptions.NoSuchTag

    def __init__(self, photodb, db_row):
        super().__init__(photodb)

        self.id = db_row['id']
        # Do not pass the name through the normalizer. It may be grandfathered
        # from previous character / length rules.
        self.name = db_row['name']
        self.description = self.normalize_description(db_row['description'])
        self.created_unix = db_row['created']
        self._author_id = self.normalize_author_id(db_row['author_id'])

        self.group_getter_many = self.photodb.get_tags_by_id

        self._cached_synonyms = None

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return f'Tag:{self.id}:{self.name}'

    def __str__(self):
        return f'Tag:{self.name}'

    @staticmethod
    def normalize_description(description) -> str:
        '''
        Raises TypeError if description is not a string or None.
        '''
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError(f'Description must be {str}, not {type(description)}.')

        description = description.strip()

        return description

    @staticmethod
    def normalize_name(name, min_length=None, max_length=None) -> str:
        '''
        Raises exceptions.TagTooShort if shorter than min_length.

        Raises exceptions.TagTooLong if longer than max_length after invalid
        characters are removed.
        '''
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
        self.photodb.caches[Tag].remove(self.id)

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def add_child(self, member):
        '''
        Raises exceptions.CantGroupSelf if member is self.

        Raises exceptions.RecursiveGrouping if member is an ancestor of self.
        '''
        ret = super().add_child(member)
        if ret is BAIL:
            return BAIL

        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def add_children(self, members):
        ret = super().add_children(members)
        if ret is BAIL:
            return BAIL

        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def add_synonym(self, synname) -> str:
        '''
        Raises any exceptions from photodb.normalize_tagname.

        Raises exceptions.CantSynonymSelf if synname is the tag's name.

        Raises exceptions.TagExists if synname resolves to an existing tag.
        '''
        synname = self.photodb.normalize_tagname(synname)

        if synname == self.name:
            raise exceptions.CantSynonymSelf(self)

        self.photodb.assert_no_such_tag(name=synname)

        log.info('New synonym %s of %s.', synname, self.name)

        self.photodb.caches['tag_exports'].clear()

        data = {
            'name': synname,
            'mastername': self.name,
            'created': timetools.now().timestamp(),
        }
        self.photodb.insert(table='tag_synonyms', pairs=data)

        if self._cached_synonyms is not None:
            self._cached_synonyms.add(synname)

        return synname

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def convert_to_synonym(self, mastertag) -> None:
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
        self.photodb.update(table='tag_synonyms', pairs=data, where_key='mastername')

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
        replace_photoids = list(self.photodb.select_column(query, bindings))

        # For those photos that only had the syn, simply replace with master.
        if replace_photoids:
            query = f'''
            UPDATE photo_tag_rel
            SET tagid = ?
            WHERE tagid == ?
            AND photoid IN {sqlhelpers.listify(replace_photoids)}
            '''
            bindings = [mastertag.id, self.id]
            self.photodb.execute(query, bindings)

        # For photos that have the old tag and DO already have the new one,
        # don't worry because the old rels will be deleted when the tag is
        # deleted.
        self.delete()

        # Enjoy your new life as a monk.
        mastertag.add_synonym(self.name)

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def delete(self, *, delete_children=False) -> None:
        log.info('Deleting %s.', self)
        super().delete(delete_children=delete_children)
        self.photodb.delete(table='photo_tag_rel', pairs={'tagid': self.id})
        self.photodb.delete(table='tag_synonyms', pairs={'mastername': self.name})
        self.photodb.delete(table=Tag, pairs={'id': self.id})
        self.photodb.caches['tag_exports'].clear()
        self._uncache()
        self.deleted = True

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def edit(self, description=None) -> None:
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
        self.photodb.update(table=Tag, pairs=data, where_key='id')
        self.description = description

        self._uncache()

    def get_synonyms(self) -> set[str]:
        if self._cached_synonyms is not None:
            return self._cached_synonyms

        synonyms = self.photodb.select_column(
            'SELECT name FROM tag_synonyms WHERE mastername == ?',
            [self.name]
        )
        synonyms = set(synonyms)
        self._cached_synonyms = synonyms
        return synonyms

    def jsonify(self, include_synonyms=False, include_parents=True, include_children=True) -> dict:
        j = {
            'type': 'tag',
            'id': self.id,
            'name': self.name,
            'created': self.created_unix,
            'author': self.author.jsonify() if self._author_id else None,
            'description': self.description,
        }
        if self.deleted:
            j['deleted'] = True

        if include_parents:
            j['parents'] = [parent.id for parent in self.get_parents()]

        if include_children:
            j['children'] = [child.id for child in self.get_children()]

        if include_synonyms:
            j['synonyms'] = list(self.get_synonyms())

        return j

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def remove_child(self, *args, **kwargs):
        ret = super().remove_child(*args, **kwargs)
        if ret is BAIL:
            return

        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def remove_children(self, *args, **kwargs):
        ret = super().remove_children(*args, **kwargs)
        if ret is BAIL:
            return

        self.photodb.caches['tag_exports'].clear()
        return ret

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def remove_synonym(self, synname) -> str:
        '''
        Delete a synonym.

        This will have no effect on photos or other synonyms because
        they always resolve to the master tag before application.

        Raises any exceptions from photodb.normalize_tagname.

        Raises exceptions.NoSuchSynonym if that synname does not exist or is
        not a synonym of this tag.
        '''
        synname = self.photodb.normalize_tagname(synname)
        if synname == self.name:
            raise exceptions.NoSuchSynonym(synname)

        syn_exists = self.photodb.select_one_value(
            'SELECT 1 FROM tag_synonyms WHERE mastername == ? AND name == ?',
            [self.name, synname]
        )

        if syn_exists is None:
            raise exceptions.NoSuchSynonym(synname)

        self.photodb.caches['tag_exports'].clear()
        self.photodb.delete(table='tag_synonyms', pairs={'name': synname})
        if self._cached_synonyms is not None:
            self._cached_synonyms.remove(synname)
        return synname

    @decorators.required_feature('tag.edit')
    @worms.atomic
    def rename(self, new_name, *, apply_to_synonyms=True) -> None:
        '''
        Rename the tag. Does not affect its relation to Photos or tag groups.

        Raises any exceptions from photodb.normalize_tagname.

        Raises exceptions.TagExists if new_name is already an existing
        tag or synonym.
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
        self.photodb.update(table=Tag, pairs=data, where_key='id')

        if apply_to_synonyms:
            data = {
                'mastername': (old_name, new_name),
            }
            self.photodb.update(table='tag_synonyms', pairs=data, where_key='mastername')

        self.name = new_name
        self._uncache()

class User(ObjectBase):
    '''
    A dear friend of ours.
    '''
    table = 'users'
    no_such_exception = exceptions.NoSuchUser

    def __init__(self, photodb, db_row):
        super().__init__(photodb)

        self.id = db_row['id']
        self.username = db_row['username']
        self.created_unix = db_row['created']
        self.password_hash = db_row['password']
        # Do not enforce maxlen here, they may be grandfathered in.
        self._display_name = self.normalize_display_name(db_row['display_name'])

    def __repr__(self):
        return f'User:{self.id}:{self.username}'

    def __str__(self):
        return f'User:{self.username}'

    @staticmethod
    def normalize_display_name(display_name, max_length=None) -> typing.Optional[str]:
        '''
        Raises TypeError if display_name is not a string or None.

        Raises exceptions.DisplayNameTooLong if longer than max_length.
        '''
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

    def _uncache(self):
        self.photodb.caches[User].remove(self.id)

    @decorators.required_feature('user.login')
    def check_password(self, password):
        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        success = bcrypt.checkpw(password, self.password_hash)
        if not success:
            raise exceptions.WrongLogin()
        return success

    @decorators.required_feature('user.edit')
    @worms.atomic
    def delete(self, *, disown_authored_things) -> None:
        '''
        If disown_authored_things is True then all of this user's albums,
        bookmarks, photos, and tags will have their author_id set to None.

        If disown_authored_things is False and the user has any belongings,
        raises exceptions.CantDeleteUser.

        You should delete those objects first. Since each object type has
        different options while deleting, that functionality is not provided
        here.
        '''
        if disown_authored_things:
            pairs = {'author_id': (self.id, None)}
            self.photodb.update(table=Album, pairs=pairs, where_key='author_id')
            self.photodb.update(table=Bookmark, pairs=pairs, where_key='author_id')
            self.photodb.update(table=Photo, pairs=pairs, where_key='author_id')
            self.photodb.update(table=Tag, pairs=pairs, where_key='author_id')
        else:
            fail = (
                self.has_any_albums() or
                self.has_any_bookmarks() or
                self.has_any_photos() or
                self.has_any_tags()
            )
            if fail:
                raise exceptions.CantDeleteUser(self)
        self.photodb.delete(table='users', pairs={'id': self.id})
        self._uncache()
        self.deleted = True

    @property
    def display_name(self) -> str:
        if self._display_name is None:
            return self.username
        else:
            return self._display_name

    def get_albums(self, *, direction='asc') -> typing.Iterable[Album]:
        '''
        Raises ValueError if direction is not asc or desc.
        '''
        if direction.lower() not in {'asc', 'desc'}:
            raise ValueError(direction)

        return self.photodb.get_albums_by_sql(
            f'SELECT * FROM albums WHERE author_id == ? ORDER BY created {direction}',
            [self.id]
        )

    def get_bookmarks(self, *, direction='asc') -> typing.Iterable[Bookmark]:
        '''
        Raises ValueError if direction is not asc or desc.
        '''
        if direction.lower() not in {'asc', 'desc'}:
            raise ValueError(direction)

        return self.photodb.get_bookmarks_by_sql(
            f'SELECT * FROM bookmarks WHERE author_id == ? ORDER BY created {direction}',
            [self.id]
        )

    def get_photos(self, *, direction='asc') -> typing.Iterable[Photo]:
        '''
        Raises ValueError if direction is not asc or desc.
        '''
        if direction.lower() not in {'asc', 'desc'}:
            raise ValueError(direction)

        return self.photodb.get_photos_by_sql(
            f'SELECT * FROM photos WHERE author_id == ? ORDER BY created {direction}',
            [self.id]
        )

    def get_tags(self, *, direction='asc') -> typing.Iterable[Tag]:
        '''
        Raises ValueError if direction is not asc or desc.
        '''
        if direction.lower() not in {'asc', 'desc'}:
            raise ValueError(direction)

        return self.photodb.get_tags_by_sql(
            f'SELECT * FROM tags WHERE author_id == ? ORDER BY created {direction}',
            [self.id]
        )

    def has_any_albums(self) -> bool:
        query = f'SELECT 1 FROM albums WHERE author_id == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def has_any_bookmarks(self) -> bool:
        query = f'SELECT 1 FROM bookmarks WHERE author_id == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def has_any_photos(self) -> bool:
        query = f'SELECT 1 FROM photos WHERE author_id == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def has_any_tags(self) -> bool:
        query = f'SELECT 1 FROM tags WHERE author_id == ? LIMIT 1'
        exists = self.photodb.select_one_value(query, [self.id])
        return exists is not None

    def jsonify(self) -> dict:
        j = {
            'type': 'user',
            'id': self.id,
            'username': self.username,
            'created': self.created_unix,
            'display_name': self.display_name,
        }
        if self.deleted:
            j['deleted'] = True

        return j

    @decorators.required_feature('user.edit')
    @worms.atomic
    def set_display_name(self, display_name) -> None:
        display_name = self.normalize_display_name(
            display_name,
            max_length=self.photodb.config['user']['max_display_name_length'],
        )

        data = {
            'id': self.id,
            'display_name': display_name,
        }
        self.photodb.update(table='users', pairs=data, where_key='id')
        self._display_name = display_name

    @decorators.required_feature('user.edit')
    @worms.atomic
    def set_password(self, password) -> None:
        if not isinstance(password, bytes):
            password = password.encode('utf-8')

        self.photodb.assert_valid_password(password)
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        data = {
            'id': self.id,
            'password': hashed_password,
        }
        self.photodb.update(table='users', pairs=data, where_key='id')
        self.hashed_password = hashed_password

class WarningBag:
    def __init__(self):
        self.warnings = set()

    def add(self, warning) -> None:
        self.warnings.add(warning)

    def jsonify(self):
        j = [getattr(w, 'error_message', str(w)) for w in self.warnings]
        return j
