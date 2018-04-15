import etiquette

import voussoirkit.bytestring

def bytestring(x):
    try:
        return voussoirkit.bytestring.bytestring(x)
    except Exception:
        return '??? b'
