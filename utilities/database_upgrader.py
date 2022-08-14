import time
import argparse
import os
import sys

from voussoirkit import vlogging

import etiquette

log = vlogging.get_logger(__name__, 'database_upgrader')

class Migrator:
    '''
    Many of the upgraders involve adding columns. ALTER TABLE ADD COLUMN only
    allows adding at the end, which I usually don't prefer. In order to add a
    column in the middle, you must rename the table, create a new one, transfer
    the data, and drop the old one. But, foreign keys and indices will still
    point to the old table, which causes broken foreign keys and dropped
    indices. So, the only way to prevent all that is to regenerate all affected
    tables and indices. Rather than parsing relationships to determine the
    affected tables, this implementation just regenerates everything.

    It's kind of horrible but it allows me to have the columns in the order I
    want instead of just always appending. Besides, modifying collations cannot
    be done in-place either.

    If you want to truly remove a table or index and not have it get
    regenerated, just do that before instantiating the Migrator.
    '''
    def __init__(self, photodb):
        self.photodb = photodb

        query = 'SELECT name, sql FROM sqlite_master WHERE type == "table"'
        self.tables = {
            name: {'create': sql, 'transfer': f'INSERT INTO {name} SELECT * FROM {name}_old'}
            for (name, sql) in self.photodb.select(query)
        }

        # The user may be adding entirely new tables derived from the data of
        # old ones. We'll need to skip new tables for the rename and drop_old
        # steps. So we track which tables already existed at the beginning.
        self.existing_tables = set(self.tables)

        query = 'SELECT name, sql FROM sqlite_master WHERE type == "index" AND name NOT LIKE "sqlite_%"'
        self.indices = list(self.photodb.select(query))

    def go(self):
        # This loop is split in many parts, because otherwise if table A
        # references table B and table A is completely reconstructed, it will
        # be pointing to the version of B which has not been reconstructed yet,
        # which is about to get renamed to B_old and then A's reference will be
        # broken.
        self.photodb.pragma_write('foreign_keys', 'OFF')

        for (name, query) in self.indices:
            self.photodb.execute(f'DROP INDEX {name}')

        for (name, table) in self.tables.items():
            if name not in self.existing_tables:
                continue
            self.photodb.execute(f'ALTER TABLE {name} RENAME TO {name}_old')

        for (name, table) in self.tables.items():
            self.photodb.execute(table['create'])

        for (name, table) in self.tables.items():
            self.photodb.execute(table['transfer'])

        for (name, query) in self.tables.items():
            if name not in self.existing_tables:
                continue
            self.photodb.execute(f'DROP TABLE {name}_old')

        for (name, query) in self.indices:
            self.photodb.execute(query)
        self.photodb.pragma_write('foreign_keys', 'ON')

def upgrade_1_to_2(photodb):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    photodb.execute('ALTER TABLE photos ADD COLUMN tagged_at INT')

def upgrade_2_to_3(photodb):
    '''
    Preliminary support for user account management was added. This includes a `users` table
    with id, username, password hash, and a timestamp.
    Plus some indices.
    '''
    photodb.executescript('''
    CREATE TABLE users(
        id TEXT,
        username TEXT COLLATE NOCASE,
        password BLOB,
        created INT
    );

    CREATE INDEX IF NOT EXISTS index_user_id ON users(id);

    CREATE INDEX IF NOT EXISTS index_user_username ON users(username COLLATE NOCASE);
    ''')

def upgrade_3_to_4(photodb):
    '''
    Add an `author_id` column to Photos.
    '''
    photodb.executescript('''
    ALTER TABLE photos ADD COLUMN author_id TEXT;

    CREATE INDEX IF NOT EXISTS index_photo_author ON photos(author_id);
    ''')

def upgrade_4_to_5(photodb):
    '''
    Add table `bookmarks` and its indices.
    '''
    photodb.executescript('''
    CREATE TABLE bookmarks(
        id TEXT,
        title TEXT,
        url TEXT,
        author_id TEXT
    );

    CREATE INDEX IF NOT EXISTS index_bookmark_id ON bookmarks(id);

    CREATE INDEX IF NOT EXISTS index_bookmark_author ON bookmarks(author_id);
    ''')

