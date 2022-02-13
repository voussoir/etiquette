'''
This file is the gevent launcher for local / development use.
'''
import gevent.monkey; gevent.monkey.patch_all()

import argparse
import gevent.pywsgi
import os
import sys

from voussoirkit import betterhelp
from voussoirkit import pathclass
from voussoirkit import vlogging

log = vlogging.getLogger(__name__, 'etiquette_flask_dev')

import etiquette
import backend

site = backend.site
site.debug = True

HTTPS_DIR = pathclass.Path(__file__).parent.with_child('https')

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
        backend.common.init_photodb()
    except etiquette.exceptions.NoClosestPhotoDB as exc:
        log.error(exc.error_message)
        log.error('Try `etiquette_cli.py init` to create the database.')
        return 1

    message = f'Starting server on port {port}, pid={os.getpid()}.'
    if use_https:
        message += ' (https)'
    log.info(message)

    try:
        http.serve_forever()
    except KeyboardInterrupt:
        log.info('Goodbye')
        return 0

def etiquette_flask_launch_argparse(args):
    return etiquette_flask_launch(
        localhost_only=args.localhost_only,
        port=args.port,
        use_https=args.use_https,
    )

@vlogging.main_decorator
def main(argv):
    parser = argparse.ArgumentParser(
        description='''
        This file is the gevent launcher for local / development use.
        ''',
    )
    parser.add_argument(
        'port',
        nargs='?',
        type=int,
        default=5000,
        help='''
        Port number on which to run the server.
        ''',
    )
    parser.add_argument(
        '--https',
        dest='use_https',
        action='store_true',
        help='''
        If this flag is not passed, HTTPS will automatically be enabled if the port
        is 443. You can pass this flag to enable HTTPS on other ports.
        We expect to find etiquette.key and etiquette.crt in
        frontends/etiquette_flask/https.
        ''',
    )
    parser.add_argument(
        '--localhost_only',
        '--localhost-only',
        action='store_true',
        help='''
        If this flag is passed, only localhost will be able to access the server.
        Other users on the LAN will be blocked.
        ''',
    )
    parser.set_defaults(func=etiquette_flask_launch_argparse)

    return betterhelp.go(parser, argv)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
