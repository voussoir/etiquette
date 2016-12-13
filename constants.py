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


# Default settings
MIN_TAG_NAME_LENGTH = 1
MAX_TAG_NAME_LENGTH = 32
VALID_TAG_CHARS = string.ascii_lowercase + string.digits + '_'

DEFAULT_ID_LENGTH = 12
DEFAULT_DBNAME = 'phototagger.db'
DEFAULT_DATADIR = '.\\_etiquette'
DEFAULT_DIGEST_EXCLUDE_FILES = [
    DEFAULT_DBNAME,
    'desktop.ini',
    'thumbs.db'
]
DEFAULT_DIGEST_EXCLUDE_DIRS = [
    '_site_thumbnails',
]
FILE_READ_CHUNK = 2 ** 20

THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400


# Operational info
ADDITIONAL_MIMETYPES = {
    'srt': 'text',
    'mkv': 'video',
}
EXPRESSION_OPERATORS = {'(', ')', 'OR', 'AND', 'NOT'}
MOTD_STRINGS = [
'Good morning, Paul. What will your first sequence of the day be?',
#'Buckle up, it\'s time to:',
]