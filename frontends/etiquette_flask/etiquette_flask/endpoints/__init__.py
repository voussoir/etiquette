import flask; from flask import request
import random

from . import album_endpoints
from . import basic_endpoints
from . import bookmark_endpoints
from . import common
from . import photo_endpoints
from . import tag_endpoints
from . import user_endpoints

site = common.site


if __name__ == '__main__':
    #site.run(threaded=True)
    pass
