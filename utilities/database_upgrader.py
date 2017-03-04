import argparse
import os
import sqlite3
import sys

import etiquette.photodb

def upgrade_1_to_2(sql):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    cur = sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN tagged_at INT')

def upgrade_2_to_3(sql):
    '''
    Preliminary support for user account management was added. This includes a `user` table
    with id, username, password hash, and a timestamp.
    Plus some indices.
    '''
    cur = sql.cursor()
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

def upgrade_3_to_4(sql):
    '''
    Add an `author_id` column to Photos.
    '''
    cur = sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN author_id TEXT')
    cur.execute('CREATE INDEX IF NOT EXISTS index_photo_author ON photos(author_id)')

def upgrade_4_to_5(sql):
    '''
    Add table `bookmarks` and its indices.
    '''
    cur = sql.cursor()
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

def upgrade_5_to_6(sql):
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
    cur = sql.cursor()
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
    cur.execute('CREATE INDEX index_albumgroup_parentid ON tag_group_rel(parentid)')
    cur.execute('CREATE INDEX index_albumgroup_memberid ON tag_group_rel(memberid)')
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

def upgrade_all(database_filename):
    '''
    Given the filename of a phototagger database, apply all of the needed
    upgrade_x_to_y functions in order.
    '''
    if not os.path.isfile(database_filename):
        raise FileNotFoundError(database_filename)

    sql = sqlite3.connect(database_filename)
    cur = sql.cursor()

    cur.execute('PRAGMA user_version')
    current_version = cur.fetchone()[0]
    needed_version = etiquette.photodb.DATABASE_VERSION

    if current_version == needed_version:
        print('Already up-to-date with version %d.' % needed_version)
        return

    for version_number in range(current_version + 1, needed_version + 1):
        print('Upgrading from %d to %d' % (current_version, version_number))
        upgrade_function = 'upgrade_%d_to_%d' % (current_version, version_number)
        upgrade_function = eval(upgrade_function)
        upgrade_function(sql)
        sql.cursor().execute('PRAGMA user_version = %d' % version_number)
        sql.commit()
        current_version = version_number
    print('Upgrades finished.')


def upgrade_all_argparse(args):
    return upgrade_all(database_filename=args.database_filename)

def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('database_filename')
    parser.set_defaults(func=upgrade_all_argparse)

    args = parser.parse_args(argv)
    args.func(args)

if __name__ == '__main__':
    main(sys.argv[1:])
