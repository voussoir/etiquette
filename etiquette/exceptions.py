import re

def pascal_to_loudsnakes(text):
    match = re.findall('[A-Z][a-z]*', text)
    text = '_'.join(match)
    text = text.upper()
    return text

def with_error_type(cls):
    cls.error_type = pascal_to_loudsnakes(cls.__name__)
    return cls

class EtiquetteException(Exception):
    error_message = ''

class WithFormat(EtiquetteException):
    def __init__(self, *args, **kwargs):
        self.given_args = args
        self.given_kwargs = kwargs
        self.error_message = self.error_message.format(*args, **kwargs)
        EtiquetteException.__init__(self, self.error_message)

# NO SUCH
class NoSuch(WithFormat):
    pass

@with_error_type
class NoSuchAlbum(NoSuch):
    error_message = 'Album "{}" does not exist.'

@with_error_type
class NoSuchBookmark(NoSuch):
    error_message = 'Bookmark "{}" does not exist.'

@with_error_type
class NoSuchGroup(NoSuch):
    error_message = 'Group "{}" does not exist.'

@with_error_type
class NoSuchPhoto(NoSuch):
    error_message = 'Photo "{}" does not exist.'

@with_error_type
class NoSuchSynonym(NoSuch):
    error_message = 'Synonym "{}" does not exist.'

@with_error_type
class NoSuchTag(NoSuch):
    error_message = 'Tag "{}" does not exist.'

@with_error_type
class NoSuchUser(NoSuch):
    error_message = 'User "{}" does not exist.'


# EXISTS
@with_error_type
class GroupExists(WithFormat):
    error_message = '{member} already in group {group}'

@with_error_type
class PhotoExists(WithFormat):
    error_message = 'Photo "{}" already exists.'
    def __init__(self, photo):
        self.photo = photo
        WithFormat.__init__(self, photo.id)

@with_error_type
class TagExists(WithFormat):
    error_message = 'Tag "{}" already exists.'
    def __init__(self, tag):
        self.tag = tag
        WithFormat.__init__(self, tag.name)

@with_error_type
class UserExists(WithFormat):
    error_message = 'User "{}" already exists.'
    def __init__(self, user):
        self.user = user
        WithFormat.__init__(self, user.username)


# TAG ERRORS
@with_error_type
class CantSynonymSelf(EtiquetteException):
    error_message = 'Cannot apply synonym to self.'

@with_error_type
class EasyBakeError(EtiquetteException):
    error_message = ''
    def __init__(self, message):
        self.error_message = message
        EtiquetteException.__init__(self)

@with_error_type
class RecursiveGrouping(WithFormat):
    error_message = '{group} is an ancestor of {member}.'

@with_error_type
class TagTooLong(WithFormat):
    error_message = 'Tag "{}" is too long.'

@with_error_type
class TagTooShort(WithFormat):
    error_message = 'Tag "{}" has too few valid characters.'


# USER ERRORS
@with_error_type
class InvalidUsernameChars(WithFormat):
    error_message = 'Username "{username}" contains invalid characters: {badchars}.'

@with_error_type
class PasswordTooShort(WithFormat):
    error_message = 'Password is shorter than the minimum of {min_length}.'

@with_error_type
class UsernameTooLong(WithFormat):
    error_message = 'Username "{username}" is longer than maximum of {max_length}.'

@with_error_type
class UsernameTooShort(WithFormat):
    error_message = 'Username "{username}" is shorter than minimum of {min_length}.'

@with_error_type
class WrongLogin(EtiquetteException):
    error_message = 'Wrong username-password combination.'


# GENERAL ERRORS
@with_error_type
class FeatureDisabled(EtiquetteException):
    '''
    For when features of the system have been disabled by the configuration.
    '''
    error_message = 'This feature has been disabled.'

@with_error_type
class NotExclusive(EtiquetteException):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    pass

@with_error_type
class OutOfOrder(WithFormat):
    '''
    For when a requested minmax range (a, b) has b > a
    '''
    error_message = 'Range "{range}": minimum "{min}" and maximum "{max}" are out of order.'
