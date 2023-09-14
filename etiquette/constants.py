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
Linux: which ffmpeg ; which ffprobe
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

DATABASE_VERSION = 24

DB_INIT = '''
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
CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
CREATE INDEX IF NOT EXISTS index_albums_author_id on albums(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks(
    id INT PRIMARY KEY NOT NULL,
    title TEXT,
    url TEXT,
    created INT,
    author_id INT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
CREATE INDEX IF NOT EXISTS index_bookmarks_author_id on bookmarks(author_id);
----------------------------------------------------------------------------------------------------
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
    tagged_at INT,
    author_id INT,
    searchhidden BOOLEAN,
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
CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_basename on photos(basename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
CREATE INDEX IF NOT EXISTS index_photos_searchhidden_created on photos(searchhidden, created);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags(
    id INT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created INT,
    author_id INT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
CREATE INDEX IF NOT EXISTS index_tags_author_id on tags(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users(
    id INT PRIMARY KEY NOT NULL,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password BLOB NOT NULL,
    display_name TEXT,
    created INT
);
CREATE INDEX IF NOT EXISTS index_users_id on users(id);
CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
----------------------------------------------------------------------------------------------------

----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_associated_directories(
    albumid INT NOT NULL,
    directory TEXT NOT NULL COLLATE NOCASE,
    created INT,
    FOREIGN KEY(albumid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
    album_associated_directories(albumid);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
    album_associated_directories(directory);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_group_rel(
    parentid INT NOT NULL,
    memberid INT NOT NULL,
    created INT,
    PRIMARY KEY(parentid, memberid),
    FOREIGN KEY(parentid) REFERENCES albums(id),
    FOREIGN KEY(memberid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid INT NOT NULL,
    photoid INT NOT NULL,
    created INT,
    PRIMARY KEY(albumid, photoid),
    FOREIGN KEY(albumid) REFERENCES albums(id),
    FOREIGN KEY(photoid) REFERENCES photos(id)
);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid INT NOT NULL,
    tagid INT NOT NULL,
    created INT,
    PRIMARY KEY(photoid, tagid),
    FOREIGN KEY(photoid) REFERENCES photos(id),
    FOREIGN KEY(tagid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid_tagid on photo_tag_rel(photoid, tagid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_thumbnails(
    photoid INT PRIMARY KEY NOT NULL,
    thumbnail BLOB NOT NULL,
    created INT NOT NULL,
    FOREIGN KEY(photoid) REFERENCES photos(id)
);
CREATE INDEX IF NOT EXISTS index_photo_thumbnails_photoid on photo_thumbnails(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid INT NOT NULL,
    memberid INT NOT NULL,
    created INT,
    PRIMARY KEY(parentid, memberid),
    FOREIGN KEY(parentid) REFERENCES tags(id),
    FOREIGN KEY(memberid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT PRIMARY KEY NOT NULL,
    mastername TEXT NOT NULL,
    created INT
);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_mastername on tag_synonyms(mastername);
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
    'aspectratio',
    'tagged_at',
    'width',
}

# Janitorial stuff #################################################################################

FILENAME_BADCHARS = '\\/:*?<>|"'

MIMETYPES = {
    '7z': ('archive', '7z'),
    'gz': ('archive', 'gz'),
    'rar': ('archive', 'rar'),
    'tar': ('archive', 'tar'),
    'zip': ('archive', 'zip'),

    'aac': ('audio', 'aac'),
    'ac3': ('audio', 'ac3'),
    'aif': ('audio', 'x-aiff'),
    'aifc': ('audio', 'x-aiff'),
    'aiff': ('audio', 'x-aiff'),
    'au': ('audio', 'basic'),
    'dts': ('audio', 'dts'),
    'flac': ('audio', 'flac'),
    'm4a': ('audio', 'mp4'),
    'mp2': ('audio', 'mpeg'),
    'mp3': ('audio', 'mpeg'),
    'opus': ('audio', 'ogg'),
    'snd': ('audio', 'basic'),
    'wav': ('audio', 'x-wav'),
    'wma': ('audio', 'x-ms-wma'),

    'bmp': ('image', 'x-ms-bmp'),
    'gif': ('image', 'gif'),
    'ico': ('image', 'vnd.microsoft.icon'),
    'ief': ('image', 'ief'),
    'jpe': ('image', 'jpeg'),
    'jpeg': ('image', 'jpeg'),
    'jpg': ('image', 'jpeg'),
    'png': ('image', 'png'),
    'svg': ('image', 'svg+xml'),
    'tif': ('image', 'tiff'),
    'tiff': ('image', 'tiff'),

    'ass': ('text', 'plain'),
    'bat': ('text', 'plain'),
    'c': ('text', 'plain'),
    'css': ('text', 'css'),
    'csv': ('text', 'csv'),
    'etx': ('text', 'x-setext'),
    'h': ('text', 'plain'),
    'htm': ('text', 'html'),
    'html': ('text', 'html'),
    'js': ('text', 'javascript'),
    'json': ('text', 'json'),
    'ksh': ('text', 'plain'),
    'md': ('text', 'plain'),
    'nfo': ('text', 'plain'),
    'pl': ('text', 'plain'),
    'py': ('text', 'x-python'),
    'rst': ('text', 'plain'),
    'rtx': ('text', 'richtext'),
    'sgm': ('text', 'x-sgml'),
    'sgml': ('text', 'x-sgml'),
    'srt': ('text', 'plain'),
    'tsv': ('text', 'tab-separated-values'),
    'txt': ('text', 'plain'),
    'vcf': ('text', 'x-vcard'),
    'xml': ('text', 'xml'),

    'avi': ('video', 'x-msvideo'),
    'm1v': ('video', 'mpeg'),
    'mkv': ('video', 'x-matroska'),
    'mov': ('video', 'quicktime'),
    'mp4': ('video', 'mp4'),
    'mpa': ('video', 'mpeg'),
    'mpe': ('video', 'mpeg'),
    'mpeg': ('video', 'mpeg'),
    'mpg': ('video', 'mpeg'),
    'qt': ('video', 'quicktime'),
    'webm': ('video', 'webm'),
    'wmv': ('video', 'x-ms-asf'),
}

# Photodb ##########################################################################################

DEFAULT_DATADIR = '_etiquette'
DEFAULT_DBNAME = 'phototagger.db'
DEFAULT_CONFIGNAME = 'config.json'
DEFAULT_THUMBDIR = 'thumbnails'

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
        'thumbnails',
    ],

    'file_read_chunk': 2 ** 20,
    'id_bits': 32,
    'thumbnail_width': 400,
    'thumbnail_height': 400,

    'recycle_instead_of_delete': True,

    'motd_strings': [
        'Good morning, Paul. What will your first sequence of the day be?',
    ],
}
