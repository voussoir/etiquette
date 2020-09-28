import argparse
import sys

from voussoirkit import pathclass

import etiquette

class CantFindPhotoDB(Exception):
    pass

photodbs = {}

def find_photodb():
    path = pathclass.cwd()

    while True:
        try:
            return photodbs[path]
        except KeyError:
            pass
        if path.with_child('_etiquette').is_dir:
            break
        if path == path.parent:
            raise CantFindPhotoDB()
        path = path.parent
    photodb = etiquette.photodb.PhotoDB(path.with_child('_etiquette'), create=False)
    photodbs[path] = photodb
    return photodb

####################################################################################################

def search_by_argparse(args, yield_albums=False, yield_photos=False):
    photodb = find_photodb()
    cwd = pathclass.cwd()
    results = photodb.search(
        area=args.area,
        width=args.width,
        height=args.height,
        ratio=args.ratio,
        bytes=args.bytes,
        duration=args.duration,
        author=args.author,
        created=args.created,
        extension=args.extension,
        extension_not=args.extension_not,
        filename=args.filename,
        has_tags=args.has_tags,
        has_thumbnail=args.has_thumbnail,
        is_searchhidden=args.is_searchhidden,
        mimetype=args.mimetype,
        tag_musts=args.tag_musts,
        tag_mays=args.tag_mays,
        tag_forbids=args.tag_forbids,
        tag_expression=args.tag_expression,
        within_directory=cwd,
        limit=args.limit,
        offset=args.offset,
        orderby=args.orderby,
        yield_albums=yield_albums,
        yield_photos=yield_photos,
    )
    return results

def search_argparse(args):
    photos = search_by_argparse(args, yield_photos=True)
    photos = sorted(photos, key=lambda p: p.real_path)
    for photo in photos:
        print(photo.real_path.absolute_path)

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers()

    primary_args = []
    photo_search_args = []
    album_search_args = []
    mode = primary_args
    for arg in argv:
        if arg in {'--search', '--photo_search', '--photo-search'}:
            mode = photo_search_args
            continue
        if arg in {'--album_search', '--album-search'}:
            mode = album_search_args
            continue
        mode.append(arg)

    p_search = subparsers.add_parser('search')
    p_search.add_argument('--area', dest='area', default=None)
    p_search.add_argument('--width', dest='width', default=None)
    p_search.add_argument('--height', dest='height', default=None)
    p_search.add_argument('--ratio', dest='ratio', default=None)
    p_search.add_argument('--bytes', dest='bytes', default=None)
    p_search.add_argument('--duration', dest='duration', default=None)
    p_search.add_argument('--author', dest='author', default=None)
    p_search.add_argument('--created', dest='created', default=None)
    p_search.add_argument('--extension', dest='extension', default=None)
    p_search.add_argument('--extension_not', '--extension-not', dest='extension_not', default=None)
    p_search.add_argument('--filename', dest='filename', default=None)
    p_search.add_argument('--has_tags', '--has-tags', dest='has_tags', default=None)
    p_search.add_argument('--has_thumbnail', '--has-thumbnail', dest='has_thumbnail', default=None)
    p_search.add_argument('--is_searchhidden', '--is-searchhidden', dest='is_searchhidden', default=False)
    p_search.add_argument('--mimetype', dest='mimetype', default=None)
    p_search.add_argument('--tag_musts', '--tag-musts', dest='tag_musts', default=None)
    p_search.add_argument('--tag_mays', '--tag-mays', dest='tag_mays', default=None)
    p_search.add_argument('--tag_forbids', '--tag-forbids', dest='tag_forbids', default=None)
    p_search.add_argument('--tag_expression', '--tag-expression', dest='tag_expression', default=None)
    p_search.add_argument('--limit', dest='limit', default=None)
    p_search.add_argument('--offset', dest='offset', default=None)
    p_search.add_argument('--orderby', dest='orderby', default=None)
    # p_search.add_argument('--yield_albums', '--yield-albums', dest='yield_albums', default=None)
    p_search.set_defaults(func=search_argparse)

    args = parser.parse_args(primary_args)
    if photo_search_args:
        args.photo_search_args = p_search.parse_args(photo_search_args)
    else:
        args.photo_search_args = None

    if album_search_args:
        args.album_search_args = p_search.parse_args(album_search_args)
    else:
        args.album_search_args = None

    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
