import functools
import time
import warnings

from voussoirkit import sentinel

from . import exceptions

NOT_CACHED = sentinel.Sentinel('not cached')

def cache_until_commit(method):
    cache_name = f'_cached_{method.__name__}'
    cache_commit_name = f'_cached_{method.__name__}_commit_id'

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        use_cache = (
            getattr(self, cache_name, NOT_CACHED) is not NOT_CACHED and
            getattr(self, cache_commit_name, NOT_CACHED) == self._photodb.last_commit_id
        )
        if use_cache:
            return getattr(self, cache_name)
        value = method(self, *args, **kwargs)
        setattr(self, cache_name, value)
        setattr(self, cache_commit_name, self._photodb.last_commit_id)
        return value
    return wrapped

def required_feature(features):
    '''
    Declare that the photodb or object method requires certain 'enable_*'
    fields in the config.
    '''
    if isinstance(features, str):
        features = [features]

    def wrapper(method):
        @functools.wraps(method)
        def wrapped_required_feature(self, *args, **kwargs):
            photodb = self._photodb
            config = photodb.config['enable_feature']

            # Using the received string like "photo.new", try to navigate the
            # config and wind up at a True or False. All other values invalid.
            # Allow KeyErrors to raise themselves.
            for feature in features:
                cfg = config
                pieces = feature.split('.')
                for piece in pieces:
                    cfg = cfg[piece]

                if cfg is True:
                    pass

                elif cfg is False:
                    raise exceptions.FeatureDisabled(requires=feature)

                else:
                    raise ValueError(f'Bad required_feature: "{feature}" led to {cfg}.')

            return method(self, *args, **kwargs)
        return wrapped_required_feature
    return wrapper

def not_implemented(function):
    '''
    Decorator to remember what needs doing.
    '''
    warnings.warn(f'{function.__name__} is not implemented')
    return function

def time_me(function):
    '''
    After the function is run, print the elapsed time.
    '''
    @functools.wraps(function)
    def timed_function(*args, **kwargs):
        start = time.time()
        result = function(*args, **kwargs)
        end = time.time()
        duration = end - start
        print(f'{function.__name__}: {duration:0.8f}')
        return result
    return timed_function
