class EtiquetteException(Exception):
    pass

# NO SUCH
class NoSuchAlbum(EtiquetteException):
    error_type = 'NO_SUCH_ALBUM'
    error_message = 'Album "{album}" does not exist.'
    pass

class NoSuchBookmark(EtiquetteException):
    error_type = 'NO_SUCH_BOOKMARK'
    error_message = 'Bookmark "{bookmark}" does not exist.'
    pass

class NoSuchGroup(EtiquetteException):
    error_type = 'NO_SUCH_GROUP'
    error_message = 'Group "{group}" does not exist.'
    pass

class NoSuchPhoto(EtiquetteException):
    error_type = 'NO_SUCH_PHOTO'
    error_message = 'Photo "{photo}" does not exist.'
    pass

class NoSuchSynonym(EtiquetteException):
    error_type = 'NO_SUCH_SYNONYM'
    error_message = 'Synonym "{synonym}" does not exist.'
    pass

class NoSuchTag(EtiquetteException):
    error_type = 'NO_SUCH_TAG'
    error_message = 'Tag "{tag}" does not exist.'
    pass

class NoSuchUser(EtiquetteException):
    error_type = 'NO_SUCH_User'
    error_message = 'User "{user}" does not exist.'
    pass


# EXISTS
class GroupExists(EtiquetteException):
    pass

class PhotoExists(EtiquetteException):
    pass

class TagExists(EtiquetteException):
    pass

class UserExists(EtiquetteException):
    error_type = 'USER_EXISTS'
    error_message = 'Username "{username}" already exists.'
    pass


# TAG ERRORS
class CantSynonymSelf(EtiquetteException):
    error_type = 'TAG_SYNONYM_ITSELF'
    error_message = 'Cannot apply synonym to self.'
    pass

class RecursiveGrouping(EtiquetteException):
    error_type = 'RECURSIVE_GROUPING'
    error_message = 'Cannot create a group within itself.'
    pass

class TagTooLong(EtiquetteException):
    error_type = 'TAG_TOO_LONG'
    error_message = 'Tag "{tag}" is too long.'
    pass

class TagTooShort(EtiquetteException):
    error_type = 'TAG_TOO_SHORT'
    error_message = 'Tag "{tag}" has too few valid characters.'
    pass


# USER ERRORS
class InvalidUsernameChars(EtiquetteException):
    error_type = 'INVALID_USERNAME_CHARACTERS'
    error_message = 'Username "{username}" contains invalid characters: {badchars}'
    pass

class PasswordTooShort(EtiquetteException):
    error_type = 'PASSWORD_TOO_SHORT'
    error_message = 'Password is shorter than the minimum of {min_length}'
    pass

class UsernameTooLong(EtiquetteException):
    error_type = 'USERNAME_TOO_LONG'
    error_message = 'Username "{username}" is longer than maximum of {max_length}'
    pass

class UsernameTooShort(EtiquetteException):
    error_type = 'USERNAME_TOO_SHORT'
    error_message = 'Username "{username}" is shorter than minimum of {min_length}'
    pass

class WrongLogin(EtiquetteException):
    pass


# GENERAL ERRORS
class NotExclusive(EtiquetteException):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    pass

class OutOfOrder(EtiquetteException):
    '''
    For when a requested minmax range (a, b) has b > a
    '''
    error_type = 'OUT_OF_ORDER'
    error_message = 'Field "{field}": minimum "{min}" and maximum "{max}" are out of order.'
    pass
