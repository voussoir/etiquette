# NO SUCH
class NoSuchAlbum(Exception):
    pass

class NoSuchGroup(Exception):
    pass

class NoSuchPhoto(Exception):
    pass

class NoSuchSynonym(Exception):
    pass

class NoSuchTag(Exception):
    pass

class NoSuchUser(Exception):
    pass


# EXISTS
class GroupExists(Exception):
    pass

class PhotoExists(Exception):
    pass

class TagExists(Exception):
    pass

class UserExists(Exception):
    pass


# TAG ERRORS
class CantSynonymSelf(Exception):
    pass

class RecursiveGrouping(Exception):
    pass

class TagTooLong(Exception):
    pass

class TagTooShort(Exception):
    pass


# USER ERRORS
class InvalidUsernameChars(Exception):
    pass

class PasswordTooShort(Exception):
    pass

class UsernameTooLong(Exception):
    pass

class UsernameTooShort(Exception):
    pass

class WrongLogin(Exception):
    pass


# GENERAL ERRORS
class NotExclusive(Exception):
    '''
    For when two or more mutually exclusive actions have been requested.
    '''
    pass

class OutOfOrder(Exception):
    '''
    For when a requested range (a, b) has b > a
    '''
    pass
