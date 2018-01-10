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

SQL_LASTID_COLUMNS = [
    'table',
    'last_id',
]
SQL_ALBUM_DIRECTORY_COLUMNS = [
    'albumid',
    'directory',
]
SQL_ALBUM_COLUMNS = [
    'id',
    'title',
    'description',
]
SQL_BOOKMARK_COLUMNS = [
    'id',
    'title',
    'url',
    'author_id',
]
SQL_PHOTO_COLUMNS = [
    'id',
    'filepath',
    'override_filename',
    'extension',
    'width',
    'height',
    'ratio',
    'area',
    'duration',
    'bytes',
    'created',
    'thumbnail',
    'tagged_at',
    'author_id',
]
SQL_TAG_COLUMNS = [
    'id',
    'name',
    'description',
]
SQL_SYN_COLUMNS = [
    'name',
    'master',
]
SQL_ALBUMGROUP_COLUMNS = [
    'parentid',
    'memberid',
]
SQL_ALBUMPHOTO_COLUMNS = [
    'albumid',
    'photoid',
]
SQL_PHOTOTAG_COLUMNS = [
    'photoid',
    'tagid',
]
SQL_TAGGROUP_COLUMNS = [
    'parentid',
    'memberid',
]
SQL_USER_COLUMNS = [
    'id',
    'username',
    'password',
    'created',
]

_sql_dictify = lambda columns: {key:index for (index, key) in enumerate(columns)}
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
