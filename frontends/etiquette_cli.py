import argparse
import os
import re
import sys

from voussoirkit import betterhelp
from voussoirkit import interactive
from voussoirkit import pathclass
from voussoirkit import pipeable
from voussoirkit import spinal
from voussoirkit import stringtools
from voussoirkit import vlogging

import etiquette

photodb = None
def load_photodb():
    global photodb
    if photodb is not None:
        return
    photodb = etiquette.photodb.PhotoDB.closest_photodb()

# HELPERS ##########################################################################################

def export_symlinks_albums(albums, destination, dry_run):
    album_directory_names = etiquette.helpers.decollide_names(albums, lambda a: a.display_name)
    for (album, directory_name) in album_directory_names.items():
        associated_directories = album.get_associated_directories()
        if len(associated_directories) == 1:
            album_dir = associated_directories.pop()
            directory_name = etiquette.helpers.remove_path_badchars(directory_name)
            symlink_dir = destination.with_child(directory_name)
            if dry_run:
                yield symlink_dir
                continue
            if not album_dir.exists:
                continue
            if symlink_dir.exists:
                yield symlink_dir
                continue
            print(album, symlink_dir)
            os.symlink(src=album_dir, dst=symlink_dir)
            yield symlink_dir

def export_symlinks_photos(photos, destination, dry_run):
    photo_filenames = etiquette.helpers.decollide_names(photos, lambda p: p.basename)
    for (photo, filename) in photo_filenames.items():
        symlink_path = destination.with_child(filename)
        if dry_run:
            yield symlink_path
            continue
        if not photo.real_path.exists:
            continue
        if symlink_path.exists:
            yield symlink_path
            continue
        print(symlink_path.absolute_path)
        os.symlink(src=photo.real_path, dst=symlink_path)
        yield symlink_path

def get_photos_by_glob(pattern):
    load_photodb()
    pattern = pathclass.normalize_sep(pattern)

    if pattern == '**':
        return search_in_cwd(yield_photos=True, yield_albums=False)

    for file in pathclass.glob_files(pattern):
        try:
            photo = photodb.get_photo_by_path(file)
            yield photo
        except etiquette.exceptions.NoSuchPhoto:
            pass

def get_photos_by_globs(patterns):
    for pattern in patterns:
        yield from get_photos_by_glob(pattern)

def get_photos_from_args(args):
    load_photodb()
    photos = []

    if args.globs:
        photos.extend(get_photos_by_globs(args.globs))

    if args.glob:
        photos.extend(get_photos_by_glob(args.glob))

    if args.photo_id_args:
        photos.extend(photodb.get_photos_by_id(args.photo_id_args))

    if args.photo_search_args:
        photos.extend(search_by_argparse(args.photo_search_args, yield_photos=True))

    return photos

def get_albums_from_args(args):
    load_photodb()
    albums = []

    if args.album_id_args:
        albums.extend(photodb.get_albums_by_id(args.album_id_args))

    if args.album_search_args:
        albums.extend(search_by_argparse(args.album_search_args, yield_albums=True))

    return albums

def search_in_cwd(**kwargs):
    load_photodb()
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
        sha256=args.sha256,
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

# ARGPARSE #########################################################################################

