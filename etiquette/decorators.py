import functools
import time
import warnings

from . import exceptions


def _get_relevant_photodb(instance):
    from . import objects
    if isinstance(instance, objects.ObjectBase):
        photodb = instance.photodb
    else:
        photodb = instance
    return photodb

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
            photodb = _get_relevant_photodb(self)
            config = photodb.config['enable_feature']

            # Using the received string like "photo.new", try to navigate the
            # config and wind up at a True.
            # Allow KeyErrors to raise themselves.
            for feature in features:
                cfg = config
                pieces = feature.split('.')
                for piece in pieces:
                    cfg = cfg[piece]
                if cfg is False:
                    raise exceptions.FeatureDisabled(method.__qualname__)
                if cfg is not True:
                    raise ValueError('Bad required_feature "%s" led to %s' % (feature, cfg))

            return method(self, *args, **kwargs)
        return wrapped_required_feature
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
    '''
    Open a savepoint before running the method.
    If the method fails, roll back to that savepoint.
    '''
    @functools.wraps(method)
    def wrapped_transaction(self, *args, **kwargs):
        photodb = _get_relevant_photodb(self)
        savepoint_id = photodb.savepoint()
        try:
            result = method(self, *args, **kwargs)
        except Exception as e:
            photodb.rollback(savepoint=savepoint_id)
            raise
        else:
            return result
    return wrapped_transaction
