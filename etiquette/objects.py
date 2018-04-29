'''
This file provides the data objects that should not be instantiated directly,
but are returned by the PDB accesses.
'''

import os
import PIL.Image
import string
import traceback

from . import constants
from . import decorators
from . import exceptions
from . import helpers

from voussoirkit import bytestring
from voussoirkit import pathclass
from voussoirkit import spinal


class ObjectBase:
    def __init__(self, photodb):
        super().__init__()
        self.photodb = photodb

    @property
    def log(self):
        return self.photodb.log

    @property
    def sql(self):
        return self.photodb.sql

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
            raise TypeError('author_id must be string, not %s' % type(author_id))

        author_id = author_id.strip()
        if author_id == '':
            return None

        return author_id

    def get_author(self):
        '''
        Return the User who created this object, or None if it is unassigned.
        '''
        if self.author_id is None:
            return None
        return self.photodb.get_user(id=self.author_id)


class GroupableMixin:
    group_getter = None
    group_getter_many = None
    group_sql_index = None
    group_table = None

    @decorators.transaction
    def add_child(self, member, *, commit=True):
        '''
        Add a child object to this group.
        Child must be of the same type as the calling object.

        If that object is already a member of another group, an
        exceptions.GroupExists is raised.
        '''
        if not isinstance(member, type(self)):
            raise TypeError('Member must be of type %s' % type(self))

        self.photodb.log.debug('Adding child %s to %s' % (member, self))

        # Groupables are only allowed to have 1 parent.
        # Unlike photos which can exist in multiple albums.
        parent_row = self.photodb.sql_select_one(
            'SELECT parentid FROM %s WHERE memberid == ?' % self.group_table,
            [member.id]
        )
        if parent_row is not None:
            parent_id = parent_row[0]
            if parent_id == self.id:
                return
            that_group = self.group_getter(id=parent_id)
            raise exceptions.GroupExists(member=member, group=that_group)

        for my_ancestor in self.walk_parents():
            if my_ancestor == member:
                raise exceptions.RecursiveGrouping(member=member, group=self)

        data = {
            'parentid': self.id,
            'memberid': member.id,
        }
        self.photodb.sql_insert(table=self.group_table, data=data)

        self.photodb._cached_frozen_children = None

        if commit:
            self.photodb.log.debug('Committing - add to group')
            self.photodb.commit()

    @decorators.transaction
    def delete(self, *, delete_children=False, commit=True):
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
        self.photodb._cached_frozen_children = None
        if delete_children:
            for child in self.get_children():
                child.delete(delete_children=delete_children, commit=False)
        else:
            # Lift children
            parent = self.get_parent()
            if parent is None:
                # Since this group was a root, children become roots by removing
                # the row.
                self.photodb.sql_delete(table=self.group_table, pairs={'parentid': self.id})
            else:
                # Since this group was a child, its parent adopts all its children.
                data = {
                    'parentid': (self.id, parent.id),
                }
                self.photodb.sql_update(table=self.group_table, pairs=data, where_key='parentid')

        # Note that this part comes after the deletion of children to prevent
        # issues of recursion.
        self.photodb.sql_delete(table=self.group_table, pairs={'memberid': self.id})
        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - delete tag')
            self.photodb.commit()

    def get_children(self):
        child_rows = self.photodb.sql_select(
            'SELECT memberid FROM %s WHERE parentid == ?' % self.group_table,
            [self.id]
        )
        child_ids = [row[0] for row in child_rows]
        children = self.group_getter_many(child_ids)

        if isinstance(self, Tag):
            children = sorted(children, key=lambda x: x.name)
        else:
            children = sorted(children, key=lambda x: x.id)
        return children

    def get_parent(self):
        '''
        Return the group of which this is a member, or None.
        Returned object will be of the same type as calling object.
        '''
        parent_row = self.photodb.sql_select_one(
            'SELECT parentid FROM %s WHERE memberid == ?' % self.group_table,
            [self.id]
        )
        if parent_row is None:
            return None

        return self.group_getter(id=parent_row[0])

    @decorators.transaction
    def join_group(self, group, *, commit=True):
        '''
        Leave the current group, then call `group.add_child(self)`.
        '''
        if not isinstance(group, type(self)):
            raise TypeError('Group must also be %s' % type(self))

        if self == group:
            raise ValueError('Cant join self')

        self.leave_group(commit=commit)
        group.add_child(self, commit=commit)

    @decorators.transaction
    def leave_group(self, *, commit=True):
        '''
        Leave the current group and become independent.
        '''
        self.photodb._cached_frozen_children = None
        self.photodb.sql_delete(table=self.group_table, pairs={'memberid': self.id})
        if commit:
            self.photodb.log.debug('Committing - leave group')
            self.photodb.commit()

    def walk_children(self):
        yield self
        for child in self.get_children():
            yield from child.walk_children()

    def walk_parents(self):
        parent = self.get_parent()
        while parent is not None:
            yield parent
            parent = parent.get_parent()