def upgrade_5_to_6(photodb):
    '''
    When Albums were first introduced, they shared the ID counter and
    relationship table with tags, because they were mostly identical at the time.
    However this is very ugly and confusing and it's time to finally change it.
    - Renames old indices `index_grouprel_*` to `index_taggroup_*`
    - Creates new indices `index_albumgroup_*`
    - Creates new table `album_group_rel`
    - Moves all album group relationships out of `tag_group_rel` and
      into `album_group_rel`
    - Gives albums their own last_id value, starting with the current tag value.
    '''
    photodb.execute('BEGIN')
    # 1. Start the id_numbers.albums value at the tags value so that the number
    # can continue to increment safely and separately, instead of starting at
    # zero and bumping into existing albums.
    last_id = photodb.select_one_value('SELECT last_id FROM id_numbers WHERE tab == "tags"')
    photodb.execute('INSERT INTO id_numbers VALUES("albums", ?)', [last_id])

    # 2. Now's a good chance to rename 'index_grouprel' to 'index_taggroup'.
    photodb.executescript('''
    DROP INDEX IF EXISTS index_grouprel_parentid;
    DROP INDEX IF EXISTS index_grouprel_memberid;
    CREATE INDEX index_taggroup_parentid ON tag_group_rel(parentid);
    CREATE INDEX index_taggroup_memberid ON tag_group_rel(memberid);
    ''')

    # 3. All of the album group relationships need to be moved into their
    # own table, out of tag_group_rel
    photodb.executescript('''
    CREATE TABLE album_group_rel(parentid TEXT, memberid TEXT);
    CREATE INDEX index_albumgroup_parentid ON album_group_rel(parentid);
    CREATE INDEX index_albumgroup_memberid ON album_group_rel(memberid);
    ''')

    album_ids = list(photodb.select_column('SELECT id FROM albums'))
    for album_id in album_ids:
        query = 'SELECT * FROM tag_group_rel WHERE parentid == ? OR memberid == ?'
        bindings = [album_id, album_id]
        grouprels = list(photodb.select(query, bindings))

        if not grouprels:
            continue

        for grouprel in grouprels:
            photodb.execute('INSERT INTO album_group_rel VALUES(?, ?)', grouprel)

        query = 'DELETE FROM tag_group_rel WHERE parentid == ? OR memberid == ?'
        bindings = [album_id, album_id]
        photodb.execute(query, bindings)

def upgrade_6_to_7(photodb):
    '''
    Albums lost their `associated_directory` column, and it has been moved to a
    separate table `album_associated_directories`, so that we can have albums
    which load from multiple directories.

    Most of the indices were renamed.
    '''
    photodb.execute('BEGIN')
    query = 'SELECT name FROM sqlite_master WHERE type == "index" AND name NOT LIKE "sqlite_%"'
    indices = photodb.select_column(query)
    for index in indices:
        photodb.execute(f'DROP INDEX {index}')

    m = Migrator(photodb)
    m.tables['album_associated_directories']['create'] = '''
    CREATE TABLE album_associated_directories(
        albumid TEXT,
        directory TEXT COLLATE NOCASE
    );
    '''
    m.tables['album_associated_directories']['transfer'] = '''
    INSERT INTO album_associated_directories SELECT
        id,
        associated_directory
    FROM albums_old
    WHERE associated_directory IS NOT NULL;
    '''

    m.tables['albums']['create'] = '''
    CREATE TABLE albums(
        id TEXT,
        title TEXT,
        description TEXT
    );
    '''
    m.tables['albums']['transfer'] = '''
    INSERT INTO albums SELECT
        id,
        title,
        description
    FROM albums_old;
    '''

    m.go()

    photodb.executescript('''
    CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
        album_associated_directories(albumid);
    CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
        album_associated_directories(directory);
    CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
    CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
    CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
    CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
    CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
    CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
    CREATE INDEX IF NOT EXISTS index_bookmarks_author on bookmarks(author_id);
    CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
    CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
    CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
    CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
    CREATE INDEX IF NOT EXISTS index_photos_override_filename on
        photos(override_filename COLLATE NOCASE);
    CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
    CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
    CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
    CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
    CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
    CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
    CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
    CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
    CREATE INDEX IF NOT EXISTS index_users_id on users(id);
    CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
    ''')

