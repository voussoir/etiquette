import argparse
import os
import sqlite3
import sys

import etiquette

def upgrade_1_to_2(photodb):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    cur = photodb.sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN tagged_at INT')

def upgrade_2_to_3(photodb):
    '''
    Preliminary support for user account management was added. This includes a `user` table
    with id, username, password hash, and a timestamp.
    Plus some indices.
    '''
    cur = photodb.sql.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id TEXT,
        username TEXT COLLATE NOCASE,
        password BLOB,
        created INT
    )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS index_user_id ON users(id)')
    cur.execute('CREATE INDEX IF NOT EXISTS index_user_username ON users(username COLLATE NOCASE)')

def upgrade_3_to_4(photodb):
    '''
    Add an `author_id` column to Photos.
    '''
    cur = photodb.sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN author_id TEXT')
    cur.execute('CREATE INDEX IF NOT EXISTS index_photo_author ON photos(author_id)')

def upgrade_4_to_5(photodb):
    '''
    Add table `bookmarks` and its indices.
    '''
    cur = photodb.sql.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS bookmarks(
        id TEXT,
        title TEXT,
        url TEXT,
        author_id TEXT
    )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS index_bookmark_id ON bookmarks(id)')
    cur.execute('CREATE INDEX IF NOT EXISTS index_bookmark_author ON bookmarks(author_id)')

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
    # 1. Start the id_numbers.albums value at the tags value so that the number
    # can continue to increment safely and separately, instead of starting at
    # zero and bumping into existing albums.
    cur = photodb.sql.cursor()
    cur.execute('SELECT * FROM id_numbers WHERE tab == "tags"')
    last_id = cur.fetchone()[1]
    cur.execute('INSERT INTO id_numbers VALUES("albums", ?)', [last_id])

    # 2. Now's a good chance to rename 'index_grouprel' to 'index_taggroup'.
    cur.execute('DROP INDEX index_grouprel_parentid')
    cur.execute('DROP INDEX index_grouprel_memberid')
    cur.execute('CREATE INDEX index_taggroup_parentid ON tag_group_rel(parentid)')
    cur.execute('CREATE INDEX index_taggroup_memberid ON tag_group_rel(memberid)')

    # 3. All of the album group relationships need to be moved into their
    # own table, out of tag_group_rel
    cur.execute('CREATE TABLE album_group_rel(parentid TEXT, memberid TEXT)')
    cur.execute('CREATE INDEX index_albumgroup_parentid ON album_group_rel(parentid)')
    cur.execute('CREATE INDEX index_albumgroup_memberid ON album_group_rel(memberid)')
    cur.execute('SELECT id FROM albums')
    album_ids = [f[0] for f in cur.fetchall()]
    for album_id in album_ids:
        cur.execute(
            'SELECT * FROM tag_group_rel WHERE parentid == ? OR memberid == ?',
            [album_id, album_id]
        )
        f = cur.fetchall()
        if f == []:
            continue
        for grouprel in f:
            cur.execute('INSERT INTO album_group_rel VALUES(?, ?)', grouprel)
        cur.execute(
            'DELETE FROM tag_group_rel WHERE parentid == ? OR memberid == ?',
            [album_id, album_id]
        )

def upgrade_6_to_7(photodb):
    '''
    Most of the indices were renamed, so delete them and let them regenerate
    next time.

    Albums lost their `associated_directory` column, and it has been moved to a
    separate table `album_associated_directories`, so that we can have albums
    which load from multiple directories.
    '''
    cur = photodb.sql.cursor()
    cur.execute('SELECT name FROM sqlite_master WHERE type == "index"')
    indices = [x[0] for x in cur.fetchall()]
    for index in indices:
        cur.execute('DROP INDEX %s' % index)

    cur.execute('''
    CREATE TABLE album_associated_directories(
        albumid TEXT,
        directory TEXT COLLATE NOCASE
    )''')
    cur.execute('ALTER TABLE albums RENAME TO deleting_albums')
    cur.execute('''
    CREATE TABLE albums(
        id TEXT,
        title TEXT,
        description TEXT
    )''')
    cur.execute('INSERT INTO albums SELECT id, title, description FROM deleting_albums')
    cur.execute('''
    INSERT INTO album_associated_directories
    SELECT id, associated_directory
    FROM deleting_albums
    WHERE associated_directory IS NOT NULL
    ''')
    cur.execute('DROP TABLE deleting_albums')

def upgrade_7_to_8(photodb):
    '''
    Give the Tags table a description field.
    '''
    cur = photodb.sql.cursor()
    cur.execute('ALTER TABLE tags ADD COLUMN description TEXT')

def upgrade_8_to_9(photodb):
    '''
    Give the Photos table a searchhidden field.
    '''
    cur = photodb.sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN searchhidden INT')
    cur.execute('UPDATE photos SET searchhidden = 0')
    cur.execute('CREATE INDEX index_photos_searchhidden on photos(searchhidden)')

def upgrade_9_to_10(photodb):
    '''
    From now on, the filepath stored in Photo's thumbnail column should be a
    relative path where . is the PhotoDB's thumbnail_directory.
    Previously, the stored path was unnecessarily high and contained the PDB's
    data_directory, reducing portability.
    '''
    cur = photodb.sql.cursor()
    photos = list(photodb.search(has_thumbnail=True, is_searchhidden=None))

    # Since we're doing it all at once, I'm going to cheat and skip the
    # relative_to() calculation.
    thumbnail_dir = photodb.thumbnail_directory.absolute_path
    for photo in photos:
        new_thumbnail_path = photo.make_thumbnail_filepath()
        new_thumbnail_path = new_thumbnail_path.absolute_path
        new_thumbnail_path = '.' + new_thumbnail_path.replace(thumbnail_dir, '')
        cur.execute('UPDATE photos SET thumbnail = ? WHERE id == ?', [new_thumbnail_path, photo.id])

def upgrade_all(data_directory):
    '''
    Given the directory containing a phototagger database, apply all of the
    needed upgrade_x_to_y functions in order.
    '''
    photodb = etiquette.photodb.PhotoDB(data_directory, create=False, skip_version_check=True)

    cur = photodb.sql.cursor()

    cur.execute('PRAGMA user_version')
    current_version = cur.fetchone()[0]
    needed_version = etiquette.constants.DATABASE_VERSION

    if current_version == needed_version:
        print('Already up-to-date with version %d.' % needed_version)
        return

    for version_number in range(current_version + 1, needed_version + 1):
        print('Upgrading from %d to %d' % (current_version, version_number))
        upgrade_function = 'upgrade_%d_to_%d' % (current_version, version_number)
        upgrade_function = eval(upgrade_function)
        upgrade_function(photodb)
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
    args.func(args)

if __name__ == '__main__':
    main(sys.argv[1:])
