import argparse
import sys

from voussoirkit import getpermission
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

# HELPERS ##########################################################################################

def get_photos_from_args(args):
    photos = []
    if args.photo_id_args:
        photos.extend(photodb.get_photos_by_id(args.photo_id_args))

    if args.photo_search_args:
        photos.extend(search_by_argparse(args.photo_search_args, yield_photos=True))

    return photos

def get_albums_from_args(args):
    albums = []
    if args.album_id_args:
        albums.extend(photodb.get_albums_by_id(args.album_id_args))

    if args.album_search_args:
        albums.extend(search_by_argparse(args.album_search_args, yield_albums=True))

    return albums

def search_in_cwd(**kwargs):
    photodb = find_photodb()
    cwd = pathclass.cwd()
    return photodb.search(
        within_directory=cwd,
        **kwargs,
    )

def search_by_argparse(args, yield_albums=False, yield_photos=False):
    return search_in_cwd(
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
        limit=args.limit,
        offset=args.offset,
        orderby=args.orderby,
        yield_albums=yield_albums,
        yield_photos=yield_photos,
    )

####################################################################################################

def add_tag_argparse(args):
    photodb = find_photodb()

    tag = photodb.get_tag(name=args.tag_name)
    if args.photo_id_args or args.photo_search_args:
        photos = get_photos_from_args(args)
    else:
        photos = search_in_cwd()

    for photo in photos:
        photo.add_tag(tag)

    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def digest_directory_argparse(args):
    directory = pathclass.Path(args.directory)
    photodb = find_photodb()
    digest = photodb.digest_directory(
        directory,
        make_albums=args.make_albums,
        recurse=args.recurse,
        new_photo_ratelimit=args.ratelimit,
        yield_albums=True,
        yield_photos=True,
    )
    for result in digest:
        print(result)

    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def easybake_argparse(args):
    photodb = find_photodb()
    for eb_string in args.eb_strings:
        notes = photodb.easybake(eb_string)

    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def init_argparse(args):
    photodb = etiquette.photodb.PhotoDB('.', create=True)
    photodb.commit()

def purge_deleted_photos_argparse(args):
    photodb = find_photodb()
    for deleted in photodb.purge_deleted_files():
        print(deleted)
    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def purge_empty_albums_argparse(args):
    photodb = find_photodb()
    for deleted in photodb.purge_empty_albums():
        print(deleted)

    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def search_argparse(args):
    photos = search_by_argparse(args, yield_photos=True)
    photos = sorted(photos, key=lambda p: p.real_path)
    for photo in photos:
        print(photo.real_path.absolute_path)

def set_unset_searchhidden_argparse(args, searchhidden):
    photodb = find_photodb()

    if args.photo_search_args:
        args.photo_search_args.is_searchhidden = not searchhidden

    if args.album_search_args:
        args.album_search_args.is_searchhidden = not searchhidden

    photos = get_photos_from_args(args)
    albums = get_albums_from_args(args)
    photos.extend(photo for album in albums for photo in album.walk_photos())

    for photo in photos:
        print(photo)
        photo.set_searchhidden(searchhidden)

    if args.autoyes or getpermission.getpermission('Commit?'):
        photodb.commit()

