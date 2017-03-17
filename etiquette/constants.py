import converter
import logging
import string
import traceback

try:
    ffmpeg = converter.Converter(
        ffmpeg_path='C:\\software\\ffmpeg\\bin\\ffmpeg.exe',
        ffprobe_path='C:\\software\\ffmpeg\\bin\\ffprobe.exe',
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
ERROR_DATABASE_OUTOFDATE = '''
Database is out-of-date. {current} should be {new}.
Please use utilities\\etiquette_upgrader.py
'''.strip()

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

    'mkv': 'video/x-matroska',

    'ass': 'text/plain',
    'srt': 'text/plain',
}

DEFAULT_DATADIR = '.\\_etiquette'

DEFAULT_CONFIGURATION = {
    'log_level': logging.DEBUG,

    'enable_new_album': True,
    'enable_new_bookmark': True,
    'enable_new_photo': True,
    'enable_new_tag': True,
    'enable_new_user': True,
    'enable_photo_add_remove_tag': True,
    'enable_photo_reload_metadata': True,
    'enable_photo_generate_thumbnail': True,

    'min_tag_name_length': 1,
    'max_tag_name_length': 32,
    'valid_tag_chars': string.ascii_lowercase + string.digits + '_',

    'min_username_length': 2,
    'max_username_length': 24,
    'valid_username_chars': string.ascii_letters + string.digits + '~!@#$%^*()[]{}:;,.<>/\\-_+=',
    'min_password_length': 6,

    'id_length': 12,
    'digest_exclude_files': [
        'phototagger.db',
        'desktop.ini',
        'thumbs.db',
    ],
    'digest_exclude_dirs': [
        '_site_thumbnails',
    ],

    'file_read_chunk': 2 ** 20,
    'thumbnail_width': 400,
    'thumbnail_height': 400,
    'motd_strings': [
        'Good morning, Paul. What will your first sequence of the day be?',
    ],

}
