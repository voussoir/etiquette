import argparse
import os
import sys

from voussoirkit import sqlhelpers

import etiquette

import old_inits

class Regenerator:
    '''
    Many of the upgraders involve adding columns. ALTER TABLE ADD COLUMN only
    allows adding at the end, which I usually don't prefer. In order to add a
    column in the middle, you must rename the table, create a new one, transfer
    the data, and drop the old one. But, foreign keys and indices will still
    point to the old table, which causes broken foreign keys and dropped
    indices. So, the only way to prevent all that is to regenerate all affected
    tables and indices. Rathern than parsing relationships to determine the
    affected tables, this implementation just regenerates everything.

    It's kind of horrible but it allows me to have the columns in the order I
    want instead of just always appending. Besides, modifying collations cannot
    be done in-place either.
    '''
    def __init__(self, photodb, except_tables=[]):
        self.photodb = photodb
        if isinstance(except_tables, str):
            except_tables = [except_tables]
        self.except_tables = except_tables

    def __enter__(self):
        query = 'SELECT name, sql FROM sqlite_master WHERE type == "table"'
        if self.except_tables:
            query += ' AND name NOT IN ' + sqlhelpers.listify(self.except_tables)
        self.tables = list(self.photodb.sql_select(query))

        query = 'SELECT name, sql FROM sqlite_master WHERE type == "index" AND name NOT LIKE "sqlite_%"'
        self.indices = list(self.photodb.sql_select(query))

    def __exit__(self, exc_type, exc, exc_traceback):
        if exc:
            raise exc

        # This loop is split in two parts, because otherwise if table A
        # references table B and table A is completely reconstructed, it will
        # be pointing to the version of B which has not been reconstructed yet,
        # which is about to get renamed to B_old and then A's reference will be
        # broken.
        for (name, query) in self.tables:
            self.photodb.sql_execute(f'ALTER TABLE {name} RENAME TO {name}_old')

        for (name, query) in self.tables:
            self.photodb.sql_execute(query)
            self.photodb.sql_execute(f'INSERT INTO {name} SELECT * FROM {name}_old')
            self.photodb.sql_execute(f'DROP TABLE {name}_old')

        for (name, query) in self.indices:
            self.photodb.sql_execute(query)
        # self.photodb.sql_execute('REINDEX')

def upgrade_1_to_2(photodb):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    photodb.sql_executescript('''
    BEGIN;
    ALTER TABLE photos ADD COLUMN tagged_at INT;
    ''')

