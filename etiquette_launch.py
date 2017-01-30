import gevent.monkey
gevent.monkey.patch_all()

import etiquette
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
        application=etiquette.site,
        keyfile='C:\\git\\etiquette\\etiquette\\https\\etiquette.key',
        certfile='C:\\git\\etiquette\\etiquette\\https\\etiquette.crt',
    )
else:
    http = gevent.pywsgi.WSGIServer(
        listener=('0.0.0.0', port),
        application=etiquette.site,
    )


print('Starting server on port %d' % port)
http.serve_forever()