def add_remove_tag_argparse(args, action):
    load_photodb()

    tag = photodb.get_tag_by_name(args.tag_name)

    if args.any_photo_args:
        photos = get_photos_from_args(args)
    else:
        # todo: require the user to provide some photo args, dont implicitly do all under cwd.
        photos = search_in_cwd(yield_photos=True, yield_albums=False)

    need_commit = False

    for photo in photos:
        if action == 'add':
            photo.add_tag(tag)
        elif action == 'remove':
            photo.remove_tag(tag)
        need_commit = True

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def delete_albums_argparse(args):
    load_photodb()

    need_commit = False
    albums = get_albums_from_args(args)
    for album in albums:
        album.delete()
        need_commit = True

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def delete_photos_argparse(args):
    load_photodb()

    need_commit = False
    photos = get_photos_from_args(args)
    for photo in photos:
        photo.delete(delete_file=args.delete_file)
        need_commit = True

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def digest_directory_argparse(args):
    directories = pipeable.input(args.directory, strip=True, skip_blank=True)
    directories = [pathclass.Path(d) for d in directories]
    for directory in directories:
        directory.assert_is_directory()

    load_photodb()
    need_commit = False

    for directory in directories:
        digest = photodb.digest_directory(
            directory,
            exclude_directories=args.exclude_directories,
            exclude_filenames=args.exclude_filenames,
            glob_directories=args.glob_directories,
            glob_filenames=args.glob_filenames,
            hash_kwargs={'bytes_per_second': args.hash_bytes_per_second},
            make_albums=args.make_albums,
            new_photo_ratelimit=args.ratelimit,
            recurse=args.recurse,
            yield_albums=True,
            yield_photos=True,
        )
        for result in digest:
            # print(result)
            need_commit = True

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def easybake_argparse(args):
    load_photodb()
    for eb_string in args.eb_strings:
        notes = photodb.easybake(eb_string)
        for (action, tagname) in notes:
            print(action, tagname)

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def export_symlinks_argparse(args):
    destination = pathclass.Path(args.destination)
    destination.makedirs(exist_ok=True)

    total_paths = set()

    if args.any_album_args:
        albums = get_albums_from_args(args)
        export = export_symlinks_albums(
            albums,
            destination,
            dry_run=args.dry_run,
        )
        total_paths.update(export)

    if args.any_photo_args:
        photos = get_photos_from_args(args)
        export = export_symlinks_photos(
            photos,
            destination,
            dry_run=args.dry_run,
        )
        total_paths.update(export)

    if not args.prune or args.dry_run:
        return 0

    symlinks = spinal.walk(destination, yield_directories=True, yield_files=True)
    symlinks = set(path for path in symlinks if path.is_link)
    symlinks = symlinks.difference(total_paths)
    for old_symlink in symlinks:
        print(f'Pruning {old_symlink}.')
        os.remove(old_symlink)
        if not old_symlink.parent.listdir():
            os.rmdir(old_symlink.parent)

    checkdirs = set(spinal.walk(destination, yield_directories=True, yield_files=False))
    while checkdirs:
        check = checkdirs.pop()
        if check not in destination:
            continue
        if len(check.listdir()) == 0:
            os.rmdir(check)
            checkdirs.add(check.parent)

    return 0

def generate_thumbnail_argparse(args):
    load_photodb()

    if args.any_photo_args:
        photos = get_photos_from_args(args)
    else:
        photos = search_in_cwd(yield_photos=True, yield_albums=False)

    need_commit = False
    try:
        for photo in photos:
            photo.generate_thumbnail()
            need_commit = True
    except KeyboardInterrupt:
        pass

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def init_argparse(args):
    photodb = etiquette.photodb.PhotoDB(create=True)
    photodb.commit()
    return 0

def purge_deleted_files_argparse(args):
    load_photodb()

    if args.any_photo_args:
        photos = get_photos_from_args(args)
    else:
        photos = search_in_cwd(yield_photos=True, yield_albums=False)

    need_commit = False

    for deleted in photodb.purge_deleted_files(photos):
        need_commit = True
        print(deleted)

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def purge_empty_albums_argparse(args):
    load_photodb()

    # We do not check args.album_search_args because currently it is not
    # possible for search results to find empty albums on account of the fact
    # that albums are only yielded when they contain some result photo.
    if args.album_id_args:
        albums = get_albums_from_args(args)
    else:
        albums = photodb.get_albums_within_directory(pathclass.cwd())

    need_commit = False

    for deleted in photodb.purge_empty_albums(albums):
        need_commit = True
        print(deleted)

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def reload_metadata_argparse(args):
    load_photodb()

    if args.any_photo_args:
        photos = get_photos_from_args(args)
    else:
        photos = search_in_cwd(yield_photos=True, yield_albums=False)

    hash_kwargs = {
        'bytes_per_second': args.hash_bytes_per_second,
        'callback_progress': spinal.callback_progress_v1,
    }

    need_commit = False
    try:
        for photo in photos:
            if not photo.real_path.is_file:
                continue

            need_reload = (
                args.force or
                photo.mtime != photo.real_path.stat.st_mtime or
                photo.bytes != photo.real_path.stat.st_size
            )

            if not need_reload:
                continue
            photo.reload_metadata(hash_kwargs=hash_kwargs)
            need_commit = True
    except KeyboardInterrupt:
        pass

    if not need_commit:
        return 0

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def relocate_argparse(args):
    load_photodb()

    photo = photodb.get_photo(args.photo_id)
    photo.relocate(args.filepath)

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def search_argparse(args):
    photos = search_by_argparse(args, yield_photos=True)
    for photo in photos:
        print(photo.real_path.absolute_path)

    return 0

