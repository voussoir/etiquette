class CantSynonymSelf(Exception):
    pass

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


class PhotoExists(Exception):
    pass

class TagExists(Exception):
    pass

class GroupExists(Exception):
    pass


class TagTooLong(Exception):
    pass

class TagTooShort(Exception):
    pass

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
