'''
This file provides the FileCacheManager to serve ETag and Cache-Control headers
for files on disk.

We consider the following cases:

Client does not have the file (or has disabled their cache, effectively same):
    Server sends file, provides ETag, and tells client to save it for max-age.

Client has the file, but it has been a long time, beyond the max-age:
    Client provides the old ETag. If it's still valid, Server responds with
    304 Not Modified and no data. Client keeps the file.

Client has the file, and it is within the max-age:
    Client does not make a request at all.

This FileCacheManager uses the file's MD5 hash as the ETag, and will only
recalculate it if the file's mtime has changed since the last request.
'''

import time

import etiquette

from voussoirkit import cacheclass
from voussoirkit import pathclass

class FileCacheManager:
    def __init__(self, maxlen, max_filesize, max_age):
        self.cache = cacheclass.Cache(maxlen=maxlen)
        self.max_filesize = int(max_filesize)
        self.max_age = int(max_age)

    def get(self, filepath):
        if (self.max_filesize is not None) and (filepath.size > self.max_filesize):
            #print('I\'m not going to cache that!')
            return None

        try:
            return self.cache[filepath]
        except KeyError:
            pass
        cache_file = CacheFile(filepath, max_age=self.max_age)
        self.cache[filepath] = cache_file
        return cache_file

class CacheFile:
    def __init__(self, filepath, max_age):
        self.filepath = filepath
        self.max_age = max_age
        self._stored_hash_time = None
        self._stored_hash_value = None

    def get_etag(self):
        if self._stored_hash_value is None:
            refresh = True
        elif self.filepath.stat.st_mtime > self._stored_hash_time:
            refresh = True
        else:
            refresh = False

        if refresh:
            self._stored_hash_time = self.filepath.stat.st_mtime
            self._stored_hash_value = etiquette.helpers.hash_file_md5(self.filepath)
        return self._stored_hash_value

    def get_headers(self):
        headers = {
            'ETag': self.get_etag(),
            'Cache-Control': 'max-age=%d' % self.max_age,
        }
        return headers
