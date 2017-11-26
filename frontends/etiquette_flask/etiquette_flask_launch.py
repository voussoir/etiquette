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

if len(sys.argv) == 2:
    port = int(sys.argv[1])
else:
    port = 5000

if port == 443:
    http = gevent.pywsgi.WSGIServer(
        listener=('0.0.0.0', port),
        application=etiquette_flask.site,
        keyfile='C:\\git\\etiquette\\etiquette\\https\\etiquette.key',
        certfile='C:\\git\\etiquette\\etiquette\\https\\etiquette.crt',
    )
else:
    http = gevent.pywsgi.WSGIServer(
        listener=('0.0.0.0', port),
        application=etiquette_flask.site,
    )


print('Starting server on port %d' % port)
http.serve_forever()
