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

            if not all(config[key] for key in features):
                raise exceptions.FeatureDisabled(function.__name__)

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
            print(e)
            self.sql.rollback()
            raise
    return wrapped
