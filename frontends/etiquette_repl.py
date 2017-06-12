# Use with
# py -i etiquette_easy.py

import etiquette
import os
import sys

P = etiquette.photodb.PhotoDB()
import traceback

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

def photag(photoid):
    photo = P.get_photo_by_id(photoid)
    print(photo.tags())
    while True:
        photo.add_tag(input('> '))
get=P.get_tag
