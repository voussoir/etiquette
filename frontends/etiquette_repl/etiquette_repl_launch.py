import logging
handler = logging.StreamHandler()
log_format = '{levelname}:etiquette.{module}.{funcName}: {message}'
handler.setFormatter(logging.Formatter(log_format, style='{'))
logging.getLogger().addHandler(handler)

import argparse
import code
import sys
import traceback

from voussoirkit import getpermission

import etiquette

P = etiquette.photodb.PhotoDB()

def easytagger():
    while True:
        i = input('> ')
        if i.startswith('?'):
            i = i.split('?')[1] or None
            try:
                etiquette.tag_export.stdout([P.get_tag(name=i)])
            except Exception:
                traceback.print_exc()
        else:
            P.easybake(i)

def photag(photo_id):
    photo = P.get_photo_by_id(photo_id)
    print(photo.get_tags())
    while True:
        photo.add_tag(input('> '))

get = P.get_tag

################################################################################
def erepl_argparse(args):
    if args.exec_statement:
        exec(args.exec_statement)
        P.commit()
    else:
        while True:
            try:
                code.interact(banner='', local=dict(globals(), **locals()))
            except SystemExit:
                pass
            if len(P.savepoints) == 0:
                break
            print('You have uncommited changes, are you sure you want to quit?')
            if getpermission.getpermission():
                break

def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('--exec', dest='exec_statement', default=None)
    parser.set_defaults(func=erepl_argparse)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