class Album(ObjectBase, GroupableMixin):
    group_table = 'album_group_rel'
    group_sql_index = constants.SQL_INDEX[group_table]

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        if isinstance(db_row, (list, tuple)):
            db_row = dict(zip(constants.SQL_COLUMNS['albums'], db_row))

        self.id = db_row['id']
        self.title = self.normalize_title(db_row['title'])
        self.description = self.normalize_description(db_row['description'])
        self.author_id = self.normalize_author_id(db_row['author_id'])

        self.name = 'Album %s' % self.id
        self.group_getter = self.photodb.get_album
        self.group_getter_many = self.photodb.get_albums_by_id

        self._sum_bytes_local = None
        self._sum_bytes_recursive = None
        self._sum_photos_recursive = None

    def __repr__(self):
        return f'Album:{self.id}'

    @staticmethod
    def normalize_description(description):
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError('Description must be string, not %s' % type(description))

        description = description.strip()

        return description

    @staticmethod
    def normalize_title(title):
        if title is None:
            return ''

        if not isinstance(title, str):
            raise TypeError('Title must be string, not %s' % type(title))

        title = title.strip()
        for whitespace in string.whitespace:
            title = title.replace(whitespace, ' ')

        return title

    def _uncache(self):
        self._uncache_sums()
        self.photodb.caches['album'].remove(self.id)

    def _uncache_sums(self):
        self._sum_photos_recursive = None
        self._sum_bytes_local = None
        self._sum_bytes_recursive = None
        parent = self.get_parent()
        if parent is not None:
            parent._uncache_sums()

    @decorators.required_feature('album.edit')
    # GroupableMixin.add_child already has @transaction.
    def add_child(self, *args, **kwargs):
        result = super().add_child(*args, **kwargs)
        self._uncache_sums()
        return result

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_associated_directory(self, filepath, *, commit=True):
        '''
        Add a directory from which this album will pull files during rescans.
        These relationships are not unique and multiple albums
        can associate with the same directory if desired.
        '''
        filepath = pathclass.Path(filepath)
        if not filepath.is_dir:
            raise ValueError('%s is not a directory' % filepath)

        try:
            existing = self.photodb.get_album_by_path(filepath)
        except exceptions.NoSuchAlbum:
            existing = None

        if existing is None:
            pass
        elif existing == self:
            return
        else:
            raise exceptions.AlbumExists(filepath)

        data = {
            'albumid': self.id,
            'directory': filepath.absolute_path,
        }
        self.photodb.sql_insert(table='album_associated_directories', data=data)

        if commit:
            self.photodb.log.debug('Committing - add associated directory')
            self.photodb.commit()

    def _add_photo(self, photo):
        self.photodb.log.debug('Adding photo %s to %s', photo, self)
        data = {
            'albumid': self.id,
            'photoid': photo.id,
        }
        self.photodb.sql_insert(table='album_photo_rel', data=data)
        self._uncache_sums()

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_photo(self, photo, *, commit=True):
        if self.photodb != photo.photodb:
            raise ValueError('Not the same PhotoDB')
        if self.has_photo(photo):
            return

        self._add_photo(photo)

        if commit:
            self.photodb.log.debug('Committing - add photo to album')
            self.photodb.commit()

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def add_photos(self, photos, *, commit=True):
        existing_photos = set(self.get_photos())
        photos = set(photos)
        photos = photos.difference(existing_photos)

        for photo in photos:
            self._add_photo(photo)

        if commit:
            self.photodb.log.debug('Committing - add photos to album')
            self.photodb.commit()

    # Photo.add_tag already has @required_feature
    @decorators.transaction
    def add_tag_to_all(self, tag, *, nested_children=True, commit=True):
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
            photo.add_tag(tag, commit=False)

        if commit:
            self.photodb.log.debug('Committing - add tag to all')
            self.photodb.commit()

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def delete(self, *, delete_children=False, commit=True):
        self.photodb.log.debug('Deleting %s', self)
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        self.photodb.sql_delete(table='albums', pairs={'id': self.id})
        self.photodb.sql_delete(table='album_photo_rel', pairs={'albumid': self.id})
        self.photodb.sql_delete(table='album_associated_directories', pairs={'albumid': self.id})
        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - delete album')
            self.photodb.commit()

    @property
    def display_name(self):
        if self.title:
            return self.title
        else:
            return self.id

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def edit(self, title=None, description=None, *, commit=True):
        '''
        Change the title or description. Leave None to keep current value.
        '''
        if title is None and description is None:
            return

        if title is not None:
            self.title = self.normalize_title(title)

        if description is not None:
            self.description = self.normalize_description(description)

        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
        }
        self.photodb.sql_update(table='albums', pairs=data, where_key='id')

        if commit:
            self.photodb.log.debug('Committing - edit album')
            self.photodb.commit()

    def get_associated_directories(self):
        directory_rows = self.photodb.sql_select(
            'SELECT directory FROM album_associated_directories WHERE albumid == ?',
            [self.id]
        )
        directories = [x[0] for x in directory_rows]
        directories = [pathclass.Path(x) for x in directories]
        return directories

    def get_photos(self):
        photos = []
        generator = self.photodb.sql_select(
            'SELECT photoid FROM album_photo_rel WHERE albumid == ?',
            [self.id]
        )
        photo_ids = [row[0] for row in generator]
        photos = self.photodb.get_photos_by_id(photo_ids)
        photos = sorted(photos, key=lambda x: x.basename.lower())
        return photos

    def has_any_photo(self, recurse=False):
        row = self.photodb.sql_select_one(
            'SELECT photoid FROM album_photo_rel WHERE albumid == ? LIMIT 1',
            [self.id]
        )
        if row is not None:
            return True
        if recurse:
            return self.has_any_subalbum_photo()
        return False

    def has_any_subalbum_photo(self):
        return any(child.has_any_photo(recurse=True) for child in self.get_children())

    def has_photo(self, photo):
        if not isinstance(photo, Photo):
            raise TypeError('`photo` must be of type %s' % Photo)

        rel_row = self.photodb.sql_select_one(
            'SELECT 1 FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        return rel_row is not None

    @decorators.required_feature('album.edit')
    # GroupableMixin.join_group already has @transaction.
    def join_group(self, *args, **kwargs):
        result = super().join_group(*args, **kwargs)
        return result

    @decorators.required_feature('album.edit')
    # GroupableMixin.leave_group already has @transaction.
    def leave_group(self, *args, **kwargs):
        parent = self.get_parent()
        if parent is not None:
            parent._uncache_sums()
        result = super().leave_group(*args, **kwargs)
        return result

    @decorators.required_feature('album.edit')
    @decorators.transaction
    def remove_photo(self, photo, *, commit=True):
        if not self.has_photo(photo):
            return

        self.photodb.log.debug('Removing photo %s from %s', photo, self)
        pairs = {'albumid': self.id, 'photoid': photo.id}
        self.photodb.sql_delete(table='album_photo_rel', pairs=pairs)
        self._uncache_sums()
        if commit:
            self.photodb.log.debug('Committing - remove photo from album')
            self.photodb.commit()

    def sum_bytes(self, recurse=True):
        query = '''
        SELECT SUM(bytes) FROM photos
        WHERE photos.id IN (
            SELECT photoid FROM album_photo_rel WHERE
            albumid IN {qmarks}
        )
        '''
        if recurse:
            albumids = [child.id for child in self.walk_children()]
        else:
            albumids = [self.id]

        query = query.format(qmarks='(%s)' % ','.join('?' * len(albumids)))
        bindings = albumids
        total = self.photodb.sql_select_one(query, bindings)[0]
        return total

    def sum_photos(self):
        if self._sum_photos_recursive is None:
            #print(self, 'sumphotos cache miss')
            total = 0
            total += sum(1 for x in self.get_photos())
            total += sum(child.sum_photos() for child in self.get_children())
            self._sum_photos_recursive = total

        return self._sum_photos_recursive

    def walk_photos(self):
        yield from self.get_photos()
        children = self.walk_children()
        # The first yield is itself
        next(children)
        for child in children:
            yield from child.walk_photos()


class Bookmark(ObjectBase):
    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        if isinstance(db_row, (list, tuple)):
            db_row = dict(zip(constants.SQL_COLUMNS['bookmarks'], db_row))

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
            raise TypeError('Title must be string, not %s' % type(title))

        title = title.strip()
        for whitespace in string.whitespace:
            title = title.replace(whitespace, ' ')

        return title

    @staticmethod
    def normalize_url(url):
        if url is None:
            return ''

        if not isinstance(url, str):
            raise TypeError('URL must be string, not %s' % type(url))

        url = url.strip()

        if not url:
            raise ValueError('Invalid URL "%s"' % url)

        return url

    @decorators.required_feature('bookmark.edit')
    @decorators.transaction
    def delete(self, *, commit=True):
        self.photodb.sql_delete(table='bookmarks', pairs={'id': self.id})
        if commit:
            self.photodb.commit()

    @decorators.required_feature('bookmark.edit')
    @decorators.transaction
    def edit(self, title=None, url=None, *, commit=True):
        '''
        Change the title or URL. Leave None to keep current.
        '''
        if title is None and url is None:
            return

        if title is not None:
            self.title = self.normalize_title(title)

        if url is not None:
            self.url = self.normalize_url(url)

        data = {
            'id': self.id,
            'title': self.title,
            'url': self.url,
        }
        self.photodb.sql_update(table='bookmarks', pairs=data, where_key='id')

        if commit:
            self.photodb.log.debug('Committing - edit bookmark')
            self.photodb.commit()


class Photo(ObjectBase):
    '''
    A PhotoDB entry containing information about an image file.
    Photo objects cannot exist without a corresponding PhotoDB object, because
    Photos are not the actual image data, just the database entry.
    '''
    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        if isinstance(db_row, (list, tuple)):
            db_row = dict(zip(constants.SQL_COLUMNS['photos'], db_row))

        self.real_path = db_row['filepath']
        self.real_path = helpers.remove_path_badchars(self.real_path, allowed=':\\/')
        self.real_path = pathclass.Path(self.real_path)

        self.id = db_row['id']
        self.created = db_row['created']
        self.author_id = self.normalize_author_id(db_row['author_id'])
        self.basename = db_row['override_filename'] or self.real_path.basename
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

        if self.duration and self.bytes is not None:
            self.bitrate = (self.bytes / 128) / self.duration
        else:
            self.bitrate = None

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

    def _uncache(self):
        self.photodb.caches['photo'].remove(self.id)

    @decorators.required_feature('photo.add_remove_tag')
    @decorators.transaction
    def add_tag(self, tag, *, commit=True):
        tag = self.photodb.get_tag(name=tag)

        existing = self.has_tag(tag, check_children=False)
        if existing:
            return existing

        # If the new tag is less specific than one we already have,
        # keep our current one.
        existing = self.has_tag(tag, check_children=True)
        if existing:
            message = f'Preferring existing {existing} over {tag}'
            self.photodb.log.debug(message)
            return existing

        # If the new tag is more specific, remove our current one for it.
        for parent in tag.walk_parents():
            if self.has_tag(parent, check_children=False):
                message = f'Preferring new {tag} over {parent}'
                self.photodb.log.debug(message)
                self.remove_tag(parent, commit=False)

        self.photodb.log.debug('Applying %s to %s', tag, self)

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

        if commit:
            self.photodb.log.debug('Committing - add photo tag')
            self.photodb.commit()
        return tag

    @property
    def bytestring(self):
        if self.bytes is not None:
            return bytestring.bytestring(self.bytes)
        return '??? b'

    @decorators.required_feature('photo.add_remove_tag')
    # Photo.add_tag already has @transaction.
    def copy_tags(self, other_photo, *, commit=True):
        '''
        Take all of the tags owned by other_photo and apply them to this photo.
        '''
        for tag in other_photo.get_tags():
            self.add_tag(tag, commit=False)
        if commit:
            self.photodb.log.debug('Committing - copy tags')
            self.photodb.commit()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def delete(self, *, delete_file=False, commit=True):
        '''
        Delete the Photo and its relation to any tags and albums.
        '''
        self.photodb.log.debug('Deleting %s', self)
        self.photodb.sql_delete(table='photos', pairs={'id': self.id})
        self.photodb.sql_delete(table='photo_tag_rel', pairs={'photoid': self.id})
        self.photodb.sql_delete(table='album_photo_rel', pairs={'photoid': self.id})

        if delete_file:
            path = self.real_path.absolute_path
            if commit:
                os.remove(path)
            else:
                queue_action = {'action': os.remove, 'args': [path]}
                self.photodb.on_commit_queue.append(queue_action)
        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - delete photo')
            self.photodb.commit()

    @property
    def duration_string(self):
        if self.duration is None:
            return None
        return helpers.seconds_to_hms(self.duration)

    #@decorators.time_me
    @decorators.required_feature('photo.generate_thumbnail')
    @decorators.transaction
    def generate_thumbnail(self, *, commit=True, **special):
        '''
        special:
            For videos, you can provide a `timestamp` to take the thumbnail at.
        '''
        hopeful_filepath = self.make_thumbnail_filepath()
        return_filepath = None

        if self.simple_mimetype == 'image':
            self.photodb.log.debug('Thumbnailing %s', self.real_path.absolute_path)
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
            #print('video')
            self.photodb.log.debug('Thumbnailing %s', self.real_path.absolute_path)
            probe = constants.ffmpeg.probe(self.real_path.absolute_path)
            try:
                if probe.video:
                    size = helpers.fit_into_bounds(
                        image_width=probe.video.video_width,
                        image_height=probe.video.video_height,
                        frame_width=self.photodb.config['thumbnail_width'],
                        frame_height=self.photodb.config['thumbnail_height'],
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
                    constants.ffmpeg.thumbnail(
                        self.real_path.absolute_path,
                        outfile=hopeful_filepath.absolute_path,
                        quality=2,
                        size=size,
                        time=timestamp,
                    )
            except Exception:
                traceback.print_exc()
            else:
                return_filepath = hopeful_filepath

        if return_filepath != self.thumbnail:
            data = {
                'id': self.id,
                'thumbnail': return_filepath.relative_to(self.photodb.thumbnail_directory),
            }
            self.photodb.sql_update(table='photos', pairs=data, where_key='id')
            self.thumbnail = return_filepath

        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - generate thumbnail')
            self.photodb.commit()

        self.__reinit__()
        return self.thumbnail

    def get_containing_albums(self):
        '''
        Return the albums of which this photo is a member.
        '''
        album_ids = self.photodb.sql_select(
            'SELECT albumid FROM album_photo_rel WHERE photoid == ?',
            [self.id]
        )
        album_ids = [row[0] for row in album_ids]
        albums = list(self.photodb.get_albums_by_id(album_ids))
        return albums

    def get_tags(self):
        '''
        Return the tags assigned to this Photo.
        '''
        tag_ids = self.photodb.sql_select(
            'SELECT tagid FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        )
        tag_ids = [row[0] for row in tag_ids]
        tags = list(self.photodb.get_tags_by_id(tag_ids))
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
        tag_option_ids = helpers.sql_listify(tag_by_id)
        rel_row = self.photodb.sql_select_one(
            'SELECT tagid FROM photo_tag_rel WHERE photoid == ? AND tagid IN %s' % tag_option_ids,
            [self.id]
        )

        if rel_row is None:
            return False

        return tag_by_id[rel_row[0]]

    def make_thumbnail_filepath(self):
        '''
        Create the filepath that should be the location of our thumbnail.
        '''
        chunked_id = helpers.chunk_sequence(self.id, 3)
        (folder, basename) = (chunked_id[:-1], chunked_id[-1])
        folder = os.sep.join(folder)
        folder = self.photodb.thumbnail_directory.join(folder)
        if folder:
            os.makedirs(folder.absolute_path, exist_ok=True)
        hopeful_filepath = folder.with_child(basename + '.jpg')
        return hopeful_filepath

    #@decorators.time_me
    @decorators.required_feature('photo.reload_metadata')
    @decorators.transaction
    def reload_metadata(self, *, commit=True):
        '''
        Load the file's height, width, etc as appropriate for this type of file.
        '''
        self.bytes = self.real_path.size
        self.width = None
        self.height = None
        self.area = None
        self.ratio = None
        self.duration = None

        self.photodb.log.debug('Reloading metadata for %s', self)

        if self.simple_mimetype == 'image':
            try:
                image = PIL.Image.open(self.real_path.absolute_path)
            except (OSError, ValueError):
                self.photodb.log.debug('Failed to read image data for %s', self)
            else:
                (self.width, self.height) = image.size
                image.close()

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            try:
                probe = constants.ffmpeg.probe(self.real_path.absolute_path)
                if probe and probe.video:
                    self.duration = probe.format.duration or probe.video.duration
                    self.width = probe.video.video_width
                    self.height = probe.video.video_height
            except Exception:
                traceback.print_exc()

        elif self.simple_mimetype == 'audio' and constants.ffmpeg:
            try:
                probe = constants.ffmpeg.probe(self.real_path.absolute_path)
                if probe and probe.audio:
                    self.duration = probe.audio.duration
            except Exception:
                traceback.print_exc()

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
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - reload metadata')
            self.photodb.commit()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def relocate(self, new_filepath, *, allow_duplicates=False, commit=True):
        '''
        Point the Photo object to a different filepath.

        DOES NOT MOVE THE FILE, only acknowledges a move that was performed
        outside of the system.
        To rename or move the file, use `rename_file`.

        allow_duplicates:
            Allow even if there is another Photo for that path.
        '''
        new_filepath = pathclass.Path(new_filepath)
        if not new_filepath.is_file:
            raise FileNotFoundError(new_filepath.absolute_path)

        if not allow_duplicates:
            try:
                existing = self.photodb.get_photo_by_path(new_filepath)
            except exceptions.NoSuchPhoto:
                # Good.
                pass
            else:
                raise exceptions.PhotoExists(existing)

        data = {
            'id': self.id,
            'filepath': new_filepath.absolute_path,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - relocate photo')
            self.photodb.commit()

    @decorators.required_feature('photo.add_remove_tag')
    @decorators.transaction
    def remove_tag(self, tag, *, commit=True):
        tag = self.photodb.get_tag(name=tag)

        self.photodb.log.debug('Removing %s from %s', tag, self)
        tags = list(tag.walk_children())

        for tag in tags:
            pairs = {'photoid': self.id, 'tagid': tag.id}
            self.photodb.sql_delete(table='photo_tag_rel', pairs=pairs)

        data = {
            'id': self.id,
            'tagged_at': helpers.now(),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        if commit:
            self.photodb.log.debug('Committing - remove photo tag')
            self.photodb.commit()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def rename_file(self, new_filename, *, move=False, commit=True):
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

        self.photodb.log.debug(old_path)
        self.photodb.log.debug(new_path)
        if (new_path.parent != old_path.parent) and not move:
            raise ValueError('Cannot move the file without param move=True')

        if new_path.absolute_path == old_path.absolute_path:
            raise ValueError('The new and old names are the same')

        os.makedirs(new_path.parent.absolute_path, exist_ok=True)

        if new_path.normcase != old_path.normcase:
            # It's possible on case-insensitive systems to have the paths point
            # to the same place while being differently cased, thus we couldn't
            # make the intermediate link.
            # Instead, we will do a simple rename in just a moment.
            try:
                os.link(old_path.absolute_path, new_path.absolute_path)
            except OSError:
                spinal.copy_file(old_path, new_path)

        data = {
            'filepath': (old_path.absolute_path, new_path.absolute_path),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='filepath')

        if new_path.normcase == old_path.normcase:
            # If they are equivalent but differently cased, just rename.
            action = os.rename
            args = [old_path.absolute_path, new_path.absolute_path]
        else:
            # Delete the original, leaving only the new copy / hardlink.
            action = os.remove
            args = [old_path.absolute_path]

        self._uncache()
        if commit:
            action(*args)
            self.photodb.log.debug('Committing - rename file')
            self.photodb.commit()
        else:
            queue_action = {'action': action, 'args': args}
            self.photodb.on_commit_queue.append(queue_action)

        self.__reinit__()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def set_searchhidden(self, searchhidden, *, commit=True):
        data = {
            'id': self.id,
            'searchhidden': bool(searchhidden),
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        self.searchhidden = searchhidden

        if commit:
            self.photodb.log.debug('Committing - set searchhidden')
            self.photodb.commit()

    @decorators.required_feature('photo.edit')
    @decorators.transaction
    def set_override_filename(self, new_filename, *, commit=True):
        if new_filename is not None:
            cleaned = helpers.remove_path_badchars(new_filename)
            cleaned = cleaned.strip()
            if not cleaned:
                raise ValueError('"%s" is not valid.' % new_filename)
            new_filename = cleaned

        data = {
            'id': self.id,
            'override_filename': new_filename,
        }
        self.photodb.sql_update(table='photos', pairs=data, where_key='id')

        if commit:
            self.photodb.log.debug('Committing - set override filename')
            self.photodb.commit()

        self.__reinit__()


class Tag(ObjectBase, GroupableMixin):
    '''
    A Tag, which can be applied to Photos for organization.
    '''
    group_table = 'tag_group_rel'
    group_sql_index = constants.SQL_INDEX[group_table]

    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        if isinstance(db_row, (list, tuple)):
            db_row = dict(zip(constants.SQL_COLUMNS['tags'], db_row))
        self.id = db_row['id']
        self.name = db_row['name']
        self.description = self.normalize_description(db_row['description'])
        self.author_id = self.normalize_author_id(db_row['author_id'])

        self.group_getter = self.photodb.get_tag
        self.group_getter_many = self.photodb.get_tags_by_id
        self._cached_qualified_name = None

    def __eq__(self, other):
        return self.name == other or ObjectBase.__eq__(self, other)

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        rep = f'Tag:{self.id}:{self.name}'
        return rep

    def __str__(self):
        rep = f'Tag:{self.name}'
        return rep

    @staticmethod
    def normalize_description(description):
        if description is None:
            return ''

        if not isinstance(description, str):
            raise TypeError('Description must be string, not %s' % type(description))

        description = description.strip()

        return description

    @staticmethod
    def normalize_name(name, valid_chars=None, min_length=None, max_length=None):
        original_name = name
        if valid_chars is None:
            valid_chars = constants.DEFAULT_CONFIG['tag']['valid_chars']

        name = name.lower()
        name = name.replace('-', '_')
        name = name.replace(' ', '_')
        name = (c for c in name if c in valid_chars)
        name = ''.join(name)

        if min_length is not None and len(name) < min_length:
            raise exceptions.TagTooShort(original_name)

        if max_length is not None and len(name) > max_length:
            raise exceptions.TagTooLong(name)

        return name

    def _uncache(self):
        self.photodb.caches['tag'].remove(self.id)
        self._cached_qualified_name = None

    @decorators.required_feature('tag.edit')
    # GroupableMixin.add_child already has @transaction.
    def add_child(self, *args, **kwargs):
        return super().add_child(*args, **kwargs)

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def add_synonym(self, synname, *, commit=True):
        synname = self.photodb.normalize_tagname(synname)

        if synname == self.name:
            raise exceptions.CantSynonymSelf()

        try:
            existing_tag = self.photodb.get_tag(name=synname)
        except exceptions.NoSuchTag:
            pass
        else:
            raise exceptions.TagExists(existing_tag)

        self.log.debug('New synonym %s of %s', synname, self.name)

        self.photodb._cached_frozen_children = None

        data = {
            'name': synname,
            'mastername': self.name,
        }
        self.photodb.sql_insert(table='tag_synonyms', data=data)

        if commit:
            self.photodb.log.debug('Committing - add synonym')
            self.photodb.commit()

        return synname

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def convert_to_synonym(self, mastertag, *, commit=True):
        '''
        Convert this tag into a synonym for a different tag.
        All photos which possess the current tag will have it replaced with the
        new master tag.
        All synonyms of the old tag will point to the new tag.

        Good for when two tags need to be merged under a single name.
        '''
        mastertag = self.photodb.get_tag(name=mastertag)

        self.photodb._cached_frozen_children = None

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
        replace_photoids = [row[0] for row in self.photodb.sql_execute(query, bindings)]

        # For those photos that only had the syn, simply replace with master.
        if replace_photoids:
            query = '''
            UPDATE photo_tag_rel
            SET tagid = ?
            WHERE tagid == ?
            AND photoid IN %s
            ''' % helpers.sql_listify(replace_photoids)
            bindings = [mastertag.id, self.id]
            self.photodb.sql_execute(query, bindings)

        # For photos that have the old tag and DO already have the new one,
        # don't worry because the old rels will be deleted when the tag is
        # deleted.
        self.delete(commit=False)

        # Enjoy your new life as a monk.
        mastertag.add_synonym(self.name, commit=False)
        if commit:
            self.photodb.log.debug('Committing - convert to synonym')
            self.photodb.commit()

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def delete(self, *, delete_children=False, commit=True):
        self.photodb.log.debug('Deleting %s', self)
        self.photodb._cached_frozen_children = None
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        self.photodb.sql_delete(table='tags', pairs={'id': self.id})
        self.photodb.sql_delete(table='photo_tag_rel', pairs={'tagid': self.id})
        self.photodb.sql_delete(table='tag_synonyms', pairs={'mastername': self.name})
        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - delete tag')
            self.photodb.commit()

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def edit(self, description=None, *, commit=True):
        '''
        Change the description. Leave None to keep current value.
        '''
        if description is None:
            return

        self.description = self.normalize_description(description)

        data = {
            'id': self.id,
            'description': self.description
        }
        self.photodb.sql_update(table='tags', pairs=data, where_key='id')

        self._uncache()
        if commit:
            self.photodb.log.debug('Committing - edit tag')
            self.photodb.commit()

    def get_synonyms(self):
        syn_rows = self.photodb.sql_select(
            'SELECT name FROM tag_synonyms WHERE mastername == ?',
            [self.name]
        )
        syn_names = [row[0] for row in syn_rows]
        syn_names.sort()
        return syn_names

    @decorators.required_feature('tag.edit')
    # GroupableMixin.join_group already has @transaction.
    def join_group(self, *args, **kwargs):
        return super().join_group(*args, **kwargs)

    @decorators.required_feature('tag.edit')
    # GroupableMixin.leave_group already has @transaction.
    def leave_group(self, *args, **kwargs):
        return super().leave_group(*args, **kwargs)

    def qualified_name(self, *, max_len=None):
        '''
        Return the 'group1.group2.tag' string for this tag.

        If `max_len` is not None, bring the length of the qualname down
        by first stripping off ancestors, then slicing the end off of the
        name if necessary.

        ('people.family.mother', max_len=25) -> 'people.family.mother'
        ('people.family.mother', max_len=15) -> 'family.mother'
        ('people.family.mother', max_len=10) -> 'mother'
        ('people.family.mother', max_len=4)  -> 'moth'
        '''
        if max_len is not None:
            if len(self.name) == max_len:
                return self.name
            if len(self.name) > max_len:
                return self.name[:max_len]

        if self._cached_qualified_name:
            qualname = self._cached_qualified_name
        else:
            qualname = self.name
            for parent in self.walk_parents():
                qualname = parent.name + '.' + qualname
            self._cached_qualified_name = qualname

        if max_len is None or len(qualname) <= max_len:
            return qualname

        while len(qualname) > max_len:
            qualname = qualname.split('.', 1)[1]

        return qualname

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def remove_synonym(self, synname, *, commit=True):
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

        self.photodb._cached_frozen_children = None
        self.photodb.sql_delete(table='tag_synonyms', pairs={'name': synname})
        if commit:
            self.photodb.log.debug('Committing - remove synonym')
            self.photodb.commit()

    @decorators.required_feature('tag.edit')
    @decorators.transaction
    def rename(self, new_name, *, apply_to_synonyms=True, commit=True):
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

        self._cached_qualified_name = None
        self.photodb._cached_frozen_children = None

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
        if commit:
            self.photodb.log.debug('Committing - rename tag')
            self.photodb.commit()


class User(ObjectBase):
    '''
    A dear friend of ours.
    '''
    def __init__(self, photodb, db_row):
        super().__init__(photodb)
        if isinstance(db_row, (list, tuple)):
            db_row = dict(zip(constants.SQL_COLUMNS['users'], db_row))
        self.id = db_row['id']
        self.username = db_row['username']
        self.created = db_row['created']
        self.password_hash = db_row['password']
        self._display_name = self.normalize_display_name(db_row['display_name'])

    def __repr__(self):
        rep = f'User:{self.id}:{self.username}'
        return rep

    def __str__(self):
        rep = f'User:{self.username}'
        return rep

    @staticmethod
    def normalize_display_name(display_name, max_length=None):
        if display_name is None:
            return None

        if not isinstance(display_name, str):
            raise TypeError('Display Name must be string, not %s' % type(display_name))

        display_name = display_name.strip()

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

    @decorators.required_feature('user.edit')
    @decorators.transaction
    def set_display_name(self, display_name, *, commit=True):
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

        if commit:
            self.photodb.log.debug('Committing - set display name')
            self.photodb.commit()

class WarningBag:
    def __init__(self):
        self.warnings = set()

    def add(self, warning):
        self.warnings.add(warning)
