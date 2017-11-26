# Use with
# py -i etiquette_easy.py

import logging
handler = logging.StreamHandler()
log_format = '{levelname}:etiquette.{module}.{funcName}: {message}'
handler.setFormatter(logging.Formatter(log_format, style='{'))
logging.getLogger().addHandler(handler)

import argparse
import os
import sys
import traceback

import etiquette

P = etiquette.photodb.PhotoDB()

def easytagger():
    while True:
        i = input('> ')
        if i.startswith('?'):
            i = i.split('?')[1] or None
            try:
                etiquette.tag_export.stdout([P.get_tag(i)])
            except:
                traceback.print_exc()
        else:
            P.easybake(i)

def photag(photo_id):
    photo = P.get_photo_by_id(photo_id)
    print(photo.tags())
    while True:
        photo.add_tag(input('> '))
get = P.get_tag


def erepl_argparse(args):
    if args.exec_statement:
        exec(args.exec_statement)

def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('--exec', dest='exec_statement', default=None)
    parser.set_defaults(func=erepl_argparse)

    args = parser.parse_args(argv)
    args.func(args)

if __name__ == '__main__':
    main(sys.argv[1:])
