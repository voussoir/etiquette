'''
This file is the WSGI entrypoint for remote / production use.

If you are using Gunicorn, for example:
gunicorn etiquette_flask_entrypoint:site --bind "0.0.0.0:PORT" --access-logfile "-"
'''
import sys

import etiquette_flask
import werkzeug.contrib.fixers

etiquette_flask.site.wsgi_app = werkzeug.contrib.fixers.ProxyFix(etiquette_flask.site.wsgi_app)

site = etiquette_flask.site
