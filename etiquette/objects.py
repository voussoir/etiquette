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
import traceback
import typing

from voussoirkit import bytestring
from voussoirkit import gentools
from voussoirkit import hms
from voussoirkit import pathclass
from voussoirkit import sentinel
from voussoirkit import spinal
from voussoirkit import sqlhelpers
from voussoirkit import stringtools
from voussoirkit import vlogging
from voussoirkit import worms

log = vlogging.getLogger(__name__)

from . import constants
from . import decorators
from . import exceptions
from . import helpers

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
        data = {'albumid': self.id, 'directory': path.absolute_path}
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
        data = {'albumid': self.id, 'photoid': photo.id}
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

    def atomify(self) -> bs4.BeautifulSoup:
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
        link['href'] = f'/album/{self.id}'
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

    def jsonify(self, include_photos=True, minimal=False) -> dict:
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
        if not minimal:
            j['parents'] = [parent.id for parent in self.get_parents()]
            j['children'] = [child.id for child in self.get_children()]

            if include_photos:
                j['photos'] = [photo.id for photo in self.get_photos()]

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
        SELECT COUNT(memberid)
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
        SELECT COUNT(photoid)
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
        photo = self.photodb.get_photo(self._thumbnail_photo)
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

        self.thumbnail = self.normalize_thumbnail(db_row['thumbnail'])
        self.tagged_at_unix = db_row['tagged_at']
        self._tagged_at_dt = None
        self.searchhidden = db_row['searchhidden']

        self._assign_mimetype()

    def __repr__(self):
        return f'Photo:{self.id}'

    def __str__(self):
        return f'Photo:{self.id}:{self.basename}'

    def normalize_thumbnail(self, thumbnail) -> pathclass.Path:
        if thumbnail is None:
            return None

        thumbnail = self.photodb.thumbnail_directory.join(thumbnail)
        if not thumbnail.is_file:
            return None

        return thumbnail

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
        # This function is defined separately because it is a derivative
        # property of the file's basename and needs to be recalculated after
        # file renames. However, I decided not to write it as a @property
        # because that would require either wasted computation or using private
        # self._mimetype vars to help memoize, which needs to be None-capable.
        # So although I normally like using @property, this is less lines of
        # code and less indirection really.
        self.mimetype = helpers.get_mimetype(self.real_path.basename)

        if self.mimetype is None:
            self.simple_mimetype = None
        else:
            self.simple_mimetype = self.mimetype.split('/')[0]

    def _uncache(self):
        self.photodb.caches[Photo].remove(self.id)

    # Will add -> Tag when forward references are supported by Python.
    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def add_tag(self, tag):
        tag = self.photodb.get_tag(name=tag)

        existing = self.has_tag(tag, check_children=False)
        if existing:
            return existing

        # If the new tag is less specific than one we already have,
        # keep our current one.
        existing = self.has_tag(tag, check_children=True)
        if existing:
            log.debug('Preferring existing %s over %s.', existing, tag)
            return existing

        # If the new tag is more specific, remove our current one for it.
        for parent in tag.walk_parents():
            if self.has_tag(parent, check_children=False):
                log.debug('Preferring new %s over %s.', tag, parent)
                self.remove_tag(parent)

        log.info('Applying %s to %s.', tag, self)

        data = {
            'photoid': self.id,
            'tagid': tag.id
        }
        self.photodb.insert(table='photo_tag_rel', pairs=data)
        data = {
            'id': self.id,
            'tagged_at': helpers.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

        return tag

    def atomify(self) -> bs4.BeautifulSoup:
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
        link['href'] = f'/photo/{self.id}'
        entry.append(link)

        published = soup.new_tag('published')
        published.string = self.created.isoformat()
        entry.append(published)

        content = soup.new_tag('content')
        content.string = bs4.CData(f'<img src="/thumbnail/{self.id}.jpg"/>')
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
            if self.thumbnail and self.thumbnail.is_file:
                self.photodb.on_commit_queue.append({
                    'action': action,
                    'args': [self.thumbnail],
                })

        self._uncache()
        self.deleted = True

    @property
    def duration_string(self) -> typing.Optional[str]:
        if self.duration is None:
            return None
        return hms.seconds_to_hms(self.duration)

    @decorators.required_feature('photo.generate_thumbnail')
    @worms.atomic
    def generate_thumbnail(self, trusted_file=False, **special) -> pathclass.Path:
        '''
        special:
            For images, you can provide `max_width` and/or `max_height` to
            override the config file.
            For videos, you can provide a `timestamp` to take the thumbnail at.
        '''
        hopeful_filepath = self.make_thumbnail_filepath()
        return_filepath = None

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
                traceback.print_exc()
            else:
                hopeful_filepath.parent.makedirs(exist_ok=True)
                image.save(hopeful_filepath.absolute_path, quality=50)
                return_filepath = hopeful_filepath

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            log.info('Thumbnailing %s.', self.real_path.absolute_path)
            try:
                hopeful_filepath.parent.makedirs(exist_ok=True)
                success = helpers.generate_video_thumbnail(
                    self.real_path.absolute_path,
                    outfile=hopeful_filepath.absolute_path,
                    width=self.photodb.config['thumbnail_width'],
                    height=self.photodb.config['thumbnail_height'],
                    **special
                )
                if success:
                    return_filepath = hopeful_filepath
            except Exception:
                log.warning(traceback.format_exc())

        if return_filepath != self.thumbnail:
            if return_filepath is None:
                store_as = None
            else:
                store_as = return_filepath.relative_to(self.photodb.thumbnail_directory)
            data = {
                'id': self.id,
                'thumbnail': store_as,
            }
            self.photodb.update(table=Photo, pairs=data, where_key='id')
            self.thumbnail = return_filepath

        self._uncache()

        self.__reinit__()
        return self.thumbnail

    def get_containing_albums(self) -> set[Album]:
        '''
        Return the albums of which this photo is a member.
        '''
        album_ids = self.photodb.select_column(
            'SELECT albumid FROM album_photo_rel WHERE photoid == ?',
            [self.id]
        )
        albums = set(self.photodb.get_albums_by_id(album_ids))
        return albums

    def get_tags(self) -> set:
        '''
        Return the tags assigned to this Photo.
        '''
        tag_ids = self.photodb.select_column(
            'SELECT tagid FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        )
        tags = set(self.photodb.get_tags_by_id(tag_ids))
        return tags

    # Will add -> Tag/False when forward references are supported.
    def has_tag(self, tag, *, check_children=True):
        '''
        Return the Tag object if this photo contains that tag.
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
        tag_id = self.photodb.select_one_value(
            f'SELECT tagid FROM photo_tag_rel WHERE photoid == ? AND tagid IN {tag_option_ids}',
            [self.id]
        )

        if tag_id is None:
            return False

        return tag_by_id[tag_id]

    def jsonify(self, include_albums=True, include_tags=True, minimal=False) -> dict:
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
            'has_thumbnail': bool(self.thumbnail),
            'created': self.created_unix,
            'filename': self.basename,
            'mimetype': self.mimetype,
            'searchhidden': bool(self.searchhidden),
            'simple_mimetype': self.simple_mimetype,
        }

        if not minimal:
            if include_albums:
                j['albums'] = [album.id for album in self.get_containing_albums()]

            if include_tags:
                j['tags'] = [tag.id for tag in self.get_tags()]

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

        # self._uncache()

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
        tag = self.photodb.get_tag(name=tag)

        log.info('Removing %s from %s.', tag, self)
        pairs = {
            'photoid': self.id,
            'tagid': tag.id,
        }
        self.photodb.delete(table='photo_tag_rel', pairs=pairs)

        data = {
            'id': self.id,
            'tagged_at': helpers.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

    @decorators.required_feature('photo.add_remove_tag')
    @worms.atomic
    def remove_tags(self, tags) -> None:
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
            'tagged_at': helpers.now().timestamp(),
        }
        self.photodb.update(table=Photo, pairs=data, where_key='id')

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

    @property
    def tagged_at(self) -> datetime.datetime:
        if self._tagged_at_dt is not None:
            return self._tagged_at_dt
        self._tagged_at_dt = helpers.utcfromtimestamp(self.tagged_at_unix)
        return self._tagged_at_dt

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

    def jsonify(self, include_synonyms=False, minimal=False) -> dict:
        j = {
            'type': 'tag',
            'id': self.id,
            'name': self.name,
            'created': self.created_unix,
        }
        if not minimal:
            j['author'] = self.author.jsonify() if self._author_id else None
            j['description'] = self.description
            j['parents'] = [parent.id for parent in self.get_parents()]
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