def show_associated_directories_argparse(args):
    if args.any_album_args:
        albums = get_albums_from_args(args)
    else:
        albums = search_in_cwd(yield_photos=False, yield_albums=True)

    for album in albums:
        directories = album.get_associated_directories()
        if not directories:
            continue
        directories = [f'"{d.absolute_path}"' for d in directories]
        directories = ' '.join(directories)
        print(f'{album} | {directories}')

    return 0

def set_unset_searchhidden_argparse(args, searchhidden):
    load_photodb()

    if args.photo_search_args:
        args.photo_search_args.is_searchhidden = not searchhidden

    if args.album_search_args:
        args.album_search_args.is_searchhidden = not searchhidden

    photos = []
    if args.any_photo_args:
        photos.extend(get_photos_from_args(args))
    if args.any_album_args:
        albums = get_albums_from_args(args)
        photos.extend(photo for album in albums for photo in album.walk_photos())
    else:
        photos = search_in_cwd(yield_photos=True, yield_albums=False)

    for photo in photos:
        print(photo)
        photo.set_searchhidden(searchhidden)

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def tag_breplace_argparse(args):
    load_photodb()
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
        if not interactive.getpermission('Ok?', must_pick=True):
            return 0

    for (tag_name, new_name, printline) in renames:
        print(printline)
        tag = photodb.get_tag(tag_name)
        tag.rename(new_name)
        if args.set_synonym:
            tag.add_synonym(tag_name)

    if args.autoyes or interactive.getpermission('Commit?'):
        photodb.commit()

    return 0

def tag_list_argparse(args):
    load_photodb()
    tags = photodb.get_all_tag_names()
    synonyms = photodb.get_all_synonyms()
    keys = sorted(tags.union(synonyms.keys()))
    for key in keys:
        if key in synonyms:
            print(f'{key}={synonyms[key]}')
        else:
            print(key)

    return 0

