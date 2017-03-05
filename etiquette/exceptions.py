import re

def pascal_to_loudsnakes(text):
    match = re.findall('[A-Z][a-z]*', text)
    text = '_'.join(match)
    text = text.upper()
    return text

class EtiquetteException(Exception):
    error_message = ''
    def __init__(self, *args):
        self.error_type = pascal_to_loudsnakes(type(self).__name__)
        Exception.__init__(self, *args)

class WithFormat(EtiquetteException):
    def __init__(self, *args, **kwargs):
        self.error_message = self.error_message.format(*args, **kwargs)
        EtiquetteException.__init__(self, self.error_message)

# NO SUCH
class NoSuch(WithFormat):
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
class GroupExists(WithFormat):
    error_message = '{member} already in group {group}'

class PhotoExists(WithFormat):
    error_message = 'Photo "{}" already exists.'
    def __init__(self, photo):
        self.photo = photo
        WithFormat.__init__(self, photo.id)

class TagExists(WithFormat):
    error_message = 'Tag "{}" already exists.'
    def __init__(self, tag):
        self.tag = tag
        WithFormat.__init__(self, tag.name)

class UserExists(WithFormat):
    error_message = 'User "{}" already exists.'
    def __init__(self, user):
        self.user = user
        WithFormat.__init__(self, user.username)


# TAG ERRORS
class CantSynonymSelf(EtiquetteException):
    error_message = 'Cannot apply synonym to self.'

class RecursiveGrouping(EtiquetteException):
    error_message = '{group} is an ancestor of {member}.'

class TagTooLong(WithFormat):
    error_message = 'Tag "{}" is too long.'

class TagTooShort(WithFormat):
    error_message = 'Tag "{}" has too few valid characters.'


# USER ERRORS
class InvalidUsernameChars(WithFormat):
    error_message = 'Username "{username}" contains invalid characters: {badchars}.'

class PasswordTooShort(WithFormat):
    error_message = 'Password is shorter than the minimum of {min_length}.'

class UsernameTooLong(WithFormat):
    error_message = 'Username "{username}" is longer than maximum of {max_length}.'

class UsernameTooShort(WithFormat):
    error_message = 'Username "{username}" is shorter than minimum of {min_length}.'

class WrongLogin(EtiquetteException):
    error_message = 'Wrong username-password combination.'


# GENERAL ERRORS
class NotExclusive(EtiquetteException):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    pass

class OutOfOrder(WithFormat):
    '''
    For when a requested minmax range (a, b) has b > a
    '''
    error_message = 'Range "{range}": minimum "{min}" and maximum "{max}" are out of order.'
