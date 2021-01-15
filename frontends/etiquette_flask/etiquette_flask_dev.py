'''
This file is the gevent launcher for local / development use.

Simply run it on the command line:
python etiquette_flask_dev.py [port]
'''
import gevent.monkey; gevent.monkey.patch_all()

import logging
handler = logging.StreamHandler()
log_format = '{levelname}:etiquette.{module}.{funcName}: {message}'
handler.setFormatter(logging.Formatter(log_format, style='{'))
logging.getLogger().addHandler(handler)

import argparse
import gevent.pywsgi
import os
import sys

from voussoirkit import pathclass
from voussoirkit import pipeable
from voussoirkit import vlogging

import etiquette
import backend

site = backend.site

HTTPS_DIR = pathclass.Path(__file__).parent.with_child('https')
LOG_LEVEL = vlogging.NOTSET

####################################################################################################

def etiquette_flask_launch(
        *,
        localhost_only,
        port,
        use_https,
    ):
    if use_https is None:
        use_https = port == 443

    if use_https:
        http = gevent.pywsgi.WSGIServer(
            listener=('0.0.0.0', port),
            application=site,
            keyfile=HTTPS_DIR.with_child('etiquette.key').absolute_path,
            certfile=HTTPS_DIR.with_child('etiquette.crt').absolute_path,
        )
    else:
        http = gevent.pywsgi.WSGIServer(
            listener=('0.0.0.0', port),
            application=site,
        )

    if localhost_only:
        site.localhost_only = True

    try:
        backend.common.init_photodb(log_level=LOG_LEVEL)
    except etiquette.exceptions.NoClosestPhotoDB as exc:
        pipeable.stderr(exc.error_message)
        pipeable.stderr('Try `etiquette_cli.py init` to create the database.')
        return 1

    message = f'Starting server on port {port}, pid={os.getpid()}'
    if use_https:
        message += ' (https)'
    print(message)

    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass

def etiquette_flask_launch_argparse(args):
    return etiquette_flask_launch(
        localhost_only=args.localhost_only,
        port=args.port,
        use_https=args.use_https,
    )

def main(argv):
    global LOG_LEVEL
    (LOG_LEVEL, argv) = vlogging.get_level_by_argv(argv)

    parser = argparse.ArgumentParser()

    parser.add_argument('port', nargs='?', type=int, default=5000)
    parser.add_argument('--https', dest='use_https', action='store_true', default=None)
    parser.add_argument('--localhost_only', '--localhost-only', dest='localhost_only', action='store_true')
    parser.set_defaults(func=etiquette_flask_launch_argparse)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
