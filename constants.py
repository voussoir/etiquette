import converter
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
SQL_ALBUM_COLUMNS = [
    'id',
    'title',
    'description',
    'associated_directory',
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
SQL_ALBUMPHOTO = _sql_dictify(SQL_ALBUMPHOTO_COLUMNS)
SQL_LASTID = _sql_dictify(SQL_LASTID_COLUMNS)
SQL_PHOTO = _sql_dictify(SQL_PHOTO_COLUMNS)
SQL_PHOTOTAG = _sql_dictify(SQL_PHOTOTAG_COLUMNS)
SQL_SYN = _sql_dictify(SQL_SYN_COLUMNS)
SQL_TAG = _sql_dictify(SQL_TAG_COLUMNS)
SQL_TAGGROUP = _sql_dictify(SQL_TAGGROUP_COLUMNS)
SQL_USER = _sql_dictify(SQL_USER_COLUMNS)


# Errors and warnings
ERROR_DATABASE_OUTOFDATE = 'Database is out-of-date. {current} should be {new}. Please use etiquette_upgrader.py'
ERROR_INVALID_ACTION = 'Invalid action'
ERROR_NO_SUCH_TAG = 'Doesn\'t exist'
ERROR_NO_TAG_GIVEN = 'No tag name supplied'
ERROR_SYNONYM_ITSELF = 'Cant apply synonym to itself'
ERROR_TAG_TOO_SHORT = 'Not enough valid chars'
WARNING_MINMAX_INVALID = 'Field "{field}": "{value}" is not a valid request. Ignored.'
WARNING_MINMAX_OOO = 'Field "{field}": minimum "{min}" maximum "{max}" are out of order. Ignored.'
WARNING_NO_SUCH_TAG = 'Tag "{tag}" does not exist. Ignored.'
WARNING_ORDERBY_BADCOL = '"{column}" is not a sorting option. Ignored.'
WARNING_ORDERBY_BADSORTER = 'You can\'t order "{column}" by "{sorter}". Defaulting to descending.'

# Operational info
EXPRESSION_OPERATORS = {'(', ')', 'OR', 'AND', 'NOT'}
ADDITIONAL_MIMETYPES = {
    'srt': 'text',
    'mkv': 'video',
}

DEFAULT_DATADIR = '.\\_etiquette'

DEFAULT_CONFIGURATION = {
    'min_tag_name_length': 1,
    'max_tag_name_length': 32,
    'valid_tag_chars': string.ascii_lowercase + string.digits + '_',

    'min_username_length': 2,
    'max_username_length': 24,
    'valid_username_chars': string.ascii_letters + string.digits + '~!@#$%^&*()[]{}:;,.<>/\\-_+=',
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
