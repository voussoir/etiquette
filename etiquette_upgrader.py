import argparse
import os
import sqlite3
import sys

import phototagger

def upgrade_1_to_2(sql):
    '''
    In this version, a column `tagged_at` was added to the Photos table, to keep
    track of the last time the photo's tags were edited (added or removed).
    '''
    cur = sql.cursor()
    cur.execute('ALTER TABLE photos ADD COLUMN tagged_at INT')


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
    needed_version = phototagger.DATABASE_VERSION

    if current_version == needed_version:
        print('Already up-to-date.')
        return

    for version_number in range(current_version + 1, needed_version + 1):
        print('Upgrading from %d to %d' % (current_version, version_number))
        upgrade_function = 'upgrade_%d_to_%d' % (current_version, version_number)
        upgrade_function = eval(upgrade_function)
        upgrade_function(sql)
        sql.cursor().execute('PRAGMA user_version = 2')
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
