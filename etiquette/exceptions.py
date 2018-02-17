import re

def pascal_to_loudsnakes(text):
    '''
    NoSuchPhoto -> NO_SUCH_PHOTO
    '''
    match = re.findall('[A-Z][a-z]*', text)
    text = '_'.join(match)
    text = text.upper()
    return text


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
        cls.error_type = pascal_to_loudsnakes(name)

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
        return self.error_type + '\n' + self.error_message


# NO SUCH
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


# EXISTS
class Exists(EtiquetteException):
    pass

class AlbumExists(Exists):
    error_message = 'Album "{}" already exists.'
    def __init__(self, album):
        self.album = album
        EtiquetteException.__init__(self, album)

class GroupExists(Exists):
    error_message = '{member} already in group {group}'

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


# TAG ERRORS
class CantSynonymSelf(EtiquetteException):
    error_message = 'Cannot apply synonym to self.'

class EasyBakeError(EtiquetteException):
    error_message = '{}'

class RecursiveGrouping(EtiquetteException):
    error_message = '{group} is an ancestor of {member}.'

class TagTooLong(EtiquetteException):
    error_message = 'Tag "{}" is too long.'

class TagTooShort(EtiquetteException):
    error_message = 'Tag "{}" has too few valid characters.'


# USER ERRORS
class AlreadySignedIn(EtiquetteException):
    error_message = 'You\'re already signed in.'

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

class WrongLogin(EtiquetteException):
    error_message = 'Wrong username-password combination.'


# GENERAL ERRORS
OUTOFDATE = '''
Database is out of date. {current} should be {new}.
Please use utilities\\database_upgrader.py
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
    error_message = 'This feature has been disabled.'

class NotExclusive(EtiquetteException):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    error_message = 'One and only one of {} must be passed.'

class OutOfOrder(EtiquetteException):
    '''
    For when a requested minmax range (a, b) has b > a
    '''
    error_message = 'Range "{range}": minimum "{min}" and maximum "{max}" are out of order.'