def upgrade_7_to_8(photodb):
    '''
    Give the Tags table a description field.
    '''
    photodb.executescript('ALTER TABLE tags ADD COLUMN description TEXT')

def upgrade_8_to_9(photodb):
    '''
    Give the Photos table a searchhidden field.
    '''
    photodb.executescript('''
    ALTER TABLE photos ADD COLUMN searchhidden INT;

    UPDATE photos SET searchhidden = 0;

    CREATE INDEX index_photos_searchhidden on photos(searchhidden);
    ''')

def upgrade_9_to_10(photodb):
    '''
    From now on, the filepath stored in Photo's thumbnail column should be a
    relative path where . is the PhotoDB's thumbnail_directory.
    Previously, the stored path was unnecessarily high and contained the PDB's
    data_directory, reducing portability.
    '''
    photodb.execute('BEGIN')
    photos = list(photodb.search(has_thumbnail=True, is_searchhidden=None, yield_albums=False))

    # Since we're doing it all at once, I'm going to cheat and skip the
    # relative_to() calculation.
    thumbnail_dir = photodb.thumbnail_directory.absolute_path
    for photo in photos:
        new_thumbnail_path = photo.make_thumbnail_filepath()
        new_thumbnail_path = new_thumbnail_path.absolute_path
        new_thumbnail_path = '.' + new_thumbnail_path.replace(thumbnail_dir, '')
        photodb.execute(
            'UPDATE photos SET thumbnail = ? WHERE id == ?',
            [new_thumbnail_path, photo.id]
        )

