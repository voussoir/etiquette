import gevent.monkey
gevent.monkey.patch_all()

import logging
handler = logging.StreamHandler()
log_format = '{levelname}:etiquette.{module}.{funcName}: {message}'
handler.setFormatter(logging.Formatter(log_format, style='{'))
logging.getLogger().addHandler(handler)

import etiquette_flask
import gevent.pywsgi
import gevent.wsgi
import sys


import werkzeug.contrib.fixers
etiquette_flask.site.wsgi_app = werkzeug.contrib.fixers.ProxyFix(etiquette_flask.site.wsgi_app)


if len(sys.argv) >= 2:
    port = int(sys.argv[1])
else:
    port = 5000

use_https = (port == 443) or ('--https' in sys.argv)
if use_https:
    http = gevent.pywsgi.WSGIServer(
        listener=('0.0.0.0', port),
        application=etiquette_flask.site,
        keyfile='D:\\git\\etiquette\\frontends\\etiquette_flask\\https\\etiquette.key',
        certfile='D:\\git\\etiquette\\frontends\\etiquette_flask\\https\\etiquette.crt',
    )
else:
    http = gevent.pywsgi.WSGIServer(
        listener=('0.0.0.0', port),
        application=etiquette_flask.site,
    )


message = 'Starting server on port %d' % port
if use_https:
    message += ' (https)'
print(message)
http.serve_forever()
