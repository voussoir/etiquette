import argparse
import sys

import etiquette

import old_inits

def upgrade_1_to_2(photodb):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('ALTER TABLE photos ADD COLUMN tagged_at INT')

def upgrade_2_to_3(photodb):
    '''
    Preliminary support for user account management was added. This includes a `user` table
    with id, username, password hash, and a timestamp.
    Plus some indices.
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('''
    CREATE TABLE IF NOT EXISTS users(
        id TEXT,
        username TEXT COLLATE NOCASE,
        password BLOB,
        created INT
    )
    ''')
    photodb.sql_execute('CREATE INDEX IF NOT EXISTS index_user_id ON users(id)')
    photodb.sql_execute('CREATE INDEX IF NOT EXISTS index_user_username ON users(username COLLATE NOCASE)')

def upgrade_3_to_4(photodb):
    '''
    Add an `author_id` column to Photos.
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('ALTER TABLE photos ADD COLUMN author_id TEXT')
    photodb.sql_execute('CREATE INDEX IF NOT EXISTS index_photo_author ON photos(author_id)')

def upgrade_4_to_5(photodb):
    '''
    Add table `bookmarks` and its indices.
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('''
    CREATE TABLE IF NOT EXISTS bookmarks(
        id TEXT,
        title TEXT,
        url TEXT,
        author_id TEXT
    )
    ''')
    photodb.sql_execute('CREATE INDEX IF NOT EXISTS index_bookmark_id ON bookmarks(id)')
    photodb.sql_execute('CREATE INDEX IF NOT EXISTS index_bookmark_author ON bookmarks(author_id)')

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
    photodb.sql_execute('DROP INDEX IF EXISTS index_grouprel_parentid')
    photodb.sql_execute('DROP INDEX IF EXISTS index_grouprel_memberid')
    photodb.sql_execute('CREATE INDEX index_taggroup_parentid ON tag_group_rel(parentid)')
    photodb.sql_execute('CREATE INDEX index_taggroup_memberid ON tag_group_rel(memberid)')

    # 3. All of the album group relationships need to be moved into their
    # own table, out of tag_group_rel
    photodb.sql_execute('CREATE TABLE album_group_rel(parentid TEXT, memberid TEXT)')
    photodb.sql_execute('CREATE INDEX index_albumgroup_parentid ON album_group_rel(parentid)')
    photodb.sql_execute('CREATE INDEX index_albumgroup_memberid ON album_group_rel(memberid)')

    album_ids = [row[0] for row in photodb.sql_select('SELECT id FROM albums')]
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
    Most of the indices were renamed, so delete them and let them regenerate
    next time.

    Albums lost their `associated_directory` column, and it has been moved to a
    separate table `album_associated_directories`, so that we can have albums
    which load from multiple directories.
    '''
    photodb.sql_execute('BEGIN')
    indices = photodb.sql_select('SELECT name FROM sqlite_master WHERE type == "index"')
    indices = [x[0] for x in indices]
    for index in indices:
        photodb.sql_execute('DROP INDEX %s' % index)

    photodb.sql_execute('''
    CREATE TABLE album_associated_directories(
        albumid TEXT,
        directory TEXT COLLATE NOCASE
    )''')
    photodb.sql_execute('ALTER TABLE albums RENAME TO deleting_albums')
    photodb.sql_execute('''
    CREATE TABLE albums(
        id TEXT,
        title TEXT,
        description TEXT
    )''')
    photodb.sql_execute('INSERT INTO albums SELECT id, title, description FROM deleting_albums')
    photodb.sql_execute('''
    INSERT INTO album_associated_directories
    SELECT id, associated_directory
    FROM deleting_albums
    WHERE associated_directory IS NOT NULL
    ''')
    photodb.sql_execute('DROP TABLE deleting_albums')

