'''
This file is the WSGI entrypoint for remote / production use.

If you are using Gunicorn, for example:
gunicorn etiquette_flask_prod:site --bind "0.0.0.0:PORT" --access-logfile "-"
'''
import werkzeug.middleware.proxy_fix

from voussoirkit import pathclass

from etiquette_flask import backend

backend.site.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(backend.site.wsgi_app)

site = backend.site
site.debug = False

backend.common.init_photodb(path=pathclass.cwd())
