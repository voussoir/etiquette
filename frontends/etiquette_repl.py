import argparse
import code
import sys
import traceback

from voussoirkit import interactive
from voussoirkit import pipeable
from voussoirkit import vlogging

import etiquette

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

################################################################################

def erepl_argparse(args):
    global P

    try:
        P = etiquette.photodb.PhotoDB.closest_photodb()
    except etiquette.exceptions.NoClosestPhotoDB as exc:
        pipeable.stderr(exc.error_message)
        pipeable.stderr('Try `etiquette_cli.py init` to create the database.')
        return 1

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
            if interactive.getpermission():
                break

@vlogging.main_decorator
def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('--exec', dest='exec_statement', default=None)
    parser.set_defaults(func=erepl_argparse)

    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