def tag_breplace_argparse(args):
    photodb = find_photodb()
    renames = []
    tag_names = photodb.get_all_tag_names()
    all_names = tag_names.union(photodb.get_all_synonyms())
    for tag_name in tag_names:
        if args.regex:
            new_name = re.sub(args.replace_from, args.replace_to, tag_name)
        else:
            new_name = tag_name.replace(args.replace_from, args.replace_to)
        new_name = photodb.normalize_tagname(new_name)
        if new_name == tag_name:
            continue

        if new_name in all_names:
            raise etiquette.exceptions.TagExists(new_name)

        if args.set_synonym:
            printline = f'{tag_name} -> {new_name}+{tag_name}'
        else:
            printline = f'{tag_name} -> {new_name}'

        renames.append((tag_name, new_name, printline))

    if not args.autoyes:
        for (tag_name, new_name, printline) in renames:
            print(printline)
        if not getpermission.getpermission('Ok?', must_pick=True):
            return

    for (tag_name, new_name, printline) in renames:
        print(printline)
        tag = photodb.get_tag(tag_name)
        tag.rename(new_name)
        if args.set_synonym:
            tag.add_synonym(tag_name)
    photodb.commit()

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers()

    primary_args = []
    photo_id_args = []
    photo_search_args = []
    album_id_args = []
    album_search_args = []
    mode = primary_args
    for arg in argv:
        if 0:
            pass
        elif arg in {'--search', '--photo_search', '--photo-search'}:
            mode = photo_search_args
        elif arg in {'--album_search', '--album-search'}:
            mode = album_search_args
        elif arg == '--photos':
            mode = photo_id_args
        elif arg == '--albums':
            mode = album_id_args
        else:
            mode.append(arg)

    p_add_tag = subparsers.add_parser('add_tag', aliases=['add-tag'])
    p_add_tag.add_argument('tag_name')
    p_add_tag.add_argument('--yes', dest='autoyes', action='store_true')
    p_add_tag.set_defaults(func=add_tag_argparse)

    p_easybake = subparsers.add_parser('easybake')
    p_easybake.add_argument('eb_strings', nargs='+')
    p_easybake.add_argument('--yes', dest='autoyes', action='store_true')
    p_easybake.set_defaults(func=easybake_argparse)

    p_digest = subparsers.add_parser('digest', aliases=['digest_directory', 'digest-directory'])
    p_digest.add_argument('directory')
    p_digest.add_argument('--no_albums', '--no-albums', dest='make_albums', action='store_false', default=True)
    p_digest.add_argument('--ratelimit', dest='ratelimit', type=float, default=0.2)
    p_digest.add_argument('--no_recurse', '--no-recurse', dest='recurse', action='store_false', default=True)
    p_digest.add_argument('--yes', dest='autoyes', action='store_true')
    p_digest.set_defaults(func=digest_directory_argparse)


    p_init = subparsers.add_parser('init', aliases=['create'])
    p_init.set_defaults(func=init_argparse)

    p_purge_deleted_photos = subparsers.add_parser('purge_deleted_photos', aliases=['purge-deleted-photos'])
    p_purge_deleted_photos.add_argument('--yes', dest='autoyes', action='store_true')
    p_purge_deleted_photos.set_defaults(func=purge_deleted_photos_argparse)

    p_purge_empty_albums = subparsers.add_parser('purge_empty_albums', aliases=['purge-empty-albums'])
    p_purge_empty_albums.add_argument('--yes', dest='autoyes', action='store_true')
    p_purge_empty_albums.set_defaults(func=purge_empty_albums_argparse)

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

    p_set_searchhidden = subparsers.add_parser('set_searchhidden', aliases=['set-searchhidden'])
    p_set_searchhidden.add_argument('--yes', dest='autoyes', action='store_true')
    p_set_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=True))

    p_unset_searchhidden = subparsers.add_parser('unset_searchhidden', aliases=['unset-searchhidden'])
    p_unset_searchhidden.add_argument('--yes', dest='autoyes', action='store_true')
    p_unset_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=False))

    p_tag_breplace = subparsers.add_parser('tag_breplace')
    p_tag_breplace.add_argument('replace_from')
    p_tag_breplace.add_argument('replace_to')
    p_tag_breplace.add_argument('--set_synonym', '--set-synonym', dest='set_synonym', action='store_true')
    p_tag_breplace.add_argument('--regex', dest='regex', action='store_true')
    p_tag_breplace.add_argument('--yes', dest='autoyes', action='store_true')
    p_tag_breplace.set_defaults(func=tag_breplace_argparse)

    ##

    args = parser.parse_args(primary_args)

    photo_search_args = p_search.parse_args(photo_search_args) if photo_search_args else None
    album_search_args = p_search.parse_args(album_search_args) if album_search_args else None
    photo_id_args = [id for arg in photo_id_args for id in etiquette.helpers.comma_space_split(arg)]
    album_id_args = [id for arg in album_id_args for id in etiquette.helpers.comma_space_split(arg)]

    args.photo_search_args = photo_search_args
    args.album_search_args = album_search_args
    args.photo_id_args = photo_id_args
    args.album_id_args = album_id_args

    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
