'''
This file is the WSGI entrypoint for remote / production use.

If you are using Gunicorn, for example:
gunicorn etiquette_flask_entrypoint:site --bind "0.0.0.0:PORT" --access-logfile "-"
'''
import sys
import werkzeug.contrib.fixers

import backend

backend.site.wsgi_app = werkzeug.contrib.fixers.ProxyFix(backend.site.wsgi_app)

site = backend.site
