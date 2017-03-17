import os
import PIL.Image
import traceback

from . import constants
from . import decorators
from . import exceptions
from . import helpers

from voussoirkit import bytestring
from voussoirkit import pathclass
from voussoirkit import spinal


class ObjectBase:
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


class GroupableMixin:
    group_getter = None
    group_sql_index = None
    group_table = None

    def add(self, member, *, commit=True):
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
        cur = self.photodb.sql.cursor()
        cur.execute(
            'SELECT * FROM %s WHERE memberid == ?' % self.group_table,
            [member.id]
        )
        fetch = cur.fetchone()
        if fetch is not None:
            parent_id = fetch[self.group_sql_index['parentid']]
            if parent_id == self.id:
                return
            that_group = self.group_getter(id=parent_id)
            raise exceptions.GroupExists(member=member, group=that_group)

        for my_ancestor in self.walk_parents():
            if my_ancestor == member:
                raise exceptions.RecursiveGrouping(member=member, group=self)

        self.photodb._cached_frozen_children = None
        cur.execute(
            'INSERT INTO %s VALUES(?, ?)' % self.group_table,
            [self.id, member.id]
        )
        if commit:
            self.photodb.log.debug('Committing - add to group')
            self.photodb.commit()

    def children(self):
        cur = self.photodb.sql.cursor()
        
        cur.execute(
            'SELECT * FROM %s WHERE parentid == ?' % self.group_table,
            [self.id]
        )
        fetch = cur.fetchall()
        results = []
        for f in fetch:
            memberid = f[self.group_sql_index['memberid']]
            child = self.group_getter(id=memberid)
            results.append(child)
        if isinstance(self, Tag):
            results.sort(key=lambda x: x.name)
        else:
            results.sort(key=lambda x: x.id)
        return results

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
        cur = self.photodb.sql.cursor()
        if delete_children:
            for child in self.children():
                child.delete(delete_children=delete_children, commit=False)
        else:
            # Lift children
            parent = self.parent()
            if parent is None:
                # Since this group was a root, children become roots by removing
                # the row.
                cur.execute(
                    'DELETE FROM %s WHERE parentid == ?' % self.group_table,
                    [self.id]
                )
            else:
                # Since this group was a child, its parent adopts all its children.
                cur.execute(
                    'UPDATE %s SET parentid == ? WHERE parentid == ?' % self.group_table,
                    [parent.id, self.id]
                )
        # Note that this part comes after the deletion of children to prevent
        # issues of recursion.
        cur.execute(
            'DELETE FROM %s WHERE memberid == ?' % self.group_table,
            [self.id]
        )
        if commit:
            self.photodb.log.debug('Committing - delete tag')
            self.photodb.commit()

    def parent(self):
        '''
        Return the group of which this is a member, or None.
        Returned object will be of the same type as calling object.
        '''
        cur = self.photodb.sql.cursor()
        cur.execute(
            'SELECT * FROM %s WHERE memberid == ?' % self.group_table,
            [self.id]
        )
        fetch = cur.fetchone()
        if fetch is None:
            return None

        parentid = fetch[self.group_sql_index['parentid']]
        return self.group_getter(id=parentid)

    def join_group(self, group, *, commit=True):
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

    def leave_group(self, *, commit=True):
        '''
        Leave the current group and become independent.
        '''
        cur = self.photodb.sql.cursor()
        self.photodb._cached_frozen_children = None
        cur.execute(
            'DELETE FROM %s WHERE memberid == ?' % self.group_table,
            [self.id]
        )
        if commit:
            self.photodb.log.debug('Committing - leave group')
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
    group_sql_index = constants.SQL_ALBUMGROUP
    group_table = 'album_group_rel'

    def __init__(self, photodb, db_row):
        self.photodb = photodb
        if isinstance(db_row, (list, tuple)):
            db_row = helpers.parallel_to_dict(constants.SQL_ALBUM_COLUMNS, db_row)
        self.id = db_row['id']
        self.title = db_row['title']
        self.description = db_row['description']
        self.name = 'Album %s' % self.id
        self.group_getter = self.photodb.get_album

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return 'Album:{id}'.format(id=self.id)

    def add_photo(self, photo, *, commit=True):
        if self.photodb != photo.photodb:
            raise ValueError('Not the same PhotoDB')
        if self.has_photo(photo):
            return
        self.photodb.log.debug('Adding photo %s to %s' % (photo, self))
        cur = self.photodb.sql.cursor()
        cur.execute('INSERT INTO album_photo_rel VALUES(?, ?)', [self.id, photo.id])
        if commit:
            self.photodb.log.debug('Committing - add photo to album')
            self.photodb.commit()

    def add_tag_to_all(self, tag, *, nested_children=True, commit=True):
        '''
        Add this tag to every photo in the album. Saves you from having to
        write the for-loop yourself.

        nested_children:
            If True, add the tag to photos contained in sub-albums.
            Otherwise, only local photos.
        '''
        tag = self.photodb.get_tag(tag)
        if nested_children:
            photos = self.walk_photos()
        else:
            photos = self.photos()
        for photo in photos:
            photo.add_tag(tag, commit=False)

        if commit:
            self.photodb.log.debug('Committing - add tag to all')
            self.photodb.commit()

    def delete(self, *, delete_children=False, commit=True):
        self.photodb.log.debug('Deleting album {album:r}'.format(album=self))
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        cur = self.photodb.sql.cursor()
        cur.execute('DELETE FROM albums WHERE id == ?', [self.id])
        cur.execute('DELETE FROM album_photo_rel WHERE albumid == ?', [self.id])
        if commit:
            self.photodb.log.debug('Committing - delete album')
            self.photodb.commit()

    @property
    def display_name(self):
        if self.title:
            return self.title
        else:
            return self.id

    def edit(self, title=None, description=None, *, commit=True):
        '''
        Change the title or description. Leave None to keep current value.
        '''
        if title is None:
            title = self.title
        if description is None:
            description = self.description
        cur = self.photodb.sql.cursor()
        cur.execute(
            'UPDATE albums SET title=?, description=? WHERE id == ?',
            [title, description, self.id]
        )
        self.title = title
        self.description = description
        if commit:
            self.photodb.log.debug('Committing - edit album')
            self.photodb.commit()

    def has_photo(self, photo):
        if not isinstance(photo, Photo):
            raise TypeError('Must be a %s' % Photo)
        cur = self.photodb.sql.cursor()
        cur.execute(
            'SELECT * FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        return cur.fetchone() is not None

    def photos(self):
        photos = []
        generator = helpers.select_generator(
            self.photodb.sql,
            'SELECT * FROM album_photo_rel WHERE albumid == ?',
            [self.id]
        )
        for photo in generator:
            photoid = photo[constants.SQL_ALBUMPHOTO['photoid']]
            photo = self.photodb.get_photo(photoid)
            photos.append(photo)
        photos.sort(key=lambda x: x.basename.lower())
        return photos

    def remove_photo(self, photo, *, commit=True):
        if not self.has_photo(photo):
            return
        cur = self.photodb.sql.cursor()
        cur.execute(
            'DELETE FROM album_photo_rel WHERE albumid == ? AND photoid == ?',
            [self.id, photo.id]
        )
        if commit:
            self.photodb.log.debug('Committing - remove photo from album')
            self.photodb.commit()

    def sum_bytes(self, recurse=True, string=False):
        if recurse:
            photos = self.walk_photos()
        else:
            photos = self.photos()

        total = sum(photo.bytes for photo in photos)

        if string:
            return bytestring.bytestring(total)
        else:
            return total

    def walk_photos(self):
        yield from self.photos()
        children = self.walk_children()
        # The first yield is itself
        next(children)
        for child in children:
            yield from child.walk_photos()


class Bookmark(ObjectBase):
    def __init__(self, photodb, db_row):
        self.photodb = photodb
        if isinstance(db_row, (list, tuple)):
            db_row = helpers.parallel_to_dict(constants.SQL_BOOKMARK_COLUMNS, db_row)

        self.id = db_row['id']
        self.title = db_row['title']
        self.url = db_row['url']
        self.author_id = db_row['author_id']

    def __repr__(self):
        return 'Bookmark:{id}'.format(id=self.id)

    def delete(self, *, commit=True):
        cur = self.photodb.sql.cursor()
        cur.execute('DELETE FROM bookmarks WHERE id == ?', [self.id])
        if commit:
            self.photodb.commit()

    def edit(self, title=None, url=None, *, commit=True):
        if title is None and url is None:
            return

        if title is not None:
            self.title = title

        if url is not None:
            self.url = url

        cur = self.photodb.sql.cursor()
        cur.execute(
            'UPDATE bookmarks SET title = ?, url = ? WHERE id == ?',
            [self.title, self.url, self.id]
        )
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
        self.photodb = photodb
        if isinstance(db_row, (list, tuple)):
            db_row = helpers.parallel_to_dict(constants.SQL_PHOTO_COLUMNS, db_row)

        self.real_filepath = helpers.normalize_filepath(db_row['filepath'], allowed=':\\/')
        self.real_path = pathclass.Path(self.real_filepath)

        self.id = db_row['id']
        self.created = db_row['created']
        self.author_id = db_row['author_id']
        self.filepath = db_row['override_filename'] or self.real_path.absolute_path
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
        self.thumbnail = db_row['thumbnail']

        self.mimetype = helpers.get_mimetype(self.real_filepath)
        if self.mimetype is None:
            self.simple_mimetype = None
        else:
            self.simple_mimetype = self.mimetype.split('/')[0]

    def __reinit__(self):
        '''
        Reload the row from the database and do __init__ with them.
        '''
        cur = self.photodb.sql.cursor()
        cur.execute('SELECT * FROM photos WHERE id == ?', [self.id])
        row = cur.fetchone()
        self.__init__(self.photodb, row)

    def __repr__(self):
        return 'Photo:{id}'.format(id=self.id)

    def add_tag(self, tag, *, commit=True):
        if not self.photodb.config['enable_photo_add_remove_tag']:
            raise exceptions.FeatureDisabled('photo.add_tag, photo.remove_tag')

        tag = self.photodb.get_tag(tag)

        existing = self.has_tag(tag, check_children=False)
        if existing:
            return existing

        # If the new tag is less specific than one we already have,
        # keep our current one.
        existing = self.has_tag(tag, check_children=True)
        if existing:
            message = 'Preferring existing {exi:s} over {tag:s}'.format(exi=existing, tag=tag)
            self.photodb.log.debug(message)
            return existing

        # If the new tag is more specific, remove our current one for it.
        for parent in tag.walk_parents():
            if self.has_tag(parent, check_children=False):
                message = 'Preferring new {tag:s} over {par:s}'.format(tag=tag, par=parent)
                self.photodb.log.debug(message)
                self.remove_tag(parent)

        self.photodb.log.debug('Applying tag {tag:s} to photo {pho:s}'.format(tag=tag, pho=self))
        now = int(helpers.now())
        cur = self.photodb.sql.cursor()
        cur.execute('INSERT INTO photo_tag_rel VALUES(?, ?)', [self.id, tag.id])
        cur.execute('UPDATE photos SET tagged_at = ? WHERE id == ?', [now, self.id])
        if commit:
            self.photodb.log.debug('Committing - add photo tag')
            self.photodb.commit()
        return tag

    def albums(self):
        '''
        Return the albums of which this photo is a member.
        '''
        cur = self.photodb.sql.cursor()
        cur.execute('SELECT albumid FROM album_photo_rel WHERE photoid == ?', [self.id])
        fetch = cur.fetchall()
        albums = [self.photodb.get_album(f[0]) for f in fetch]
        return albums

    def author(self):
        return self.photodb.get_user(id=self.author_id)

    def bytestring(self):
        return bytestring.bytestring(self.bytes)

    def copy_tags(self, other_photo):
        '''
        Take all of the tags owned by other_photo and apply them to this photo.
        '''
        for tag in other_photo.tags():
            self.add_tag(tag)

    def delete(self, *, delete_file=False, commit=True):
        '''
        Delete the Photo and its relation to any tags and albums.
        '''
        self.photodb.log.debug('Deleting photo {photo:r}'.format(photo=self))
        cur = self.photodb.sql.cursor()
        cur.execute('DELETE FROM photos WHERE id == ?', [self.id])
        cur.execute('DELETE FROM photo_tag_rel WHERE photoid == ?', [self.id])
        cur.execute('DELETE FROM album_photo_rel WHERE photoid == ?', [self.id])

        if delete_file:
            path = self.real_path.absolute_path
            if commit:
                os.remove(path)
            else:
                queue_action = {'action': os.remove, 'args': [path]}
                self.photodb.on_commit_queue.append(queue_action)
        if commit:
            self.photodb.log.debug('Committing - delete photo')
            self.photodb.commit()

    @property
    def duration_string(self):
        if self.duration is None:
            return None
        return helpers.seconds_to_hms(self.duration)

    #@decorators.time_me
    def generate_thumbnail(self, *, commit=True, **special):
        '''
        special:
            For videos, you can provide a `timestamp` to take the thumbnail from.
        '''
        if not self.photodb.config['enable_photo_generate_thumbnail']:
            raise exceptions.FeatureDisabled('photo.generate_thumbnail')

        hopeful_filepath = self.make_thumbnail_filepath()
        hopeful_filepath = hopeful_filepath.relative_path
        #print(hopeful_filepath)
        return_filepath = None

        if self.simple_mimetype == 'image':
            self.photodb.log.debug('Thumbnailing %s' % self.real_filepath)
            try:
                image = PIL.Image.open(self.real_filepath)
            except (OSError, ValueError):
                pass
            else:
                (width, height) = image.size
                (new_width, new_height) = helpers.fit_into_bounds(
                    image_width=width,
                    image_height=height,
                    frame_width=self.photodb.config['thumbnail_width'],
                    frame_height=self.photodb.config['thumbnail_height'],
                )
                if new_width < width:
                    image = image.resize((new_width, new_height))

                if image.mode == 'RGBA':
                    background = helpers.checkerboard_image(
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
                image.save(hopeful_filepath, quality=50)
                return_filepath = hopeful_filepath

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            #print('video')
            probe = constants.ffmpeg.probe(self.real_filepath)
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
                        self.real_filepath,
                        outfile=hopeful_filepath,
                        quality=2,
                        size=size,
                        time=timestamp,
                    )
            except:
                traceback.print_exc()
            else:
                return_filepath = hopeful_filepath


        if return_filepath != self.thumbnail:
            cur = self.photodb.sql.cursor()
            cur.execute(
                'UPDATE photos SET thumbnail = ? WHERE id == ?',
                [return_filepath, self.id]
            )
            self.thumbnail = return_filepath

        if commit:
            self.photodb.log.debug('Committing - generate thumbnail')
            self.photodb.commit()

        self.__reinit__()
        return self.thumbnail

    def has_tag(self, tag, *, check_children=True):
        '''
        Return the Tag object if this photo contains that tag.
        Otherwise return False.

        check_children:
            If True, children of the requested tag are accepted.
        '''
        tag = self.photodb.get_tag(tag)

        if check_children:
            tags = tag.walk_children()
        else:
            tags = [tag]

        cur = self.photodb.sql.cursor()
        for tag in tags:
            cur.execute(
                'SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid == ?',
                [self.id, tag.id]
            )
            if cur.fetchone() is not None:
                return tag

        return False

    def make_thumbnail_filepath(self):
        '''
        Create the filepath that should be the location of our thumbnail.
        '''
        chunked_id = helpers.chunk_sequence(self.id, 3)
        basename = chunked_id[-1]
        folder = chunked_id[:-1]
        folder = os.sep.join(folder)
        folder = self.photodb.thumbnail_directory.join(folder)
        if folder:
            os.makedirs(folder.absolute_path, exist_ok=True)
        hopeful_filepath = folder.with_child(basename + '.jpg')
        return hopeful_filepath

    #@decorators.time_me
    def reload_metadata(self, *, commit=True):
        '''
        Load the file's height, width, etc as appropriate for this type of file.
        '''
        if not self.photodb.config['enable_photo_reload_metadata']:
            raise exceptions.FeatureDisabled('photo.reload_metadata')

        self.bytes = os.path.getsize(self.real_filepath)
        self.width = None
        self.height = None
        self.area = None
        self.ratio = None
        self.duration = None

        self.photodb.log.debug('Reloading metadata for {photo:r}'.format(photo=self))

        if self.simple_mimetype == 'image':
            try:
                image = PIL.Image.open(self.real_filepath)
            except (OSError, ValueError):
                self.photodb.log.debug('Failed to read image data for {photo:r}'.format(photo=self))
            else:
                (self.width, self.height) = image.size
                image.close()
                #self.photodb.log.debug('Loaded image data for {photo:r}'.format(photo=self))

        elif self.simple_mimetype == 'video' and constants.ffmpeg:
            try:
                probe = constants.ffmpeg.probe(self.real_filepath)
                if probe and probe.video:
                    self.duration = probe.format.duration or probe.video.duration
                    self.width = probe.video.video_width
                    self.height = probe.video.video_height
            except:
                traceback.print_exc()

        elif self.simple_mimetype == 'audio' and constants.ffmpeg:
            try:
                probe = constants.ffmpeg.probe(self.real_filepath)
                if probe and probe.audio:
                    self.duration = probe.audio.duration
            except:
                traceback.print_exc()

        if self.width and self.height:
            self.area = self.width * self.height
            self.ratio = round(self.width / self.height, 2)

        cur = self.photodb.sql.cursor()
        cur.execute(
            'UPDATE photos SET width=?, height=?, area=?, ratio=?, duration=?, bytes=? WHERE id==?',
            [self.width, self.height, self.area, self.ratio, self.duration, self.bytes, self.id],
        )
        if commit:
            self.photodb.log.debug('Committing - reload metadata')
            self.photodb.commit()

    def remove_tag(self, tag, *, commit=True):
        if not self.photodb.config['enable_photo_add_remove_tag']:
            raise exceptions.FeatureDisabled('photo.add_tag, photo.remove_tag')

        tag = self.photodb.get_tag(tag)

        self.photodb.log.debug('Removing tag {t} from photo {p}'.format(t=repr(tag), p=repr(self)))
        tags = list(tag.walk_children())

        cur = self.photodb.sql.cursor()
        for tag in tags:
            cur.execute(
                'DELETE FROM photo_tag_rel WHERE photoid == ? AND tagid == ?',
                [self.id, tag.id]
            )
        now = int(helpers.now())
        cur.execute('UPDATE photos SET tagged_at = ? WHERE id == ?', [now, self.id])
        if commit:
            self.photodb.log.debug('Committing - remove photo tag')
            self.photodb.commit()

    def rename_file(self, new_filename, *, move=False, commit=True):
        '''
        Rename the file on the disk as well as in the database.

        move:
            If True, allow the file to be moved into another directory.
            Otherwise, the rename must be local.
        '''
        old_path = self.real_path
        old_path.correct_case()

        new_filename = helpers.normalize_filepath(new_filename, allowed=':\\/')
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

        cur = self.photodb.sql.cursor()
        cur.execute(
            'UPDATE photos SET filepath = ? WHERE filepath == ?',
            [new_path.absolute_path, old_path.absolute_path]
        )

        if new_path.normcase == old_path.normcase:
            # If they are equivalent but differently cased, just rename.
            action = os.rename
            args = [old_path.absolute_path, new_path.absolute_path]
        else:
            # Delete the original, leaving only the new copy / hardlink.
            action = os.remove
            args = [old_path.absolute_path]
        
        if commit:
            action(*args)
            self.photodb.log.debug('Committing - rename file')
            self.photodb.commit()
        else:
            queue_action = {'action': action, 'args': args}
            self.photodb.on_commit_queue.append(queue_action)

        self.__reinit__()

    def sorted_tags(self):
        tags = self.tags()
        tags.sort(key=lambda x: x.qualified_name())
        return tags

    def tags(self):
        '''
        Return the tags assigned to this Photo.
        '''
        tags = []
        generator = helpers.select_generator(
            self.photodb.sql,
            'SELECT * FROM photo_tag_rel WHERE photoid == ?',
            [self.id]
        )
        for tag in generator:
            tagid = tag[constants.SQL_PHOTOTAG['tagid']]
            tag = self.photodb.get_tag(id=tagid)
            tags.append(tag)
        return tags


class Tag(ObjectBase, GroupableMixin):
    '''
    A Tag, which can be applied to Photos for organization.
    '''
    group_sql_index = constants.SQL_TAGGROUP
    group_table = 'tag_group_rel'

    def __init__(self, photodb, db_row):
        self.photodb = photodb
        if isinstance(db_row, (list, tuple)):
            db_row = helpers.parallel_to_dict(constants.SQL_TAG_COLUMNS, db_row)
        self.id = db_row['id']
        self.name = db_row['name']
        self.group_getter = self.photodb.get_tag
        self._cached_qualified_name = None

    def __eq__(self, other):
        return self.name == other or ObjectBase.__eq__(self, other)

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        rep = 'Tag:{id}:{name}'.format(name=self.name, id=self.id)
        return rep

    def __str__(self):
        rep = 'Tag:{name}'.format(name=self.name)
        return rep

    def add_synonym(self, synname, *, commit=True):
        synname = self.photodb.normalize_tagname(synname)

        print(synname, self.name)
        if synname == self.name:
            raise exceptions.CantSynonymSelf()

        try:
            existing_tag = self.photodb.get_tag_by_name(synname)
        except exceptions.NoSuchTag:
            pass
        else:
            raise exceptions.TagExists(existing_tag)

        self.photodb._cached_frozen_children = None
        cur = self.photodb.sql.cursor()
        cur.execute('INSERT INTO tag_synonyms VALUES(?, ?)', [synname, self.name])

        if commit:
            self.photodb.log.debug('Committing - add synonym')
            self.photodb.commit()

    def convert_to_synonym(self, mastertag, *, commit=True):
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
        cur = self.photodb.sql.cursor()
        cur.execute(
            'UPDATE tag_synonyms SET mastername = ? WHERE mastername == ?',
            [mastertag.name, self.name]
        )

        # Iterate over all photos with the old tag, and swap them to the new tag
        # if they don't already have it.
        generator = helpers.select_generator(
            self.photodb.sql,
            'SELECT * FROM photo_tag_rel WHERE tagid == ?',
            [self.id]
        )
        for relationship in generator:
            photoid = relationship[constants.SQL_PHOTOTAG['photoid']]
            cur.execute(
                'SELECT * FROM photo_tag_rel WHERE photoid == ? AND tagid == ?',
                [photoid, mastertag.id]
            )
            if cur.fetchone() is None:
                cur.execute(
                    'INSERT INTO photo_tag_rel VALUES(?, ?)',
                    [photoid, mastertag.id]
                )

        # Then delete the relationships with the old tag
        self.delete()

        # Enjoy your new life as a monk.
        mastertag.add_synonym(self.name, commit=False)
        if commit:
            self.photodb.log.debug('Committing - convert to synonym')
            self.photodb.commit()

    def delete(self, *, delete_children=False, commit=True):
        self.photodb.log.debug('Deleting tag {tag:r}'.format(tag=self))
        self.photodb._cached_frozen_children = None
        GroupableMixin.delete(self, delete_children=delete_children, commit=False)
        cur = self.photodb.sql.cursor()
        cur.execute('DELETE FROM tags WHERE id == ?', [self.id])
        cur.execute('DELETE FROM photo_tag_rel WHERE tagid == ?', [self.id])
        cur.execute('DELETE FROM tag_synonyms WHERE mastername == ?', [self.name])
        if commit:
            self.photodb.log.debug('Committing - delete tag')
            self.photodb.commit()

    def qualified_name(self):
        '''
        Return the 'group1.group2.tag' string for this tag.
        '''
        if self._cached_qualified_name:
            return self._cached_qualified_name
        qualname = self.name
        for parent in self.walk_parents():
            qualname = parent.name + '.' + qualname
        self._cached_qualified_name = qualname
        return qualname

    def remove_synonym(self, synname, *, commit=True):
        '''
        Delete a synonym.
        This will have no effect on photos or other synonyms because
        they always resolve to the master tag before application.
        '''
        synname = self.photodb.normalize_tagname(synname)
        if synname == self.name:
            raise exceptions.NoSuchSynonym(synname)

        cur = self.photodb.sql.cursor()
        cur.execute(
            'SELECT * FROM tag_synonyms WHERE mastername == ? AND name == ?',
            [self.name, synname]
        )
        fetch = cur.fetchone()
        if fetch is None:
            raise exceptions.NoSuchSynonym(synname)

        self.photodb._cached_frozen_children = None
        cur.execute('DELETE FROM tag_synonyms WHERE name == ?', [synname])
        if commit:
            self.photodb.log.debug('Committing - remove synonym')
            self.photodb.commit()

    def rename(self, new_name, *, apply_to_synonyms=True, commit=True):
        '''
        Rename the tag. Does not affect its relation to Photos or tag groups.
        '''
        new_name = self.photodb.normalize_tagname(new_name)
        if new_name == self.name:
            return

        try:
            existing_tag = self.photodb.get_tag(new_name)
        except exceptions.NoSuchTag:
            pass
        else:
            raise exceptions.TagExists(existing_tag)

        self._cached_qualified_name = None
        self.photodb._cached_frozen_children = None
        cur = self.photodb.sql.cursor()
        cur.execute('UPDATE tags SET name = ? WHERE id == ?', [new_name, self.id])
        if apply_to_synonyms:
            cur.execute(
                'UPDATE tag_synonyms SET mastername = ? WHERE mastername = ?',
                [new_name, self.name]
            )

        self.name = new_name
        if commit:
            self.photodb.log.debug('Committing - rename tag')
            self.photodb.commit()

    def synonyms(self):
        cur = self.photodb.sql.cursor()
        cur.execute('SELECT name FROM tag_synonyms WHERE mastername == ?', [self.name])
        fetch = cur.fetchall()
        fetch = [f[0] for f in fetch]
        fetch.sort()
        return fetch


class User(ObjectBase):
    '''
    A dear friend of ours.
    '''
    def __init__(self, photodb, db_row):
        self.photodb = photodb
        if isinstance(db_row, (list, tuple)):
            db_row = helpers.parallel_to_dict(constants.SQL_USER_COLUMNS, db_row)
        self.id = db_row['id']
        self.username = db_row['username']
        self.created = db_row['created']

    def __repr__(self):
        rep = 'User:{id}:{username}'.format(id=self.id, username=self.username)
        return rep

    def __str__(self):
        rep = 'User:{username}'.format(username=self.username)
        return rep


class WarningBag:
    def __init__(self):
        self.warnings = set()

    def add(self, warning):
        self.warnings.add(warning)
