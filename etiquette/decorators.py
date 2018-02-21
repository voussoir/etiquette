import functools
import time
import warnings

from . import exceptions


def required_feature(features):
    '''
    Declare that the photodb or object method requires certain 'enable_*'
    fields in the config.
    '''
    from . import objects
    if isinstance(features, str):
        features = [features]

    def wrapper(function):
        @functools.wraps(function)
        def wrapped(self, *args, **kwargs):
            if isinstance(self, objects.ObjectBase):
                config = self.photodb.config
            else:
                config = self.config

            config = config['enable_feature']

            # Using the received string like "photo.new", try to navigate the
            # config and wind up at a True.
            # Allow KeyErrors to raise themselves.
            for feature in features:
                cfg = config
                pieces = feature.split('.')
                for piece in pieces:
                    cfg = cfg[piece]
                if cfg is False:
                    raise exceptions.FeatureDisabled(function.__qualname__)
                if cfg is not True:
                    raise ValueError('Bad required_feature "%s" led to %s' % (feature, cfg))

            return function(self, *args, **kwargs)
        return wrapped
    return wrapper

def not_implemented(function):
    '''
    Decorator to remember what needs doing.
    '''
    warnings.warn('%s is not implemented' % function.__name__)
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
        print('%s: %0.8f' % (function.__name__, end-start))
        return result
    return timed_function

def transaction(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            ret = method(self, *args, **kwargs)
            return ret
        except Exception as e:
            self.log.debug('Rolling back')
            self.sql.rollback()
            raise
    return wrapped