@vlogging.main_decorator
def main(argv):
    parser = argparse.ArgumentParser(
        description='''
        This is the command-line interface for Etiquette, so that you can automate your
        database and integrate it into other scripts.
        ''',
    )
    subparsers = parser.add_subparsers()

    ################################################################################################

    p_add_tag = subparsers.add_parser(
        'add_tag',
        aliases=['add-tag'],
        description='''
        Add a tag to photos by a filename glob or by search results.
        ''',
    )
    p_add_tag.examples = [
        'wallpaper wall*.jpg wall*.png',
        {'args': 'author.voussoir --photo-search --tag-forbids author', 'comment': 'Add an author tag to all photos that don\'t have one.'}
    ]
    p_add_tag.add_argument(
        'tag_name',
    )
    p_add_tag.add_argument(
        'globs',
        nargs='*',
        help='''
        Select Photos by using glob patterns that match files.
        ''',
    )
    p_add_tag.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to tag.
        ''',
    )
    p_add_tag.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to tag. See search --help for help.
        ''',
    )
    p_add_tag.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_add_tag.set_defaults(func=lambda args: add_remove_tag_argparse(args, action='add'))

    ################################################################################################

    p_remove_tag = subparsers.add_parser(
        'remove_tag',
        aliases=['remove-tag'],
        description='''
        Remove a tag from photos by a filename glob or by search results.
        ''',
    )
    p_remove_tag.examples = [
        'watchlist spongebob*.mp4',
        'watchlist --photo-search --tag-musts directed_by_michael_bay',
    ]
    p_remove_tag.add_argument(
        'tag_name',
    )
    p_remove_tag.add_argument(
        'globs',
        nargs='*',
        help='''
        Select Photos by using glob patterns that match files.
        ''',
    )
    p_remove_tag.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to untag.
        ''',
    )
    p_remove_tag.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to untag. See search --help for help.
        ''',
    )
    p_remove_tag.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_remove_tag.set_defaults(func=lambda args: add_remove_tag_argparse(args, action='remove'))

    ################################################################################################

    p_delete_albums = subparsers.add_parser(
        'delete_albums',
        aliases=['delete-albums'],
        description='''
        Remove albums from the database.
        ''',
    )
    p_delete_albums.add_argument(
        '--albums',
        dest='album_id_args',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Albums to delete.
        ''',
    )
    p_delete_albums.add_argument(
        '--album_search',
        '--album-search',
        dest='album_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Albums to delete. See search --help for help.
        ''',
    )
    p_delete_albums.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_delete_albums.set_defaults(func=delete_albums_argparse)

    ################################################################################################

    p_delete_photos = subparsers.add_parser(
        'delete_photos',
        aliases=['delete-photos'],
        description='''
        Remove photos from the database.
        ''',
    )
    p_delete_photos.add_argument(
        'globs',
        nargs='*',
        help='''
        Select Photos by using glob patterns that match files.
        ''',
    )
    p_delete_photos.add_argument(
        '--delete_file',
        '--delete-file',
        action='store_true',
        help='''
        Delete the file from disk after committing.
        Your config.json file's recycle_instead_of_delete will influence this.
        Without this flag, photos are removed from the db but remain on disk.
        ''',
    )
    p_delete_photos.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to delete.
        ''',
    )
    p_delete_photos.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to delete. See search --help for help.
        ''',
    )
    p_delete_photos.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_delete_photos.set_defaults(func=delete_photos_argparse)

    ################################################################################################

    p_digest = subparsers.add_parser(
        'digest',
        aliases=['digest_directory', 'digest-directory'],
        description='''
        Digest a directory, adding new files as Photos and folders as Albums into
        the database.
        ''',
    )
    p_digest.examples = [
        'media --ratelimit 1',
        'photos --no-recurse --no-albums --ratelimit 0.25',
        '. --glob-filenames *.jpg --exclude-filenames thumb*',
    ]
    p_digest.add_argument(
        'directory',
    )
    p_digest.add_argument(
        '--exclude_directories',
        '--exclude-directories',
        metavar='pattern',
        nargs='+',
        default=None,
        help='''
        Any directories matching any of these patterns will be skipped.
        These patterns may be absolute paths like 'D:\\temp', plain names like
        'thumbnails' or glob patterns like 'build_*'.
        ''',
    )
    p_digest.add_argument(
        '--exclude_filenames',
        '--exclude-filenames',
        metavar='pattern',
        nargs='+',
        default=None,
        help='''
        Any filenames matching any of these patterns will be skipped.
        These patterns may be absolute paths like 'D:\\somewhere\\config.json',
        plain names like 'thumbs.db' or glob patterns like '*.temp'.
        ''',
    )
    p_digest.add_argument(
        '--glob_directories',
        '--glob-directories',
        metavar='pattern',
        nargs='+',
        default=None,
        help='''
        Only directories matching any of these patterns will be digested.
        These patterns may be plain names or glob patterns like '2021*'
        ''',
    )
    p_digest.add_argument(
        '--glob_filenames',
        '--glob-filenames',
        metavar='pattern',
        nargs='+',
        default=None,
        help='''
        Only filenames matching any of these patterns will be digested.
        These patterns may be plain names or glob patterns like '*.jpg'
        ''',
    )
    p_digest.add_argument(
        '--no_albums',
        '--no-albums',
        dest='make_albums',
        action='store_false',
        default=True,
        help='''
        Do not create any albums. By default, albums are created and nested to
        match the directory structure.
        ''',
    )
    p_digest.add_argument(
        '--ratelimit',
        dest='ratelimit',
        type=float,
        default=0.2,
        help='''
        Limit the ingest of new Photos to only one per this many seconds. This
        can be used to reduce system load or to make sure that two photos don't
        get the same `created` timestamp.
        ''',
    )
    p_digest.add_argument(
        '--no_recurse',
        '--no-recurse',
        dest='recurse',
        action='store_false',
        default=True,
        help='''
        Do not recurse into subdirectories. Only create Photos from files in
        the current directory. By default, we traverse all subdirectories except
        those excluded by --exclude-directories.
        ''',
    )
    p_digest.add_argument(
        '--hash_bytes_per_second',
        '--hash-bytes-per-second',
        metavar='bytes',
        default=None,
        help='''
        Limit the speed of file hashing. This can be used to reduce system load.
        ''',
    )
    p_digest.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_digest.set_defaults(func=digest_directory_argparse)

    ################################################################################################

    p_easybake = subparsers.add_parser(
        'easybake',
        description='''
        Create and manipulate tags by easybake strings.
        ''',
    )
    p_easybake.examples = [
        'people.family.parents.mother+mom',
        'watchlist=to_watch',
    ]
    p_easybake.add_argument(
        'eb_strings',
        nargs='+',
        help='''
        One or more easybake strings. Easybake strings work like this:
        Every tag name is implicitly created if it does not already exist.
        Dot '.' is used to make hierarchies.
        Plus '+' is used to make synonyms.
        Equals '=' is used to rename tags.
        ''',
    )
    p_easybake.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_easybake.set_defaults(func=easybake_argparse)

    ################################################################################################

    p_export_symlinks = subparsers.add_parser(
        'export_symlinks',
        aliases=['export-symlinks'],
        description='''
        Search for photos or albums, then create symlinks pointing to the results.

        THIS IS STILL A BIT EXPERIMENTAL.
        This can be used to gather up search results for the purpose of further
        uploading, transfering, etc. with other applications.
        Symlinks point to files (if result is a photo) or directories (if result is
        an album with an associated directory).
        Albums are limited to only one associated directory since the output
        symlink can't point to two places at once.
        ''',
    )
    p_export_symlinks.add_argument(
        '--destination',
        dest='destination',
        required=True,
        help='''
        A path to a directory into which the symlinks will be placed.
        ''',
    )
    p_export_symlinks.add_argument(
        '--dry',
        dest='dry_run',
        action='store_true',
        help='''
        Print the results without actually creating the symlinks.
        ''',
    )
    p_export_symlinks.add_argument(
        '--prune',
        dest='prune',
        action='store_true',
        help='''
        In the destination directory, any existing symlinks whose target no
        longer exists will be deleted.
        ''',
    )
    p_export_symlinks.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to export.
        ''',
    )
    p_export_symlinks.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to export. See search --help for help.
        ''',
    )
    p_export_symlinks.add_argument(
        '--albums',
        dest='album_id_args',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Albums to export.
        ''',
    )
    p_export_symlinks.add_argument(
        '--album_search',
        '--album-search',
        dest='album_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Albums to export. See search --help for help.
        ''',
    )
    p_export_symlinks.set_defaults(func=export_symlinks_argparse)

    ################################################################################################

    p_generate_thumbnail = subparsers.add_parser(
        'generate_thumbnail',
        aliases=['generate-thumbnail'],
        description='''
        Generate thumbnails for photos.
        ''',
    )
    p_generate_thumbnail.examples = [
        '--photo-search --has-thumbnail no',
    ]
    p_generate_thumbnail.add_argument(
        'globs',
        nargs='*',
        help='''
        Select Photos by using glob patterns that match files.
        ''',
    )
    p_generate_thumbnail.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to thumbnail.
        ''',
    )
    p_generate_thumbnail.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to thumbnail. See search --help for help.
        ''',
    )
    p_generate_thumbnail.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_generate_thumbnail.set_defaults(func=generate_thumbnail_argparse)

    ################################################################################################

    p_init = subparsers.add_parser(
        'init',
        aliases=['create'],
        description='''
        Create a new Etiquette database in the current directory.
        ''',
    )
    p_init.set_defaults(func=init_argparse)

    ################################################################################################

    p_purge_deleted_files = subparsers.add_parser(
        'purge_deleted_files',
        aliases=['purge-deleted-files'],
        description='''
        Delete any Photo objects whose file no longer exists on disk.

        When --photos and --photo-search are not passed, all photos under the cwd
        and subdirectories will be checked.
        ''',
    )
    p_purge_deleted_files.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to purge,
        if eligible.
        ''',
    )
    p_purge_deleted_files.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to purge, if eligible. See search --help for help.
        ''',
    )
    p_purge_deleted_files.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_purge_deleted_files.set_defaults(func=purge_deleted_files_argparse)

    ################################################################################################

    p_purge_empty_albums = subparsers.add_parser(
        'purge_empty_albums',
        aliases=['purge-empty-albums'],
        description='''
        Delete any albums which have no child albums or photos.

        Consider running purge_deleted_files first, so that albums containing
        deleted files will get cleared out and then caught by this function.

        With no args, all albums will be checked.
        Or you can pass specific album ids. (--album-search is not available since
        albums only appear in search results when a matching photo is found, and
        we're looking for albums with no photos!)
        ''',
    )
    p_purge_empty_albums.add_argument(
        '--albums',
        dest='album_id_args',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Albums to purge,
        if eligible.
        ''',
    )
    p_purge_empty_albums.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_purge_empty_albums.set_defaults(func=purge_empty_albums_argparse)

    ################################################################################################

    p_reload_metadata = subparsers.add_parser(
        'reload_metadata',
        aliases=['reload-metadata'],
        description='''
        Reload photos' metadata by reading the files from disk.
        ''',
    )
    p_reload_metadata.add_argument(
        'globs',
        nargs='*',
        help='''
        Select Photos by using glob patterns that match files.
        ''',
    )
    p_reload_metadata.add_argument(
        '--hash_bytes_per_second',
        '--hash-bytes-per-second',
        default=None,
        help='''
        A string like "10mb" to limit the speed of file hashing for the purpose
        of reducing system load.
        ''',
    )
    p_reload_metadata.add_argument(
        '--force',
        action='store_true',
        help='''
        By default, we wil skip any files that have the same mtime and byte
        size as before. You can pass --force to always reload.
        ''',
    )
    p_reload_metadata.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to reload.
        ''',
    )
    p_reload_metadata.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to reload. See search --help for help.
        ''',
    )
    p_reload_metadata.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_reload_metadata.set_defaults(func=reload_metadata_argparse)

    ################################################################################################

    p_relocate = subparsers.add_parser(
        'relocate',
        description='''
        Update a photo's filepath in the database. This does not actually move
        the file there, rather it is used for updating photos that have already
        been moved by external tools.
        ''',
    )
    p_relocate.add_argument(
        'photo_id',
    )
    p_relocate.add_argument(
        'filepath',
    )
    p_relocate.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_relocate.set_defaults(func=relocate_argparse)

    ################################################################################################

    p_search = subparsers.add_parser(
        'search',
        description='''
        Search for photos and albums with complex operators. Many other commands
        can use search arguments to pick which Photos / Albums to process.
        ''',
    )
    p_search.add_argument(
        '--area',
        metavar='X-Y',
        default=None,
        help='''
        Photo/video width*height between X and Y.
        ''',
    )
    p_search.add_argument(
        '--width',
        metavar='X-Y',
        default=None,
        help='''
        Photo/video width between X and Y.
        ''',
    )
    p_search.add_argument(
        '--height',
        metavar='X-Y',
        default=None,
        help='''
        Photo/video height between X and Y.
        ''',
    )
    p_search.add_argument(
        '--ratio',
        metavar='X-Y',
        default=None,
        help='''
        Photo/video aspect ratio between X and Y.
        ''',
    )
    p_search.add_argument(
        '--bytes',
        metavar='X-Y',
        default=None,
        help='''
        File size in bytes between X and Y.
        ''',
    )
    p_search.add_argument(
        '--duration',
        metavar='X-Y',
        default=None,
        help='''
        Media duration between X and Y seconds.
        ''',
    )
    p_search.add_argument(
        '--author',
        metavar='A,B,C',
        default=None,
        help='''
        Photo authored by user A, B, or C...
        ''',
    )
    p_search.add_argument(
        '--created',
        metavar='X-Y',
        default=None,
        help='''
        Photo creation date between X and Y unix timestamp.
        ''',
    )
    p_search.add_argument(
        '--extension',
        metavar='A,B,C',
        default=None,
        help='''
        Photo with any extension of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--extension_not',
        '--extension-not',
        metavar='A,B,C',
        default=None,
        help='''
        Photo without any extension of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--filename',
        default=None,
        help='''
        Search for strings within Photos' filenames.
        ''',
    )
    p_search.add_argument(
        '--has_tags',
        '--has-tags',
        default=None,
        help='''
        If "yes", Photo must have at least one tag.
        If "no", Photo must have no tags.
        If "null", doesn't matter.
        ''',
    )
    p_search.add_argument(
        '--has_thumbnail',
        '--has-thumbnail',
        default=None,
        help='''
        If "yes", Photo must have a thumbnail.
        If "no", Photo must not have a thumbnail.
        If "null", doesn't matter.
        ''',
    )
    p_search.add_argument(
        '--is_searchhidden',
        '--is-searchhidden',
        default=False,
        help='''
        If "yes", Photo must be searchhidden.
        If "no", Photo must not be searchhidden.
        If "null", doesn't matter.
        ''',
    )
    p_search.add_argument(
        '--sha256',
        metavar='A,B,C',
        default=None,
        help='''
        Photo with any sha256 of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--mimetype',
        metavar='A,B,C',
        default=None,
        help='''
        Photo with any mimetype of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--tag_musts',
        '--tag-musts',
        metavar='A,B,C',
        default=None,
        help='''
        Photo must have all tags A and B and C...
        ''',
    )
    p_search.add_argument(
        '--tag_mays',
        '--tag-mays',
        metavar='A,B,C',
        default=None,
        help='''
        Photo must have at least one tag of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--tag_forbids',
        '--tag-forbids',
        metavar='A,B,C',
        default=None,
        help='''
        Photo must not have any tags of A, B, C...
        ''',
    )
    p_search.add_argument(
        '--tag_expression',
        '--tag-expression',
        default=None,
        help='''
        Complex expression string to match tags.
        ''',
    )
    p_search.add_argument(
        '--limit',
        default=None,
        help='''
        Limit results to first X items.
        ''',
    )
    p_search.add_argument(
        '--offset',
        default=None,
        help='''
        Skip the first X items.
        ''',
    )
    p_search.add_argument(
        '--orderby',
        dest='orderby',
        default='basename-ASC',
        help='''
        Order the results by property X in direction Y. E.g. created-desc or
        bytes-asc.
        ''',
    )
    p_search.add_argument(
        '--album_search',
        '--album-search',
        dest='album_search_args',
        nargs='...',
        help='''
        Search for albums instead of photos.
        ''',
    )
    p_search.set_defaults(func=search_argparse)

    ################################################################################################

    p_show_associated_directories = subparsers.add_parser(
        'show_associated_directories',
        aliases=['show-associated-directories'],
        description='''
        Show the associated directories for albums.
        ''',
    )
    p_show_associated_directories.add_argument(
        '--albums',
        dest='album_id_args',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Albums to list.
        ''',
    )
    p_show_associated_directories.add_argument(
        '--album_search',
        '--album-search',
        dest='album_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Albums to list. See search --help for help.
        ''',
    )
    p_show_associated_directories.set_defaults(func=show_associated_directories_argparse)

    ################################################################################################

    p_set_searchhidden = subparsers.add_parser(
        'set_searchhidden',
        aliases=['set-searchhidden'],
        description='''
        Mark photos as searchhidden.
        ''',
    )
    p_set_searchhidden.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to set.
        ''',
    )
    p_set_searchhidden.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to set. See search --help for help.
        ''',
    )
    p_set_searchhidden.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_set_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=True))

    ################################################################################################

    p_unset_searchhidden = subparsers.add_parser(
        'unset_searchhidden',
        aliases=['unset-searchhidden'],
        description='''
        Unmark photos as searchhidden.
        ''',
    )
    p_unset_searchhidden.add_argument(
        '--photos',
        dest='photo_id_args',
        metavar='photo_id',
        nargs='...',
        help='''
        All remaining arguments will be treated as IDs of Photos to unset.
        ''',
    )
    p_unset_searchhidden.add_argument(
        '--photo_search',
        '--photo-search',
        dest='photo_search_args',
        nargs='...',
        help='''
        All remaining arguments will go to the search command to generate the
        list of Photos to unset. See search --help for help.
        ''',
    )
    p_unset_searchhidden.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_unset_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=False))

    ################################################################################################

    p_tag_breplace = subparsers.add_parser(
        'tag_breplace',
        aliases=['tag-breplace'],
        description='''
        For all tags in the database, use find-and-replace to rename the tags.
        ''',
    )
    p_tag_breplace.add_argument(
        'replace_from',
    )
    p_tag_breplace.add_argument(
        'replace_to',
    )
    p_tag_breplace.add_argument(
        '--set_synonym',
        '--set-synonym',
        dest='set_synonym',
        action='store_true',
        help='''
        After renaming the tag, assign the old name as a synonym to the new one.
        ''',
    )
    p_tag_breplace.add_argument(
        '--regex',
        dest='regex',
        action='store_true',
        help='''
        Treat replace_from and replace_to as regex patterns instead of plain
        strings.
        ''',
    )
    p_tag_breplace.add_argument(
        '--yes',
        dest='autoyes',
        action='store_true',
        help='''
        Commit the database without prompting.
        ''',
    )
    p_tag_breplace.set_defaults(func=tag_breplace_argparse)

    ################################################################################################

    p_tag_list = subparsers.add_parser(
        'tag_list',
        aliases=['tag-list'],
        description='''
        Show all tags in the database.
        ''',
    )
    p_tag_list.set_defaults(func=tag_list_argparse)

    ##

    def postprocessor(args):
        if hasattr(args, 'photo_search_args'):
            args.photo_search_args = p_search.parse_args(args.photo_search_args)
        else:
            args.photo_search_args = None

        if hasattr(args, 'album_search_args'):
            args.album_search_args = p_search.parse_args(args.album_search_args)
        else:
            args.album_search_args = None

        if hasattr(args, 'photo_id_args'):
            args.photo_id_args = [
                photo_id
                for arg in args.photo_id_args
                for photo_id in stringtools.comma_space_split(arg)
            ]
        else:
            args.photo_id_args = None

        if hasattr(args, 'album_id_args'):
            args.album_id_args = [
                album_id
                for arg in args.album_id_args
                for album_id in stringtools.comma_space_split(arg)
            ]
        else:
            args.album_id_args = None


        if not hasattr(args, 'globs'):
            args.globs = None

        if not hasattr(args, 'glob'):
            args.glob = None

        args.any_photo_args = bool(
            args.photo_search_args or
            args.photo_id_args or
            args.globs or
            args.glob
        )
        args.any_album_args = bool(
            args.album_id_args or
            args.album_search_args
        )
        return args

    try:
        return betterhelp.go(parser, argv)
    except etiquette.exceptions.NoClosestPhotoDB as exc:
        pipeable.stderr(exc.error_message)
        pipeable.stderr('Try `etiquette_cli.py init` to create the database.')
        return 1

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