def upgrade_10_to_11(photodb):
    '''
    Added Primary keys, Foreign keys, and NOT NULL constraints.
    Added author_id column to Album and Tag tables.
    '''
    m = Migrator(photodb)

    m.tables['albums']['create'] = '''
    CREATE TABLE albums(
        id TEXT PRIMARY KEY NOT NULL,
        title TEXT,
        description TEXT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['albums']['transfer'] = '''
    INSERT INTO albums SELECT
        id,
        title,
        description,
        NULL
    FROM albums_old;
    '''

    m.tables['tags']['create'] = '''
    CREATE TABLE tags(
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['tags']['transfer'] = '''
    INSERT INTO tags SELECT
        id,
        name,
        description,
        NULL
    FROM tags_old;
    '''

    m.go()

def upgrade_11_to_12(photodb):
    '''
    Added multicolumn (photoid, tagid) index to the photo_tag_rel table to
    improve the speed of individual relation searching, important for the
    new intersection-based search.
    '''
    photodb.execute('''
    CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid_tagid on photo_tag_rel(photoid, tagid);
    ''')

def upgrade_12_to_13(photodb):
    '''
    Added display_name column to the User table.
    '''
    m = Migrator(photodb)
    m.tables['users']['create'] = '''
    CREATE TABLE users(
        id TEXT PRIMARY KEY NOT NULL,
        username TEXT NOT NULL COLLATE NOCASE,
        password BLOB NOT NULL,
        display_name TEXT,
        created INT
    );
    '''
    m.tables['users']['transfer'] = '''
    INSERT INTO users SELECT
        id,
        username,
        password,
        NULL,
        created
    FROM users_old;
    '''

def upgrade_13_to_14(photodb):
    '''
    Rename user.min_length to min_username_length.
    '''
    photodb.config['user']['min_username_length'] = photodb.config['user'].pop('min_length')
    photodb.config['user']['max_username_length'] = photodb.config['user'].pop('max_length')
    photodb.save_config()

def upgrade_14_to_15(photodb):
    '''
    Added the dev_ino column to photos.
    '''
    m = Migrator(photodb)
    m.tables['photos']['create'] = '''
    CREATE TABLE photos(
        id TEXT PRIMARY KEY NOT NULL,
        filepath TEXT COLLATE NOCASE,
        dev_ino TEXT,
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
        author_id TEXT,
        searchhidden INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['photos']['transfer'] = '''
    INSERT INTO photos SELECT
        id,
        filepath,
        NULL,
        override_filename,
        extension,
        width,
        height,
        ratio,
        area,
        duration,
        bytes,
        created,
        thumbnail,
        tagged_at,
        author_id,
        searchhidden
    FROM photos_old;
    '''

    m.go()

    photodb.execute('CREATE INDEX index_photos_dev_ino ON photos(dev_ino);')

    for photo in photodb.get_photos_by_recent():
        if not photo.real_path.is_file:
            continue
        stat = photo.real_path.stat
        (dev, ino) = (stat.st_dev, stat.st_ino)
        if dev == 0 or ino == 0:
            continue
        dev_ino = f'{dev},{ino}'
        photodb.execute('UPDATE photos SET dev_ino = ? WHERE id == ?', [dev_ino, photo.id])

def upgrade_15_to_16(photodb):
    '''
    Added the basename column to photos. Added collate nocase to extension.
    '''
    m = Migrator(photodb)
    m.tables['photos']['create'] = '''
    CREATE TABLE photos(
        id TEXT PRIMARY KEY NOT NULL,
        filepath TEXT COLLATE NOCASE,
        dev_ino TEXT,
        basename TEXT COLLATE NOCASE,
        override_filename TEXT COLLATE NOCASE,
        extension TEXT COLLATE NOCASE,
        width INT,
        height INT,
        ratio REAL,
        area INT,
        duration INT,
        bytes INT,
        created INT,
        thumbnail TEXT,
        tagged_at INT,
        author_id TEXT,
        searchhidden INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['photos']['transfer'] = '''
    INSERT INTO photos SELECT
        id,
        filepath,
        dev_ino,
        NULL,
        override_filename,
        extension,
        width,
        height,
        ratio,
        area,
        duration,
        bytes,
        created,
        thumbnail,
        tagged_at,
        author_id,
        searchhidden
    FROM photos_old;
    '''

    m.go()

    for (id, filepath) in photodb.select('SELECT id, filepath FROM photos'):
        basename = os.path.basename(filepath)
        photodb.execute('UPDATE photos SET basename = ? WHERE id == ?', [basename, id])

def upgrade_16_to_17(photodb):
    '''
    Added the created column to albums, bookmarks, tags.
    '''
    m = Migrator(photodb)
    m.tables['albums']['create'] = '''
    CREATE TABLE albums(
        id TEXT PRIMARY KEY NOT NULL,
        title TEXT,
        description TEXT,
        created INT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['albums']['transfer'] = '''
    INSERT INTO albums SELECT
        id,
        title,
        description,
        0,
        author_id
    FROM albums_old;
    '''

    m.tables['bookmarks']['create'] = '''
    CREATE TABLE bookmarks(
        id TEXT PRIMARY KEY NOT NULL,
        title TEXT,
        url TEXT,
        created INT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['bookmarks']['transfer'] = '''
    INSERT INTO bookmarks SELECT
        id,
        title,
        url,
        0,
        author_id
    FROM bookmarks_old;
    '''

    m.tables['tags']['create'] = '''
    CREATE TABLE tags(
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        created INT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['tags']['transfer'] = '''
    INSERT INTO tags SELECT
        id,
        name,
        description,
        0,
        author_id
    FROM tags_old;
    '''

    m.go()

def upgrade_17_to_18(photodb):
    '''
    Added the thumbnail_photo column to albums.
    '''
    m = Migrator(photodb)
    m.tables['albums']['create'] = '''
    CREATE TABLE albums(
        id TEXT PRIMARY KEY NOT NULL,
        title TEXT,
        description TEXT,
        created INT,
        thumbnail_photo TEXT,
        author_id TEXT,
        FOREIGN KEY(author_id) REFERENCES users(id),
        FOREIGN KEY(thumbnail_photo) REFERENCES photos(id)
    );
    '''
    m.tables['albums']['transfer'] = '''
    INSERT INTO albums SELECT
        id,
        title,
        description,
        created,
        NULL,
        author_id
    FROM albums_old;
    '''

    m.go()

def upgrade_18_to_19(photodb):
    m = Migrator(photodb)

    m.tables['photos']['create'] = '''
    CREATE TABLE photos(
        id TEXT PRIMARY KEY NOT NULL,
        filepath TEXT COLLATE NOCASE,
        basename TEXT COLLATE NOCASE,
        override_filename TEXT COLLATE NOCASE,
        extension TEXT COLLATE NOCASE,
        mtime INT,
        sha256 TEXT,
        width INT,
        height INT,
        ratio REAL,
        area INT,
        duration INT,
        bytes INT,
        created INT,
        thumbnail TEXT,
        tagged_at INT,
        author_id TEXT,
        searchhidden INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['photos']['transfer'] = '''
    INSERT INTO photos SELECT
        id,
        filepath,
        basename,
        override_filename,
        extension,
        NULL,
        NULL,
        width,
        height,
        ratio,
        area,
        duration,
        bytes,
        created,
        thumbnail,
        tagged_at,
        author_id,
        searchhidden
    FROM photos_old;
    '''

    m.go()

def upgrade_19_to_20(photodb):
    '''
    In this version, the thumbnail folder was renamed from "site_thumbnails"
    to just "thumbnails".
    '''
    old = photodb.data_directory.with_child('site_thumbnails')
    if not old.exists:
        return
    new = photodb.data_directory.with_child('thumbnails')
    if new.exists:
        if len(new.listdir()) > 0:
            raise Exception(f'{new.absolute_path} already has items in it.')
        else:
            os.rmdir(new)

    photodb.execute('UPDATE photos SET thumbnail = REPLACE(thumbnail, "/site_thumbnails/", "/thumbnails/")')
    photodb.execute('UPDATE photos SET thumbnail = REPLACE(thumbnail, "\\site_thumbnails\\", "\\thumbnails\\")')
    photodb.on_commit_queue.append({'action': os.rename, 'args': (old, new)})

def upgrade_20_to_21(photodb):
    '''
    In this version, the object IDs were migrated from string to int.
    '''
    m = Migrator(photodb)

    m.tables['albums']['create'] = '''
    CREATE TABLE IF NOT EXISTS albums(
        id INT PRIMARY KEY NOT NULL,
        title TEXT,
        description TEXT,
        created INT,
        thumbnail_photo INT,
        author_id INT,
        FOREIGN KEY(author_id) REFERENCES users(id),
        FOREIGN KEY(thumbnail_photo) REFERENCES photos(id)
    );
    '''
    m.tables['albums']['transfer'] = 'INSERT INTO albums SELECT * FROM albums_old'

    m.tables['bookmarks']['create'] = '''
    CREATE TABLE IF NOT EXISTS bookmarks(
        id INT PRIMARY KEY NOT NULL,
        title TEXT,
        url TEXT,
        created INT,
        author_id INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['bookmarks']['transfer'] = 'INSERT INTO bookmarks SELECT * FROM bookmarks_old'

    m.tables['photos']['create'] = '''
    CREATE TABLE IF NOT EXISTS photos(
        id INT PRIMARY KEY NOT NULL,
        filepath TEXT COLLATE NOCASE,
        basename TEXT COLLATE NOCASE,
        override_filename TEXT COLLATE NOCASE,
        extension TEXT COLLATE NOCASE,
        mtime INT,
        sha256 TEXT,
        width INT,
        height INT,
        ratio REAL,
        area INT,
        duration INT,
        bytes INT,
        created INT,
        thumbnail TEXT,
        tagged_at INT,
        author_id INT,
        searchhidden INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['photos']['transfer'] = 'INSERT INTO photos SELECT * FROM photos_old'

    m.tables['tags']['create'] = '''
    CREATE TABLE IF NOT EXISTS tags(
        id INT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        created INT,
        author_id INT,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['tags']['transfer'] = 'INSERT INTO tags SELECT * FROM tags_old'

    m.tables['users']['create'] = '''
    CREATE TABLE IF NOT EXISTS users(
        id INT PRIMARY KEY NOT NULL,
        username TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password BLOB NOT NULL,
        display_name TEXT,
        created INT
    );
    '''
    m.tables['users']['transfer'] = 'INSERT INTO users SELECT * FROM users_old'

    m.tables['album_associated_directories']['create'] = '''
    CREATE TABLE IF NOT EXISTS album_associated_directories(
        albumid INT NOT NULL,
        directory TEXT NOT NULL COLLATE NOCASE,
        FOREIGN KEY(albumid) REFERENCES albums(id)
    );
    '''
    m.tables['album_associated_directories']['transfer'] = 'INSERT INTO album_associated_directories SELECT * FROM album_associated_directories_old'

    m.tables['album_group_rel']['create'] = '''
    CREATE TABLE IF NOT EXISTS album_group_rel(
        parentid INT NOT NULL,
        memberid INT NOT NULL,
        FOREIGN KEY(parentid) REFERENCES albums(id),
        FOREIGN KEY(memberid) REFERENCES albums(id)
    );
    '''
    m.tables['album_group_rel']['transfer'] = 'INSERT INTO album_group_rel SELECT * FROM album_group_rel_old'

    m.tables['album_photo_rel']['create'] = '''
    CREATE TABLE IF NOT EXISTS album_photo_rel(
        albumid INT NOT NULL,
        photoid INT NOT NULL,
        FOREIGN KEY(albumid) REFERENCES albums(id),
        FOREIGN KEY(photoid) REFERENCES photos(id)
    );
    '''
    m.tables['album_photo_rel']['transfer'] = 'INSERT INTO album_photo_rel SELECT * FROM album_photo_rel_old'

    m.tables['photo_tag_rel']['create'] = '''
    CREATE TABLE IF NOT EXISTS photo_tag_rel(
        photoid INT NOT NULL,
        tagid INT NOT NULL,
        FOREIGN KEY(photoid) REFERENCES photos(id),
        FOREIGN KEY(tagid) REFERENCES tags(id)
    );
    '''
    m.tables['photo_tag_rel']['transfer'] = 'INSERT INTO photo_tag_rel SELECT * FROM photo_tag_rel_old'

    m.tables['tag_group_rel']['create'] = '''
    CREATE TABLE IF NOT EXISTS tag_group_rel(
        parentid INT NOT NULL,
        memberid INT NOT NULL,
        FOREIGN KEY(parentid) REFERENCES tags(id),
        FOREIGN KEY(memberid) REFERENCES tags(id)
    );
    '''
    m.tables['tag_group_rel']['transfer'] = 'INSERT INTO tag_group_rel SELECT * FROM tag_group_rel_old'

    m.go()

    users = list(photodb.get_users())
    for user in users:
        old_id = user.id
        new_id = photodb.generate_id(etiquette.objects.User)
        photodb.execute('UPDATE users SET id = ? WHERE id = ?', [new_id, old_id])
        photodb.execute('UPDATE albums SET author_id = ? WHERE author_id = ?', [new_id, old_id])
        photodb.execute('UPDATE bookmarks SET author_id = ? WHERE author_id = ?', [new_id, old_id])
        photodb.execute('UPDATE photos SET author_id = ? WHERE author_id = ?', [new_id, old_id])
        photodb.execute('UPDATE tags SET author_id = ? WHERE author_id = ?', [new_id, old_id])

    def movethumbnail(old_thumbnail, new_thumbnail):
        new_thumbnail.parent.makedirs(exist_ok=True)
        shutil.move(old_thumbnail.absolute_path, new_thumbnail.absolute_path)

    photos = photodb.get_photos()
    import shutil
    for photo in photos:
        if photo.thumbnail is None:
            continue
        old_thumbnail = photo.thumbnail
        new_thumbnail = photo.make_thumbnail_filepath()
        print(old_thumbnail, new_thumbnail)
        photodb.on_commit_queue.append({'action': movethumbnail, 'args': (old_thumbnail, new_thumbnail)})
        store_as = new_thumbnail.relative_to(photodb.thumbnail_directory)
        photodb.update(table=etiquette.objects.Photo, pairs={'id': photo.id, 'thumbnail': store_as}, where_key='id')
        photo.thumbnail = new_thumbnail

def upgrade_21_to_22(photodb):
    m = Migrator(photodb)

    m.tables['photos']['create'] = '''
    CREATE TABLE IF NOT EXISTS photos(
        id INT PRIMARY KEY NOT NULL,
        filepath TEXT COLLATE NOCASE,
        override_filename TEXT COLLATE NOCASE,
        mtime INT,
        sha256 TEXT,
        width INT,
        height INT,
        duration INT,
        bytes INT,
        created INT,
        thumbnail TEXT,
        tagged_at INT,
        author_id INT,
        searchhidden INT,
        -- GENERATED COLUMNS
        area INT GENERATED ALWAYS AS (width * height) VIRTUAL,
        aspectratio REAL GENERATED ALWAYS AS (1.0 * width / height) VIRTUAL,
        -- Thank you ungalcrys
        -- https://stackoverflow.com/a/38330814/5430534
        basename TEXT GENERATED ALWAYS AS (
            COALESCE(
                override_filename,
                replace(filepath, rtrim(filepath, replace(replace(filepath, '\\', '/'), '/', '')), '')
            )
        ) STORED COLLATE NOCASE,
        extension TEXT GENERATED ALWAYS AS (
            replace(basename, rtrim(basename, replace(basename, '.', '')), '')
        ) VIRTUAL COLLATE NOCASE,
        bitrate REAL GENERATED ALWAYS AS ((bytes / 128) / duration) VIRTUAL,
        FOREIGN KEY(author_id) REFERENCES users(id)
    );
    '''
    m.tables['photos']['transfer'] = '''
    INSERT INTO photos SELECT
        id,
        filepath,
        override_filename,
        mtime,
        sha256,
        width,
        height,
        duration,
        bytes,
        created,
        thumbnail,
        tagged_at,
        author_id,
        searchhidden
    FROM photos_old;
    '''

    m.go()

    photodb.execute('DROP INDEX index_photos_override_filename')
    photodb.execute('CREATE INDEX IF NOT EXISTS index_photos_basename on photos(basename COLLATE NOCASE)')

def upgrade_all(data_directory):
    '''
    Given the directory containing a phototagger database, apply all of the
    needed upgrade_x_to_y functions in order.
    '''
    photodb = etiquette.photodb.PhotoDB(data_directory, create=False, skip_version_check=True)

    current_version = photodb.pragma_read('user_version')
    needed_version = etiquette.constants.DATABASE_VERSION

    if current_version == needed_version:
        print('Already up to date with version %d.' % needed_version)
        photodb.close()
        return

    for version_number in range(current_version + 1, needed_version + 1):
        print('Upgrading from %d to %d.' % (current_version, version_number))
        upgrade_function = 'upgrade_%d_to_%d' % (current_version, version_number)
        upgrade_function = eval(upgrade_function)

        photodb.pragma_write('journal_mode', 'wal')
        with photodb.transaction:
            photodb.pragma_write('foreign_keys', 'ON')
            upgrade_function(photodb)
            photodb.pragma_write('user_version', version_number)

        current_version = version_number
    photodb.close()
    print('Upgrades finished.')

def upgrade_all_argparse(args):
    return upgrade_all(data_directory=args.data_directory)

@vlogging.main_decorator
def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('data_directory')
    parser.set_defaults(func=upgrade_all_argparse)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