def upgrade_7_to_8(photodb):
    '''
    Give the Tags table a description field.
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('ALTER TABLE tags ADD COLUMN description TEXT')

def upgrade_8_to_9(photodb):
    '''
    Give the Photos table a searchhidden field.
    '''
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('ALTER TABLE photos ADD COLUMN searchhidden INT')
    photodb.sql_execute('UPDATE photos SET searchhidden = 0')
    photodb.sql_execute('CREATE INDEX index_photos_searchhidden on photos(searchhidden)')

def upgrade_9_to_10(photodb):
    '''
    From now on, the filepath stored in Photo's thumbnail column should be a
    relative path where . is the PhotoDB's thumbnail_directory.
    Previously, the stored path was unnecessarily high and contained the PDB's
    data_directory, reducing portability.
    '''
    photodb.sql_execute('BEGIN')
    photos = list(photodb.search(has_thumbnail=True, is_searchhidden=None))

    # Since we're doing it all at once, I'm going to cheat and skip the
    # relative_to() calculation.
    thumbnail_dir = photodb.thumbnail_directory.absolute_path
    for photo in photos:
        new_thumbnail_path = photo.make_thumbnail_filepath()
        new_thumbnail_path = new_thumbnail_path.absolute_path
        new_thumbnail_path = '.' + new_thumbnail_path.replace(thumbnail_dir, '')
        photodb.sql_execute('UPDATE photos SET thumbnail = ? WHERE id == ?', [new_thumbnail_path, photo.id])

def upgrade_10_to_11(photodb):
    '''
    Added Primary keys, Foreign keys, and NOT NULL constraints.
    Added author_id column to Album and Tag tables.
    '''
    photodb.sql_execute('PRAGMA foreign_keys = OFF')
    photodb.sql_execute('BEGIN')

    tables_to_copy = {
        'users': '*',
        'albums': '*, NULL',
        'bookmarks': '*',
        'photos': '*',
        'tags': '*, NULL',
        'album_associated_directories': '*',
        'album_group_rel': '*',
        'album_photo_rel': '*',
        'id_numbers': '*',
        'photo_tag_rel': '*',
        'tag_group_rel': '*',
        'tag_synonyms': '*',
    }
    print('Renaming existing tables.')
    for table in tables_to_copy:
        statement = 'ALTER TABLE %s RENAME TO %s_old' % (table, table)
        photodb.sql_execute(statement)

    lines = [line.strip() for line in old_inits.V11.splitlines()]
    lines = [line for line in lines if not line.startswith('--')]
    statements = '\n'.join(lines).split(';')
    statements = [x.strip() for x in statements]
    create_tables = [x for x in statements if x.lower().startswith('create table')]
    create_indices = [x for x in statements if x.lower().startswith('create index')]

    print('Recreating tables.')
    for statement in create_tables:
        photodb.sql_execute(statement)

    print('Migrating table data.')
    for (table, select_columns) in tables_to_copy.items():
        statement = 'INSERT INTO %s SELECT %s FROM %s_old' % (table, select_columns, table)
        photodb.sql_execute(statement)
        statement = 'DROP TABLE %s_old' % table
        photodb.sql_execute(statement)

    print('Recreating indices.')
    for statement in create_indices:
        photodb.sql_execute(statement)

def upgrade_11_to_12(photodb):
    '''
    Added multicolumn (photoid, tagid) index to the photo_tag_rel table to
    improve the speed of individual relation searching, important for the
    new intersection-based search.
    '''
    photodb.sql_execute('BEGIN')
    query = '''
    CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid_tagid on photo_tag_rel(photoid, tagid)
    '''
    photodb.sql_execute(query)

def upgrade_12_to_13(photodb):
    '''
    Added display_name column to the User table.
    '''
    photodb.sql_execute('PRAGMA foreign_keys = OFF')
    photodb.sql_execute('BEGIN')
    photodb.sql_execute('ALTER TABLE users RENAME TO users_old')
    photodb.sql_execute('''
    CREATE TABLE users(
        id TEXT PRIMARY KEY NOT NULL,
        username TEXT NOT NULL COLLATE NOCASE,
        password BLOB NOT NULL,
        display_name TEXT,
        created INT
    )''')
    photodb.sql_execute('INSERT INTO users SELECT id, username, password, NULL, created FROM users_old')
    photodb.sql_execute('DROP TABLE users_old')

def upgrade_13_to_14(photodb):
    '''
    Rename user.min_length to min_username_length.
    '''
    photodb.sql_execute('BEGIN')
    photodb.config['user']['min_username_length'] = photodb.config['user'].pop('min_length')
    photodb.config['user']['max_username_length'] = photodb.config['user'].pop('max_length')
    photodb.save_config()

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
