import functools
import time
import warnings

from . import exceptions

def _get_relevant_photodb(instance):
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
                    raise exceptions.FeatureDisabled(feature)

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

def transaction(method):
    '''
    Open a savepoint before running the method.
    If the method fails, roll back to that savepoint.
    '''
    @functools.wraps(method)
    def wrapped_transaction(self, *args, **kwargs):
        if isinstance(self, objects.ObjectBase):
            self.assert_not_deleted()

        photodb = _get_relevant_photodb(self)

        commit = kwargs.pop('commit', False)
        is_root = len(photodb.savepoints) == 0

        savepoint_id = photodb.savepoint(message=method.__qualname__)

        try:
            result = method(self, *args, **kwargs)
        except Exception as exc:
            photodb.log.debug(f'{method} raised {repr(exc)}.')
            photodb.rollback(savepoint=savepoint_id)
            raise

        if commit:
            photodb.commit(message=method.__qualname__)
        elif not is_root:
            photodb.release_savepoint(savepoint=savepoint_id)
        return result

    return wrapped_transaction

# Circular dependency.
# I would like to un-circularize this, but as long as objects and photodb are
# using the same decorators, and the decorator needs to follow the photodb
# instance of the object...
# I'd rather not create separate decorators, or write hasattr-based decisions.
from . import objects
