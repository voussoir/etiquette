import converter
import logging
import string
import traceback

try:
    ffmpeg = converter.Converter(
        ffmpeg_path='D:\\software\\ffmpeg\\bin\\ffmpeg.exe',
        ffprobe_path='D:\\software\\ffmpeg\\bin\\ffprobe.exe',
    )
except converter.ffmpeg.FFMpegError:
    traceback.print_exc()
    ffmpeg = None

FILENAME_BADCHARS = '\\/:*?<>|"'

# Note: Setting user_version pragma in init sequence is safe because it only
# happens after the out-of-date check occurs, so no chance of accidentally
# overwriting it.
DATABASE_VERSION = 8
DB_INIT = '''
PRAGMA count_changes = OFF;
PRAGMA cache_size = 10000;
PRAGMA user_version = {user_version};

----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_associated_directories(
    albumid TEXT,
    directory TEXT COLLATE NOCASE
);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
    album_associated_directories(albumid);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
    album_associated_directories(directory);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_group_rel(
    parentid TEXT,
    memberid TEXT
);
CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid TEXT,
    photoid TEXT
);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS albums(
    id TEXT,
    title TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks(
    id TEXT,
    title TEXT,
    url TEXT,
    author_id TEXT
);
CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
CREATE INDEX IF NOT EXISTS index_bookmarks_author on bookmarks(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_numbers(
    tab TEXT,
    last_id TEXT
);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid TEXT,
    tagid TEXT
);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photos(
    id TEXT,
    filepath TEXT COLLATE NOCASE,
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
    author_id TEXT
);
CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_override_filename on
    photos(override_filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid TEXT,
    memberid TEXT
);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT,
    mastername TEXT
);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags(
    id TEXT,
    name TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users(
    id TEXT,
    username TEXT COLLATE NOCASE,
    password BLOB,
    created INT
);
CREATE INDEX IF NOT EXISTS index_users_id on users(id);
CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
'''.format(user_version=DATABASE_VERSION)

SQL_COLUMNS = {}
for statement in DB_INIT.split(';'):
    if 'create table' not in statement.lower():
        continue

    table_name = statement.split('(')[0].strip().split(' ')[-1]
    column_names = statement.split('(')[1].rsplit(')', 1)[0]
    column_names = column_names.split(',')
    column_names = [x.strip().split(' ')[0] for x in column_names]
    SQL_COLUMNS[table_name] = column_names

_sql_dictify = lambda columns: {key:index for (index, key) in enumerate(columns)}
SQL_INDEX = {key: _sql_dictify(value) for (key, value) in SQL_COLUMNS.items()}

def _extract_column_names(table):
    statement = DB_INIT.split('CREATE TABLE IF NOT EXISTS %s(' % table)[1]
    statement = statement.split(');')[0]
    statement = statement.replace('\n', ' ')
    columns = statement.split(',')
    columns = [column.strip().split(' ')[0] for column in columns]
    return columns

SQL_LASTID_COLUMNS = _extract_column_names('id_numbers')
SQL_ALBUM_DIRECTORY_COLUMNS = _extract_column_names('album_associated_directories')
SQL_ALBUM_COLUMNS = _extract_column_names('albums')
SQL_BOOKMARK_COLUMNS = _extract_column_names('bookmarks')
SQL_PHOTO_COLUMNS = _extract_column_names('photos')
SQL_TAG_COLUMNS = _extract_column_names('tags')
SQL_SYN_COLUMNS = _extract_column_names('tag_synonyms')
SQL_ALBUMGROUP_COLUMNS = _extract_column_names('album_group_rel')
SQL_ALBUMPHOTO_COLUMNS = _extract_column_names('album_photo_rel')
SQL_PHOTOTAG_COLUMNS = _extract_column_names('photo_tag_rel')
SQL_TAGGROUP_COLUMNS = _extract_column_names('tag_group_rel')
SQL_USER_COLUMNS = _extract_column_names('users')

