'''
This file is the gevent launcher for local / development use.

Simply run it on the command line:
python etiquette_flask_launch.py [port]
'''
import gevent.monkey; gevent.monkey.patch_all()

import logging
handler = logging.StreamHandler()
log_format = '{levelname}:etiquette.{module}.{funcName}: {message}'
handler.setFormatter(logging.Formatter(log_format, style='{'))
logging.getLogger().addHandler(handler)

import argparse
import gevent.pywsgi
import sys

import etiquette_flask_entrypoint

site = etiquette_flask_entrypoint.site

def run(port=None, use_https=None):
    if port is None:
        port = 5000
    else:
        port = int(port)

    if use_https is None:
        use_https = port == 443

    if use_https:
        http = gevent.pywsgi.WSGIServer(
            listener=('0.0.0.0', port),
            application=site,
            keyfile='D:\\git\\etiquette\\frontends\\etiquette_flask\\https\\etiquette.key',
            certfile='D:\\git\\etiquette\\frontends\\etiquette_flask\\https\\etiquette.crt',
        )
    else:
        http = gevent.pywsgi.WSGIServer(
            listener=('0.0.0.0', port),
            application=site,
        )

    message = f'Starting server on port {port}'
    if use_https:
        message += ' (https)'
    print(message)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

def run_argparse(args):
    return run(port=args.port, use_https=args.use_https)

def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument(dest='port', nargs='?', default=None)
    parser.add_argument('--https', dest='use_https', action='store_true', default=None)
    parser.set_defaults(func=run_argparse)

    args = parser.parse_args(argv)
    args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
