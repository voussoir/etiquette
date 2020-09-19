import flask; from flask import request
import functools
import time

from voussoirkit import cacheclass

import etiquette

def cached_endpoint(max_age):
    '''
    The cached_endpoint decorator can be used on slow endpoints that don't need
    to be constantly updated or endpoints that produce large, static responses.

    WARNING: The return value of the endpoint is shared with all users.
    You should never use this cache on an endpoint that provides private
    or personalized data, and you should not try to pass other headers through
    the response.

    When the function is run, its return value is stored and a random etag is
    generated so that subsequent runs can respond with 304. This way, large
    response bodies do not need to be transmitted often.

    Given a nonzero max_age, the endpoint will only be run once per max_age
    seconds on a global basis (not per-user). This way, you can prevent a slow
    function from being run very often. In-between requests will just receive
    the previous return value (still using 200 or 304 as appropriate for the
    client's provided etag).

    An example use case would be large-sized data dumps that don't need to be
    precisely up to date every time.
    '''
    state = {
        'max_age': max_age,
        'stored_value': None,
        'stored_etag': None,
        'headers': {'ETag': None, 'Cache-Control': f'max-age={max_age}'},
        'last_run': 0,
    }

    def wrapper(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if (not state['max_age']) or (time.time() - state['last_run'] > state['max_age']):
                value = function(*args, **kwargs)
                if isinstance(value, flask.Response):
                    value = value.response
                if value != state['stored_value']:
                    state['stored_value'] = value
                    state['stored_etag'] = etiquette.helpers.random_hex(20)
                    state['headers']['ETag'] = state['stored_etag']
                state['last_run'] = time.time()
            else:
                value = state['stored_value']

            client_etag = request.headers.get('If-None-Match', None)
            if client_etag == state['stored_etag']:
                response = flask.Response(status=304, headers=state['headers'])
            else:
                response = flask.Response(value, status=200, headers=state['headers'])

            return response
        return wrapped
    return wrapper

class FileCacheManager:
    '''
    The FileCacheManager serves ETag and Cache-Control headers for disk files.

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
    '''
    def __init__(self, maxlen, max_age, max_filesize):
        self.cache = cacheclass.Cache(maxlen=maxlen)
        self.max_age = int(max_age)
        self.max_filesize = max(int(max_filesize), 0) or None

    def get(self, filepath):
        try:
            return self.cache[filepath]
        except KeyError:
            pass

        if (self.max_filesize is not None) and (filepath.size > self.max_filesize):
            return None

        cache_file = CacheFile(filepath, max_age=self.max_age)
        self.cache[filepath] = cache_file
        return cache_file

    def matches(self, request, filepath):
        client_etag = request.headers.get('If-None-Match', None)
        if client_etag is None:
            return False

        server_value = self.get(filepath)
        if server_value is None:
            return False

        server_etag = server_value.get_etag()
        if client_etag != server_etag:
            return False

        return server_value.get_headers()

class CacheFile:
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