SQL_ALBUM = _sql_dictify(SQL_ALBUM_COLUMNS)
SQL_ALBUM_DIRECTORY = _sql_dictify(SQL_ALBUM_DIRECTORY_COLUMNS)
SQL_ALBUMGROUP = _sql_dictify(SQL_ALBUMGROUP_COLUMNS)
SQL_BOOKMARK = _sql_dictify(SQL_BOOKMARK_COLUMNS)
SQL_ALBUMPHOTO = _sql_dictify(SQL_ALBUMPHOTO_COLUMNS)
SQL_LASTID = _sql_dictify(SQL_LASTID_COLUMNS)
SQL_PHOTO = _sql_dictify(SQL_PHOTO_COLUMNS)
SQL_PHOTOTAG = _sql_dictify(SQL_PHOTOTAG_COLUMNS)
SQL_SYN = _sql_dictify(SQL_SYN_COLUMNS)
SQL_TAG = _sql_dictify(SQL_TAG_COLUMNS)
SQL_TAGGROUP = _sql_dictify(SQL_TAGGROUP_COLUMNS)
SQL_USER = _sql_dictify(SQL_USER_COLUMNS)

ALLOWED_ORDERBY_COLUMNS = [
    'extension',
    'width',
    'height',
    'ratio',
    'area',
    'duration',
    'bytes',
    'created',
    'tagged_at',
    'random',
]


# Errors and warnings
WARNING_MINMAX_INVALID = 'Field "{field}": "{value}" is not a valid request. Ignored.'
WARNING_ORDERBY_INVALID = 'Invalid orderby request "{request}". Ignored.'
WARNING_ORDERBY_BADCOL = '"{column}" is not a sorting option. Ignored.'
WARNING_ORDERBY_BADDIRECTION = '''
You can\'t order "{column}" by "{direction}". Defaulting to descending.
'''

# Operational info
TRUTHYSTRING_TRUE = {s.lower() for s in ('1', 'true', 't', 'yes', 'y', 'on')}
TRUTHYSTRING_NONE = {s.lower() for s in ('null', 'none')}

ADDITIONAL_MIMETYPES = {
    '7z': 'archive',
    'gz': 'archive',
    'rar': 'archive',

    'aac': 'audio/aac',
    'ac3': 'audio/ac3',
    'dts': 'audio/dts',
    'm4a': 'audio/mp4',
    'opus': 'audio/ogg',

    'mkv': 'video/x-matroska',

    'ass': 'text/plain',
    'nfo': 'text/plain',
    'srt': 'text/plain',
}

DEFAULT_DATADIR = '.\\_etiquette'
DEFAULT_DBNAME = 'phototagger.db'
DEFAULT_CONFIGNAME = 'config.json'
DEFAULT_THUMBDIR = 'site_thumbnails'

DEFAULT_CONFIGURATION = {
    'log_level': logging.DEBUG,

    'cache_size': {
        'album': 1000,
        'bookmark': 100,
        'photo': 100000,
        'tag': 1000,
        'user': 200,
    },

    'enable_feature': {
        'album': {
            'edit': True,
            'new': True,
        },
        'bookmark': {
            'edit': True,
            'new': True,
        },
        'photo': {
            'add_remove_tag': True,
            'new': True,
            'edit': True,
            'generate_thumbnail': True,
            'reload_metadata': True,
        },
        'tag': {
            'edit': True,
            'new': True,
        },
        'user': {
            'login': True,
            'new': True,
        },
    },

    'tag': {
        'min_length': 1,
        'max_length': 32,
        'valid_chars': string.ascii_lowercase + string.digits + '_()',
    },

    'user': {
        'min_length': 2,
        'min_password_length': 6,
        'max_length': 24,
        'valid_chars': string.ascii_letters + string.digits + '~!@#$%^*()[]{}:;,.<>/\\-_+=',
    },

    'digest_exclude_files': [
        'phototagger.db',
        'desktop.ini',
        'thumbs.db',
    ],
    'digest_exclude_dirs': [
        '_site_thumbnails',
    ],

    'file_read_chunk': 2 ** 20,
    'id_length': 12,
    'thumbnail_width': 400,
    'thumbnail_height': 400,

    'motd_strings': [
        'Good morning, Paul. What will your first sequence of the day be?',
    ],
}
