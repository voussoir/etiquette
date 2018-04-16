import sys

import etiquette_flask
import werkzeug.contrib.fixers

etiquette_flask.site.wsgi_app = werkzeug.contrib.fixers.ProxyFix(etiquette_flask.site.wsgi_app)

site = etiquette_flask.site
