from gevent import monkey
monkey.patch_all()

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
        ('', port),
        etiquette.site,
        keyfile='https\\etiquette.key',
        certfile='https\\etiquette.crt',
    )
else:
    http = gevent.wsgi.WSGIServer(('', port), etiquette.site)

print('Starting server')
http.serve_forever()