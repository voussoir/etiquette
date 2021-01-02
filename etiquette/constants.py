'''
This file provides data and objects that do not change throughout the runtime.
'''
import converter
import string
import traceback
import warnings

from voussoirkit import sqlhelpers
from voussoirkit import winwhich

# FFmpeg ###########################################################################################

FFMPEG_NOT_FOUND = '''
ffmpeg or ffprobe not found.
Add them to your PATH or use symlinks such that they appear in:
Linux: which ffmpeg & which ffprobe
Windows: where ffmpeg & where ffprobe
'''

def _load_ffmpeg():
    ffmpeg_path = winwhich.which('ffmpeg')
    ffprobe_path = winwhich.which('ffprobe')

    if (not ffmpeg_path) or (not ffprobe_path):
        warnings.warn(FFMPEG_NOT_FOUND)
        return None

    try:
        ffmpeg = converter.Converter(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
        )
    except converter.ffmpeg.FFMpegError:
        traceback.print_exc()
        return None

    return ffmpeg

ffmpeg = _load_ffmpeg()

# Database #########################################################################################

DATABASE_VERSION = 16
DB_VERSION_PRAGMA = f'''
PRAGMA user_version = {DATABASE_VERSION};
'''

DB_PRAGMAS = f'''
PRAGMA cache_size = 10000;
PRAGMA count_changes = OFF;
PRAGMA foreign_keys = ON;
'''

DB_INIT = f'''
BEGIN;
{DB_PRAGMAS}
{DB_VERSION_PRAGMA}
----------------------------------------------------------------------------------------------------
-- users table is defined first because other tables have foreign keys here.
CREATE TABLE IF NOT EXISTS users(
    id TEXT PRIMARY KEY NOT NULL,
    username TEXT NOT NULL COLLATE NOCASE,
    password BLOB NOT NULL,
    display_name TEXT,
    created INT
);
CREATE INDEX IF NOT EXISTS index_users_id on users(id);
CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS albums(
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    description TEXT,
    author_id TEXT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
CREATE INDEX IF NOT EXISTS index_albums_author_id on albums(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks(
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    url TEXT,
    author_id TEXT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
CREATE INDEX IF NOT EXISTS index_bookmarks_author_id on bookmarks(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photos(
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
CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_dev_ino on photos(dev_ino);
CREATE INDEX IF NOT EXISTS index_photos_override_filename on
    photos(override_filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
CREATE INDEX IF NOT EXISTS index_photos_searchhidden on photos(searchhidden);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags(
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    author_id TEXT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
CREATE INDEX IF NOT EXISTS index_tags_author_id on tags(author_id);
----------------------------------------------------------------------------------------------------

----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_associated_directories(
    albumid TEXT NOT NULL,
    directory TEXT NOT NULL COLLATE NOCASE,
    FOREIGN KEY(albumid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
    album_associated_directories(albumid);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
    album_associated_directories(directory);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_group_rel(
    parentid TEXT NOT NULL,
    memberid TEXT NOT NULL,
    FOREIGN KEY(parentid) REFERENCES albums(id),
    FOREIGN KEY(memberid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid TEXT NOT NULL,
    photoid TEXT NOT NULL,
    FOREIGN KEY(albumid) REFERENCES albums(id),
    FOREIGN KEY(photoid) REFERENCES photos(id)
);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_numbers(
    tab TEXT NOT NULL,
    last_id TEXT NOT NULL
);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid TEXT NOT NULL,
    tagid TEXT NOT NULL,
    FOREIGN KEY(photoid) REFERENCES photos(id),
    FOREIGN KEY(tagid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid_tagid on photo_tag_rel(photoid, tagid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid TEXT NOT NULL,
    memberid TEXT NOT NULL,
    FOREIGN KEY(parentid) REFERENCES tags(id),
    FOREIGN KEY(memberid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT NOT NULL,
    mastername TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
----------------------------------------------------------------------------------------------------
COMMIT;
'''

SQL_COLUMNS = sqlhelpers.extract_table_column_map(DB_INIT)
SQL_INDEX = sqlhelpers.reverse_table_column_map(SQL_COLUMNS)

ALLOWED_ORDERBY_COLUMNS = {
    'area',
    'basename',
    'bitrate',
    'bytes',
    'created',
    'duration',
    'extension',
    'height',
    'random',
    'ratio',
    'tagged_at',
    'width',
}

# Errors and warnings ##############################################################################

WARNING_MINMAX_INVALID = 'Field "{field}": "{value}" is not a valid request. Ignored.'
WARNING_ORDERBY_INVALID = 'Invalid orderby request "{request}". Ignored.'
WARNING_ORDERBY_BADCOL = '"{column}" is not a sorting option. Ignored.'
WARNING_ORDERBY_BADDIRECTION = '''
You can\'t order "{column}" by "{direction}". Defaulting to descending.
'''

# Janitorial stuff #################################################################################

FILENAME_BADCHARS = '\\/:*?<>|"'
TRUTHYSTRING_TRUE = {s.lower() for s in ('1', 'true', 't', 'yes', 'y', 'on')}
TRUTHYSTRING_NONE = {s.lower() for s in ('null', 'none')}

USER_ID_CHARACTERS = string.digits + string.ascii_uppercase

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
    'md': 'text/plain',
    'nfo': 'text/plain',
    'rst': 'text/plain',
    'srt': 'text/plain',
}

# Photodb ##########################################################################################

DEFAULT_DATADIR = '.\\_etiquette'
DEFAULT_DBNAME = 'phototagger.db'
DEFAULT_CONFIGNAME = 'config.json'
DEFAULT_THUMBDIR = 'site_thumbnails'

DEFAULT_CONFIGURATION = {
    'cache_size': {
        'album': 1000,
        'bookmark': 100,
        'photo': 100000,
        'tag': 10000,
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
            'edit': True,
            'login': True,
            'new': True,
        },
    },

    'tag': {
        'min_length': 1,
        'max_length': 32,
        # 'valid_chars': string.ascii_lowercase + string.digits + '_()',
    },

    'user': {
        'min_username_length': 2,
        'min_password_length': 6,
        'max_display_name_length': 24,
        'max_username_length': 24,
        'valid_chars': string.ascii_letters + string.digits + '_-',
    },

    'digest_exclude_files': [
        'phototagger.db',
        'desktop.ini',
        'thumbs.db',
    ],
    'digest_exclude_dirs': [
        '_etiquette',
        '_site_thumbnails',
        'site_thumbnails',
    ],

    'file_read_chunk': 2 ** 20,
    'id_length': 12,
    'thumbnail_width': 400,
    'thumbnail_height': 400,

    'recycle_instead_of_delete': True,

    'motd_strings': [
        'Good morning, Paul. What will your first sequence of the day be?',
    ],
}
