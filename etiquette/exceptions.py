from voussoirkit import stringtools

class ErrorTypeAdder(type):
    '''
    During definition, the Exception class will automatically receive a class
    attribute called `error_type` which is just the class's name as a string
    in the loudsnake casing style. NoSuchPhoto -> NO_SUCH_PHOTO.

    This is used for serialization of the exception object and should
    basically act as a status code when displaying the error to the user.

    Thanks Unutbu
    http://stackoverflow.com/a/18126678
    '''
    def __init__(cls, name, bases, clsdict):
        type.__init__(cls, name, bases, clsdict)
        cls.error_type = stringtools.pascal_to_loudsnakes(name)

class EtiquetteException(Exception, metaclass=ErrorTypeAdder):
    '''
    Base type for all of the Etiquette exceptions.
    Subtypes should have a class attribute `error_message`. The error message
    may contain {format} strings which will be formatted using the
    Exception's constructor arguments.
    '''
    error_message = ''

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.given_args = args
        self.given_kwargs = kwargs
        self.error_message = self.error_message.format(*args, **kwargs)
        self.args = (self.error_message, args, kwargs)

    def __str__(self):
        return f'{self.error_type}: {self.error_message}'

    def jsonify(self):
        j = {
            'type': 'error',
            'error_type': self.error_type,
            'error_message': self.error_message,
        }
        return j

# NO SUCH ##########################################################################################

class NoSuch(EtiquetteException):
    pass

class NoSuchAlbum(NoSuch):
    error_message = 'Album "{}" does not exist.'

class NoSuchBookmark(NoSuch):
    error_message = 'Bookmark "{}" does not exist.'

class NoSuchGroup(NoSuch):
    error_message = 'Group "{}" does not exist.'

class NoSuchPhoto(NoSuch):
    error_message = 'Photo "{}" does not exist.'

class NoSuchSynonym(NoSuch):
    error_message = 'Synonym "{}" does not exist.'

class NoSuchTag(NoSuch):
    error_message = 'Tag "{}" does not exist.'

class NoSuchUser(NoSuch):
    error_message = 'User "{}" does not exist.'

# EXISTS ###########################################################################################

# The following inits store a copy of the object so that the exception catcher
# can do something with it. It's not related to the string formatting.

class Exists(EtiquetteException):
    pass

class AlbumExists(Exists):
    error_message = 'Album "{}" already exists.'

    def __init__(self, album):
        self.album = album
        EtiquetteException.__init__(self, album)

class GroupExists(Exists):
    error_message = '{member} already in group {group}.'

class PhotoExists(Exists):
    error_message = 'Photo "{}" already exists.'

    def __init__(self, photo):
        self.photo = photo
        EtiquetteException.__init__(self, photo)

class TagExists(Exists):
    error_message = 'Tag "{}" already exists.'

    def __init__(self, tag):
        self.tag = tag
        EtiquetteException.__init__(self, tag)

class UserExists(Exists):
    error_message = 'User "{}" already exists.'

    def __init__(self, user):
        self.user = user
        EtiquetteException.__init__(self, user)

# TAG ERRORS #######################################################################################

class CantGroupSelf(EtiquetteException):
    error_message = 'Cannot group {} into itself.'

class CantSynonymSelf(EtiquetteException):
    error_message = 'Cannot make {} a synonym of itself.'

class EasyBakeError(EtiquetteException):
    error_message = '{}'

class RecursiveGrouping(EtiquetteException):
    error_message = '{group} is an ancestor of {member}.'

class TagTooLong(EtiquetteException):
    error_message = 'Tag "{}" is too long.'

class TagTooShort(EtiquetteException):
    error_message = 'Tag "{}" has too few valid characters.'

# USER ERRORS ######################################################################################

class AlreadySignedIn(EtiquetteException):
    error_message = 'You\'re already signed in.'

class CantDeleteUser(EtiquetteException):
    error_message = '{} can\'t be deleted because they still have possessions.'

class InvalidPassword(EtiquetteException):
    error_message = 'Password is invalid.'

class InvalidUsername(EtiquetteException):
    error_message = 'Username "{username}" is invalid.'

class InvalidUsernameChars(InvalidUsername):
    error_message = 'Username "{username}" contains invalid characters: {badchars}.'

class PasswordTooShort(InvalidPassword):
    error_message = 'Password is shorter than the minimum of {min_length}.'

class UsernameTooLong(InvalidUsername):
    error_message = 'Username "{username}" is longer than maximum of {max_length}.'

class UsernameTooShort(InvalidUsername):
    error_message = 'Username "{username}" is shorter than minimum of {min_length}.'

class DisplayNameTooLong(EtiquetteException):
    error_message = 'Display name "{display_name}" is longer than maximum of {max_length}.'

class Unauthorized(EtiquetteException):
    error_message = 'You\'re not allowed to do that.'

class WrongLogin(EtiquetteException):
    error_message = 'Wrong username-password combination.'

# GENERAL ERRORS ###################################################################################

class BadDataDirectory(EtiquetteException):
    '''
    Raised by PhotoDB __init__ if the requested data_directory is invalid.
    '''
    error_message = 'Bad data directory "{}"'

OUTOFDATE = '''
Database is out of date. {existing} should be {new}.
Please run utilities\\database_upgrader.py "{filepath.absolute_path}"
'''.strip()
class DatabaseOutOfDate(EtiquetteException):
    '''
    Raised by PhotoDB __init__ if the user's database is behind.
    '''
    error_message = OUTOFDATE

class FeatureDisabled(EtiquetteException):
    '''
    For when features of the system have been disabled by the configuration.
    '''
    error_message = 'This feature has been disabled. Requires {requires}.'

class GenerateIDFailed(EtiquetteException):
    error_message = 'Could not generate unique ID on {table}. You should increase ID bits.'

class MinMaxInvalid(EtiquetteException):
    '''
    For when the user searches for e.g. width=a-b but the a-b can't be parsed.
    If the values can be parsed but are backward, use MinMaxOutOfOrder.
    '''
    error_message = 'Field "{field}": "{value}" is not a valid request.'

class MinMaxOutOfOrder(EtiquetteException):
    '''
    For when a requested minmax range (a, b) has b > a
    '''
    error_message = 'Range "{range}": minimum "{min}" and maximum "{max}" are out of order.'

class NoClosestPhotoDB(EtiquetteException):
    '''
    For calls to PhotoDB.closest_photodb where none exists between cwd and
    drive root.
    '''
    error_message = 'There is no PhotoDB in "{}" or its parents.'

class NoYields(EtiquetteException):
    '''
    For when all of the yield_* arguments have been provided as False, and thus
    there is nothing for the called function to yield.
    '''
    error_message = 'At least one of {} must be selected.'

class NotExclusive(EtiquetteException):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    error_message = 'One and only one of {} must be passed.'

class OrderByBadColumn(EtiquetteException):
    '''
    For when the user tries to orderby a column that does not exist or is
    not allowed.
    '''
    error_message = '"{column}" is not a sortable column.'

class OrderByBadDirection(EtiquetteException):
    '''
    For when the user tries to orderby a direction that is not asc or desc.
    '''
    error_message = 'You can\'t order "{column}" by "{direction}". Should be asc or desc.'

class OrderByInvalid(EtiquetteException):
    '''
    For when the orderby request cannot be parsed into column and direction.
    For example, it contains too many hyphens like a-b-c.

    If the column and direction can be parsed but are invalid, use
    OrderByBadColumn or OrderByBadDirection
    '''
    error_message = 'Invalid orderby request "{request}".'
