from voussoirkit import cacheclass

import etiquette

class FileEtagManager:
    '''
    The FileEtagManager serves ETag and Cache-Control headers for disk files to
    enable client-side caching.

    We consider the following cases:

    Client does not have the file (or has disabled their cache):
        Server sends file, provides ETag, tells client to save it for max-age.

    Client has the file, but it has been a long time, beyond the max-age:
        Client provides the old ETag. If it's still valid, Server responds with
        304 Not Modified and no data. Client keeps the old file.

    Client has the file, and it is within the max-age:
        Client does not make a request at all.

    We use the file's MD5 hash as the ETag, and will only recalculate it if the
    file's mtime has changed since the last request.

    Note, this class does not store any of the file's content data.
    '''
    def __init__(self, maxlen, max_age, max_filesize):
        '''
        max_len:
            The number of files to track in this cache.
        max_age:
            Integer number of seconds that will be send to the client as
            Cache-Control:max-age=x
        max_filesize:
            Integer number of bytes. Because we use the file's MD5 as its etag,
            you may wish to prevent the reading of large files. Files larger
            than this size will not be etagged.
        '''
        self.cache = cacheclass.Cache(maxlen=maxlen)
        self.max_age = int(max_age)
        self.max_filesize = max(int(max_filesize), 0) or None

    def get_304_headers(self, request, filepath):
        '''
        Given a request object and a filepath that we would like to send back
        as the response, check if the client's provided etag matches the
        server's cached etag, and return the headers to be used in a 304
        response (etag, cache-control).

        If the client did not provide an etag, or their etag does not match the
        current file, or the file cannot be cached, return None.
        '''
        client_etag = request.headers.get('If-None-Match', None)
        if client_etag is None:
            return None

        server_value = self.get_file(filepath)
        if server_value is None:
            return None

        server_etag = server_value.get_etag()
        if client_etag != server_etag:
            return None

        return server_value.get_headers()

    def get_file(self, filepath):
        '''
        Return a FileEtag object if the filepath can be cached, or None if it
        cannot (size greater than max_filesize).
        '''
        try:
            return self.cache[filepath]
        except KeyError:
            pass

        if (self.max_filesize is not None) and (filepath.size > self.max_filesize):
            return None

        cache_file = FileEtag(filepath, max_age=self.max_age)
        self.cache[filepath] = cache_file
        return cache_file

class FileEtag:
    '''
    This class represents an individual disk file that is being managed by the
    FileEtagManager.
    '''
    def __init__(self, filepath, max_age):
        self.filepath = filepath
        self.max_age = int(max_age)
        self._stored_hash_time = None
        self._stored_hash_value = None

    def get_etag(self):
        mtime = self.filepath.stat.st_mtime
        do_refresh = (self._stored_hash_value is None) or (mtime > self._stored_hash_time)

        if do_refresh:
            self._stored_hash_time = mtime
            self._stored_hash_value = etiquette.helpers.hash_file_md5(self.filepath)

        return self._stored_hash_value

    def get_headers(self):
        headers = {
            'ETag': self.get_etag(),
            'Cache-Control': f'max-age={self.max_age}',
        }
        return headers