def upgrade_2_to_3(photodb):
    '''
    Preliminary support for user account management was added. This includes a `users` table
    with id, username, password hash, and a timestamp.
    Plus some indices.
    '''
    photodb.sql_executescript('''
    BEGIN;

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
    photodb.sql_executescript('''
    BEGIN;

    ALTER TABLE photos ADD COLUMN author_id TEXT;

    CREATE INDEX IF NOT EXISTS index_photo_author ON photos(author_id);
    ''')

def upgrade_4_to_5(photodb):
    '''
    Add table `bookmarks` and its indices.
    '''
    photodb.sql_executescript('''
    BEGIN;

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
    photodb.sql_execute('BEGIN')
    # 1. Start the id_numbers.albums value at the tags value so that the number
    # can continue to increment safely and separately, instead of starting at
    # zero and bumping into existing albums.
    last_id = photodb.sql_select_one('SELECT last_id FROM id_numbers WHERE tab == "tags"')[0]
    photodb.sql_execute('INSERT INTO id_numbers VALUES("albums", ?)', [last_id])

    # 2. Now's a good chance to rename 'index_grouprel' to 'index_taggroup'.
    photodb.sql_executescript('''
    DROP INDEX IF EXISTS index_grouprel_parentid;
    DROP INDEX IF EXISTS index_grouprel_memberid;
    CREATE INDEX index_taggroup_parentid ON tag_group_rel(parentid);
    CREATE INDEX index_taggroup_memberid ON tag_group_rel(memberid);
    ''')

    # 3. All of the album group relationships need to be moved into their
    # own table, out of tag_group_rel
    photodb.sql_executescript('''
    CREATE TABLE album_group_rel(parentid TEXT, memberid TEXT);
    CREATE INDEX index_albumgroup_parentid ON album_group_rel(parentid);
    CREATE INDEX index_albumgroup_memberid ON album_group_rel(memberid);
    ''')

    album_ids = [id for (id,) in photodb.sql_select('SELECT id FROM albums')]
    for album_id in album_ids:
        query = 'SELECT * FROM tag_group_rel WHERE parentid == ? OR memberid == ?'
        bindings = [album_id, album_id]
        grouprels = list(photodb.sql_select(query, bindings))

        if not grouprels:
            continue

        for grouprel in grouprels:
            photodb.sql_execute('INSERT INTO album_group_rel VALUES(?, ?)', grouprel)

        query = 'DELETE FROM tag_group_rel WHERE parentid == ? OR memberid == ?'
        bindings = [album_id, album_id]
        photodb.sql_execute(query, bindings)

def upgrade_6_to_7(photodb):
    '''
    Albums lost their `associated_directory` column, and it has been moved to a
    separate table `album_associated_directories`, so that we can have albums
    which load from multiple directories.

    Most of the indices were renamed.
    '''
    photodb.sql_execute('BEGIN')
    indices = photodb.sql_select('SELECT name FROM sqlite_master WHERE type == "index" AND name NOT LIKE "sqlite_%"')
    indices = [name for (name,) in indices]
    for index in indices:
        photodb.sql_execute(f'DROP INDEX {index}')

    with Regenerator(photodb, except_tables='albums'):
        photodb.sql_executescript('''
        CREATE TABLE album_associated_directories(
            albumid TEXT,
            directory TEXT COLLATE NOCASE
        );

        ALTER TABLE albums RENAME TO deleting_albums;

        CREATE TABLE albums(
            id TEXT,
            title TEXT,
            description TEXT
        );

        INSERT INTO albums SELECT
            id,
            title,
            description
        FROM deleting_albums;

        INSERT INTO album_associated_directories SELECT
            id,
            associated_directory
        FROM deleting_albums
        WHERE associated_directory IS NOT NULL;

        DROP TABLE deleting_albums;

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
    photodb.sql_executescript('''
    BEGIN;
    ALTER TABLE tags ADD COLUMN description TEXT;
    ''')

def upgrade_8_to_9(photodb):
    '''
    Give the Photos table a searchhidden field.
    '''
    photodb.sql_executescript('''
    BEGIN;

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
    photodb.sql_execute('BEGIN')
    photos = list(photodb.search(has_thumbnail=True, is_searchhidden=None, yield_albums=False))

    # Since we're doing it all at once, I'm going to cheat and skip the
    # relative_to() calculation.
    thumbnail_dir = photodb.thumbnail_directory.absolute_path
    for photo in photos:
        new_thumbnail_path = photo.make_thumbnail_filepath()
        new_thumbnail_path = new_thumbnail_path.absolute_path
        new_thumbnail_path = '.' + new_thumbnail_path.replace(thumbnail_dir, '')
        photodb.sql_execute(
            'UPDATE photos SET thumbnail = ? WHERE id == ?',
            [new_thumbnail_path, photo.id]
        )

def upgrade_10_to_11(photodb):
    '''
    Added Primary keys, Foreign keys, and NOT NULL constraints.
    Added author_id column to Album and Tag tables.
    '''
    with Regenerator(photodb, except_tables=['albums', 'tags']):
        photodb.sql_executescript('''
        PRAGMA foreign_keys = OFF;
        BEGIN;

        ALTER TABLE albums RENAME TO albums_old;

        CREATE TABLE albums(
            id TEXT PRIMARY KEY NOT NULL,
            title TEXT,
            description TEXT,
            author_id TEXT,
            FOREIGN KEY(author_id) REFERENCES users(id)
        );

        INSERT INTO albums SELECT
            id,
            title,
            description,
            NULL
        FROM albums_old;

        DROP TABLE albums_old;

        ALTER_TABLE tags RENAME TO tags_old;

        CREATE TABLE tags(
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            author_id TEXT,
            FOREIGN KEY(author_id) REFERENCES users(id)
        );

        INSERT INTO tags SELECT
            id,
            name,
            description,
            NULL
        FROM tags_old;

        DROP TABLE tags_old;
        ''')

def upgrade_11_to_12(photodb):
    '''
    Added multicolumn (photoid, tagid) index to the photo_tag_rel table to
    improve the speed of individual relation searching, important for the
    new intersection-based search.
    '''
    photodb.sql_executescript('''
    BEGIN;

    CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid_tagid on photo_tag_rel(photoid, tagid);
    ''')

def upgrade_12_to_13(photodb):
    '''
    Added display_name column to the User table.
    '''
    with Regenerator(photodb, except_tables='users'):
        photodb.sql_executescript('''
        PRAGMA foreign_keys = OFF;

        BEGIN;

        ALTER TABLE users RENAME TO users_old;

        CREATE TABLE users(
            id TEXT PRIMARY KEY NOT NULL,
            username TEXT NOT NULL COLLATE NOCASE,
            password BLOB NOT NULL,
            display_name TEXT,
            created INT
        );

        INSERT INTO users SELECT
            id,
            username,
            password,
            NULL,
            created
        FROM users_old;

        DROP TABLE users_old;
        ''')

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
    with Regenerator(photodb, except_tables='photos'):
        photodb.sql_executescript('''
        PRAGMA foreign_keys = OFF;

        BEGIN;

        ALTER TABLE photos RENAME TO photos_old;

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

        DROP TABLE photos_old;

        CREATE INDEX index_photos_dev_ino ON photos(dev_ino);
        ''')

    for photo in photodb.get_photos_by_recent():
        if not photo.real_path.is_file:
            continue
        stat = photo.real_path.stat
        (dev, ino) = (stat.st_dev, stat.st_ino)
        if dev == 0 or ino == 0:
            continue
        dev_ino = f'{dev},{ino}'
        photodb.sql_execute('UPDATE photos SET dev_ino = ? WHERE id == ?', [dev_ino, photo.id])

def upgrade_15_to_16(photodb):
    '''
    Added the basename column to photos. Added collate nocase to extension.
    '''
    with Regenerator(photodb, except_tables='photos'):
        photodb.sql_executescript('''
        PRAGMA foreign_keys = OFF;

        BEGIN;

        ALTER TABLE photos RENAME TO photos_old;

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

        DROP TABLE photos_old;
        ''')

    for (id, filepath) in photodb.sql_select('SELECT id, filepath FROM photos'):
        basename = os.path.basename(filepath)
        photodb.sql_execute('UPDATE photos SET basename = ? WHERE id == ?', [basename, id])

def upgrade_all(data_directory):
    '''
    Given the directory containing a phototagger database, apply all of the
    needed upgrade_x_to_y functions in order.
    '''
    photodb = etiquette.photodb.PhotoDB(data_directory, create=False, skip_version_check=True)

    current_version = photodb.sql_execute('PRAGMA user_version').fetchone()[0]
    needed_version = etiquette.constants.DATABASE_VERSION

    if current_version == needed_version:
        print('Already up to date with version %d.' % needed_version)
        return

    for version_number in range(current_version + 1, needed_version + 1):
        print('Upgrading from %d to %d.' % (current_version, version_number))
        upgrade_function = 'upgrade_%d_to_%d' % (current_version, version_number)
        upgrade_function = eval(upgrade_function)

        try:
            photodb.sql_execute('PRAGMA foreign_keys = ON')
            upgrade_function(photodb)
        except Exception as exc:
            photodb.rollback()
            raise
        else:
            photodb.sql.cursor().execute('PRAGMA user_version = %d' % version_number)
            photodb.commit()

        current_version = version_number
    print('Upgrades finished.')

def upgrade_all_argparse(args):
    return upgrade_all(data_directory=args.data_directory)

def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('data_directory')
    parser.set_defaults(func=upgrade_all_argparse)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
