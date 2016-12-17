import string

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
