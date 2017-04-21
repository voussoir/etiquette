import re

def pascal_to_loudsnakes(text):
    match = re.findall('[A-Z][a-z]*', text)
    text = '_'.join(match)
    text = text.upper()
    return text


class ErrorTypeAdder(type):
    '''
    Thanks Unutbu
    http://stackoverflow.com/a/18126678
    '''
    def __init__(cls, name, bases, clsdict):
        type.__init__(cls, name, bases, clsdict)
        cls.error_type = pascal_to_loudsnakes(name)

class EtiquetteException(Exception, metaclass=ErrorTypeAdder):
    error_message = ''
    def __init__(self, *args, **kwargs):
        self.given_args = args
        self.given_kwargs = kwargs
        self.error_message = self.error_message.format(*args, **kwargs)


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
class AlbumExists(EtiquetteException):
    error_message = 'Album "{}" already exists.'
    def __init__(self, album):
        self.album = album
        EtiquetteException.__init__(self, album.id)

class GroupExists(EtiquetteException):
    error_message = '{member} already in group {group}'

class PhotoExists(EtiquetteException):
    error_message = 'Photo "{}" already exists.'
    def __init__(self, photo):
        self.photo = photo
        EtiquetteException.__init__(self, photo.id)

class TagExists(EtiquetteException):
    error_message = 'Tag "{}" already exists.'
    def __init__(self, tag):
        self.tag = tag
        EtiquetteException.__init__(self, tag.name)

class UserExists(EtiquetteException):
    error_message = 'User "{}" already exists.'
    def __init__(self, user):
        self.user = user
        EtiquetteException.__init__(self, user.username)


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

class InvalidUsernameChars(EtiquetteException):
    error_message = 'Username "{username}" contains invalid characters: {badchars}.'

class PasswordTooShort(EtiquetteException):
    error_message = 'Password is shorter than the minimum of {min_length}.'

class UsernameTooLong(EtiquetteException):
    error_message = 'Username "{username}" is longer than maximum of {max_length}.'

class UsernameTooShort(EtiquetteException):
    error_message = 'Username "{username}" is shorter than minimum of {min_length}.'

class WrongLogin(EtiquetteException):
    error_message = 'Wrong username-password combination.'


# GENERAL ERRORS
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
