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

DOCSTRING = '''
Etiquette CLI
=============

This is the command-line interface for Etiquette, so that you can automate your
database and integrate it into other scripts.

-- DATABASE --------------------------------------------------------------------

{init}

-- ALBUMS ----------------------------------------------------------------------

{delete_albums}

{export_symlinks}

{purge_empty_albums}

{show_associated_directories}

-- PHOTOS ----------------------------------------------------------------------

{add_tag}

{delete_photos}

{digest}

{export_symlinks}

{generate_thumbnail}

{purge_deleted_files}

{reload_metadata}

{relocate}

{remove_tag}

{search}

{set_searchhidden}

{unset_searchhidden}

-- TAGS ------------------------------------------------------------------------

{easybake}

{tag_breplace}

{tag_list}

--------------------------------------------------------------------------------

You can add --yes to avoid the "Commit?" prompt on commands that modify the db.

TO SEE DETAILS ON EACH COMMAND, RUN
> etiquette_cli.py <command> --help
'''

SUB_DOCSTRINGS = dict(
add_tag='''
add_tag:
    Add a tag to photos by a filename glob or by search results.

    > etiquette_cli.py add_tag tag_name glob_patterns
    > etiquette_cli.py add_tag tag_name --search searchargs

    Examples:
    > etiquette_cli.py add_tag wallpaper wall*.jpg wall*.png
    > etiquette_cli.py add_tag author.author_voussoir --search --tag-forbids author

    See etiquette_cli.py search --help for more info about searchargs.
''',

remove_tag='''
remove_tag:
    Remove a tag from photos by a filename glob or by search results.

    > etiquette_cli.py remove_tag tag_name glob_patterns
    > etiquette_cli.py remove_tag tag_name --search searchargs

    Examples:
    > etiquette_cli.py remove_tag watchlist spongebob*.mp4
    > etiquette_cli.py remove_tag watchlist --search --tag-musts directed_by_michael_bay

    See etiquette_cli.py search --help for more info about searchargs.
''',

delete_albums='''
delete_albums:
    Remove albums from the database.

    > etiquette_cli.py delete_albums --albums id id id
    > etiquette_cli.py delete_albums --album-search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

delete_photos='''
delete_photos:
    Remove photos from the database.

    flags:
    --delete_file:
        Delete the file from disk after committing.
        Your config.json file's recycle_instead_of_delete will influence this.
        Without this flag, photos are removed from the db but remain on disk.

    > etiquette_cli.py delete_photos --photos id id id
    > etiquette_cli.py delete_photos --search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

digest='''
digest:
    Digest a directory, adding new files as Photos into the database.

    > etiquette_cli.py digest directory <flags>

    flags:
    --exclude_directories A B C:
        Any directories matching any pattern of A, B, C... will be skipped.
        These patterns may be absolute paths like 'D:\\temp', plain names like
        'thumbnails' or glob patterns like 'build_*'.

    --exclude_filenames A B C:
        Any filenames matching any pattern of A, B, C... will be skipped.
        These patterns may be absolute paths like 'D:\\somewhere\\config.json',
        plain names like 'thumbs.db' or glob patterns like '*.temp'.

    --glob_directories A B C:
        Only directories matching any pattern of A, B, C... will be digested.
        These patterns may be plain names or glob patterns like '2021*'

    --glob_filenames A B C:
        Only filenames matching any pattern of A, B, C... will be digested.
        These patterns may be plain names or glob patterns like '*.jpg'

    --no_albums:
        Do not create any albums. By default, albums are created and nested to
        match the directory structure.

    --ratelimit X:
        Limit the ingest of new Photos to only one per X seconds. This can be
        used to reduce system load or to make sure that two photos don't get the
        same `created` timestamp.

    --no_recurse:
        Do not recurse into subdirectories. Only create Photos from files in
        the current directory.

    Examples:
    > etiquette_cli.py digest media --ratelimit 1
    > etiquette_cli.py digest photos --no-recurse --no-albums --ratelimit 0.25
    > etiquette_cli.py digest . --glob-filenames *.jpg --exclude-filenames thumb*
''',

easybake='''
easybake:
    Create and manipulate tags by easybake strings.

    > etiquette_cli.py easybake eb_string
''',

export_symlinks='''
export_symlinks:
    Search for photos or albums, then create symlinks pointing to the results.

    THIS IS STILL A BIT EXPERIMENTAL.
    This can be used to gather up search results for the purpose of further
    uploading, transfering, etc. with other applications.
    Symlinks point to files (if result is a photo) or directories (if result is
    an album with an associated directory).
    Albums are limited to only one associated directory since the output
    symlink can't point to two places at once.

    > etiquette_cli.py export_symlinks --destination directory --search searchargs
    > etiquette_cli.py export_symlinks --destination directory --album-search searchargs

    flags:
    --destination X:
        A path to a directory into which the symlinks will be placed.

    --dry:
        Print the results without actually creating the symlinks.

    --prune:
        In the destination directory, any existing symlinks whose target no
        longer exists will be deleted.

    See etiquette_cli.py search --help for more info about searchargs.
''',

generate_thumbnail='''
generate_thumbnail:
    Generate thumbnails for photos.

    With no args, all files under the cwd will be thumbnailed.
    Or, you can pass specific photo ids or searchargs.

    > etiquette_cli.py generate_thumbnail
    > etiquette_cli.py generate_thumbnail --photos id id id
    > etiquette_cli.py generate_thumbnail --search searchargs

    Examples:
    > etiquette_cli.py generate_thumbnail --search --has-thumbnail no

    See etiquette_cli.py search --help for more info about searchargs.
''',

init='''
init:
    Create a new Etiquette database in the current directory.

    > etiquette_cli.py init
''',

purge_deleted_files='''
purge_deleted_files:
    Delete any Photo objects whose file no longer exists on disk.

    > etiquette_cli.py purge_deleted_files
    > etiquette_cli.py purge_deleted_files --photos id id id
    > etiquette_cli.py purge_deleted_files --search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

purge_empty_albums='''
purge_empty_albums:
    Delete any albums which have no child albums or photos.

    Consider running purge_deleted_files first, so that albums containing
    deleted files will get cleared out and then caught by this function.

    With no args, all albums will be checked.
    Or you can pass specific album ids. (searchargs is not available since
    albums only appear in search results when a matching photo is found, and
    we're looking for albums with no photos!)

    > etiquette_cli.py purge_empty_albums
    > etiquette_cli.py purge_empty_albums --albums id id id
''',

reload_metadata='''
reload_metadata:
    Reload photos' metadata by reading the files from disk.

    With no args, all files under the cwd will be reloaded.
    Or, you can pass specific photo ids or searchargs.

    > etiquette_cli.py reload_metadata
    > etiquette_cli.py reload_metadata --photos id id id
    > etiquette_cli.py reload_metadata --search searchargs

    flags:
    --force:
        By default, we wil skip any files that have the same mtime and byte
        size as before. You can pass --force to always reload.

    --hash_bytes_per_second X:
        A string like "10mb" to limit the speed of file hashing for the purpose
        of reducing system load.

    See etiquette_cli.py search --help for more info about searchargs.
''',

relocate='''
relocate:
    Change a photo's filepath. Used for updating photos that have been changed
    by external tools.

    > etiquette_cli.py relocate photo_id filepath
''',

search='''
search:
    Search for photos and albums with complex operators.

    > etiquette_cli.py search searchargs
    > etiquette_cli.py search --album-search searchargs

    Searchargs:
    --area X-Y:
        Photo/video width*height between X and Y.

    --width X-Y:
        Photo/video width between X and Y.

    --height X-Y:
        Photo/video height between X and Y.

    --ratio X-Y:
        Photo/video aspect ratio between X and Y.

    --bytes X-Y:
        File size in bytes between X and Y.

    --duration X-Y:
        Media duration between X and Y seconds.

    --author X:
        Photo authored by user with username X.

    --created X-Y:
        Photo creation date between X and Y unix timestamp.

    --extension A,B,C:
        Photo with any extension of A, B, C...

    --extension_not A,B,C:
        Photo without any extension of A, B, C...

    --filename X:
        Search terms for Photo's filename.

    --has_tags yes/no/null:
        If yes, Photo must have at least one tag.
        If no, Photo must have no tags.
        If null, doesn't matter.

    --has_thumbnail yes/no/null:

    --is_searchhidden yes/no/null:

    --mimetype A,B,C:
        Photo with any mimetype of A, B, C...

    --sha256 A,B,C:
        Photo with any sha256 of A, B, C...

    --tag_musts A,B,C:
        Photo must have all tags A and B and C...

    --tag_mays A,B,C:
        Photo must have at least one tag of A, B, C...

    --tag_forbids A,B,C:
        Photo must not have any tags of A, B, C...

    --tag_expression X:
        Complex expression string to match tags.

    --limit X:
        Limit results to first X items.

    --offset X:
        Skip the first X items.

    --orderby X-Y:
        Order the results by property X in direction Y. E.g. created-desc or
        bytes-asc.
''',

show_associated_directories='''
show_associated_directories:
    Show the associated directories for albums.

    > etiquette_cli.py show_associated_directories
    > etiquette_cli.py show_associated_directories --albums id id id
    > etiquette_cli.py show_associated_directories --album-search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

set_searchhidden='''
set_searchhidden:
    Mark photos as searchhidden.

    > etiquette_cli.py set_searchhidden --photos id id id
    > etiquette_cli.py set_searchhidden --search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

unset_searchhidden='''
unset_searchhidden:
    Unmark photos as searchhidden.

    > etiquette_cli.py unset_searchhidden --photos id id id
    > etiquette_cli.py unset_searchhidden --search searchargs

    See etiquette_cli.py search --help for more info about searchargs.
''',

tag_breplace='''
tag_breplace:
    For all tags in the database, use find-and-replace to rename the tags.

    > etiquette_cli.py tag_breplace replace_from replace_to
''',

tag_list='''
tag_list:
    Show all tags in the database.

    > etiquette_cli.py tag_list
''',
)

DOCSTRING = betterhelp.add_previews(DOCSTRING, SUB_DOCSTRINGS)

@vlogging.main_decorator
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
    p_add_tag.add_argument('globs', nargs='*')
    p_add_tag.add_argument('--yes', dest='autoyes', action='store_true')
    p_add_tag.set_defaults(func=lambda args: add_remove_tag_argparse(args, action='add'))

    p_remove_tag = subparsers.add_parser('remove_tag', aliases=['remove-tag'])
    p_remove_tag.add_argument('tag_name')
    p_remove_tag.add_argument('globs', nargs='*')
    p_remove_tag.add_argument('--yes', dest='autoyes', action='store_true')
    p_remove_tag.set_defaults(func=lambda args: add_remove_tag_argparse(args, action='remove'))

    p_delete_albums = subparsers.add_parser('delete_albums', aliases=['delete-albums'])
    p_delete_albums.add_argument('--yes', dest='autoyes', action='store_true')
    p_delete_albums.set_defaults(func=delete_albums_argparse)

    p_delete_photos = subparsers.add_parser('delete_photos', aliases=['delete-photos'])
    p_delete_photos.add_argument('--delete_file', '--delete-file', action='store_true')
    p_delete_photos.add_argument('--yes', dest='autoyes', action='store_true')
    p_delete_photos.set_defaults(func=delete_photos_argparse)

    p_digest = subparsers.add_parser('digest', aliases=['digest_directory', 'digest-directory'])
    p_digest.add_argument('directory')
    p_digest.add_argument('--exclude_directories', '--exclude-directories', nargs='+', default=None)
    p_digest.add_argument('--exclude_filenames', '--exclude-filenames', nargs='+', default=None)
    p_digest.add_argument('--glob_directories', '--glob-directories', nargs='+', default=None)
    p_digest.add_argument('--glob_filenames', '--glob-filenames', nargs='+', default=None)
    p_digest.add_argument('--no_albums', '--no-albums', dest='make_albums', action='store_false', default=True)
    p_digest.add_argument('--ratelimit', dest='ratelimit', type=float, default=0.2)
    p_digest.add_argument('--no_recurse', '--no-recurse', dest='recurse', action='store_false', default=True)
    p_digest.add_argument('--hash_bytes_per_second', '--hash-bytes-per-second', default=None)
    p_digest.add_argument('--yes', dest='autoyes', action='store_true')
    p_digest.set_defaults(func=digest_directory_argparse)

    p_easybake = subparsers.add_parser('easybake')
    p_easybake.add_argument('eb_strings', nargs='+')
    p_easybake.add_argument('--yes', dest='autoyes', action='store_true')
    p_easybake.set_defaults(func=easybake_argparse)

    p_export_symlinks = subparsers.add_parser('export_symlinks', aliases=['export-symlinks'])
    p_export_symlinks.add_argument('--destination', dest='destination', required=True)
    p_export_symlinks.add_argument('--dry', dest='dry_run', action='store_true')
    p_export_symlinks.add_argument('--prune', dest='prune', action='store_true')
    p_export_symlinks.set_defaults(func=export_symlinks_argparse)

    p_generate_thumbnail = subparsers.add_parser('generate_thumbnail', aliases=['generate-thumbnail'])
    p_generate_thumbnail.add_argument('--yes', dest='autoyes', action='store_true')
    p_generate_thumbnail.set_defaults(func=generate_thumbnail_argparse)

    p_init = subparsers.add_parser('init', aliases=['create'])
    p_init.set_defaults(func=init_argparse)

    p_purge_deleted_files = subparsers.add_parser('purge_deleted_files', aliases=['purge-deleted-files'])
    p_purge_deleted_files.add_argument('--yes', dest='autoyes', action='store_true')
    p_purge_deleted_files.set_defaults(func=purge_deleted_files_argparse)

    p_purge_empty_albums = subparsers.add_parser('purge_empty_albums', aliases=['purge-empty-albums'])
    p_purge_empty_albums.add_argument('--yes', dest='autoyes', action='store_true')
    p_purge_empty_albums.set_defaults(func=purge_empty_albums_argparse)

    p_reload_metadata = subparsers.add_parser('reload_metadata', aliases=['reload-metadata'])
    p_reload_metadata.add_argument('globs', nargs='*')
    p_reload_metadata.add_argument('--hash_bytes_per_second', '--hash-bytes-per-second', default=None)
    p_reload_metadata.add_argument('--force', action='store_true')
    p_reload_metadata.add_argument('--yes', dest='autoyes', action='store_true')
    p_reload_metadata.set_defaults(func=reload_metadata_argparse)

    p_relocate = subparsers.add_parser('relocate')
    p_relocate.add_argument('photo_id')
    p_relocate.add_argument('filepath')
    p_relocate.add_argument('--yes', dest='autoyes', action='store_true')
    p_relocate.set_defaults(func=relocate_argparse)

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
    p_search.add_argument('--sha256', default=None)
    p_search.add_argument('--mimetype', dest='mimetype', default=None)
    p_search.add_argument('--tag_musts', '--tag-musts', dest='tag_musts', default=None)
    p_search.add_argument('--tag_mays', '--tag-mays', dest='tag_mays', default=None)
    p_search.add_argument('--tag_forbids', '--tag-forbids', dest='tag_forbids', default=None)
    p_search.add_argument('--tag_expression', '--tag-expression', dest='tag_expression', default=None)
    p_search.add_argument('--limit', dest='limit', default=None)
    p_search.add_argument('--offset', dest='offset', default=None)
    p_search.add_argument('--orderby', dest='orderby', default='basename-ASC')
    # p_search.add_argument('--yield_albums', '--yield-albums', dest='yield_albums', default=None)
    p_search.set_defaults(func=search_argparse)

    p_show_associated_directories = subparsers.add_parser('show_associated_directories', aliases=['show-associated-directories'])
    p_show_associated_directories.set_defaults(func=show_associated_directories_argparse)

    p_set_searchhidden = subparsers.add_parser('set_searchhidden', aliases=['set-searchhidden'])
    p_set_searchhidden.add_argument('--yes', dest='autoyes', action='store_true')
    p_set_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=True))

    p_unset_searchhidden = subparsers.add_parser('unset_searchhidden', aliases=['unset-searchhidden'])
    p_unset_searchhidden.add_argument('--yes', dest='autoyes', action='store_true')
    p_unset_searchhidden.set_defaults(func=lambda args: set_unset_searchhidden_argparse(args, searchhidden=False))

    p_tag_breplace = subparsers.add_parser('tag_breplace', aliases=['tag-breplace'])
    p_tag_breplace.add_argument('replace_from')
    p_tag_breplace.add_argument('replace_to')
    p_tag_breplace.add_argument('--set_synonym', '--set-synonym', dest='set_synonym', action='store_true')
    p_tag_breplace.add_argument('--regex', dest='regex', action='store_true')
    p_tag_breplace.add_argument('--yes', dest='autoyes', action='store_true')
    p_tag_breplace.set_defaults(func=tag_breplace_argparse)

    p_tag_list = subparsers.add_parser('tag_list', aliases=['tag-list'])
    p_tag_list.set_defaults(func=tag_list_argparse)

    ##

    def postprocessor(args):
        args.photo_search_args = p_search.parse_args(photo_search_args) if photo_search_args else None
        args.album_search_args = p_search.parse_args(album_search_args) if album_search_args else None
        args.photo_id_args = [id for arg in photo_id_args for id in stringtools.comma_space_split(arg)]
        args.album_id_args = [id for arg in album_id_args for id in stringtools.comma_space_split(arg)]

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
        return betterhelp.subparser_main(
            primary_args,
            parser,
            main_docstring=DOCSTRING,
            sub_docstrings=SUB_DOCSTRINGS,
            args_postprocessor=postprocessor,
        )
    except etiquette.exceptions.NoClosestPhotoDB as exc:
        pipeable.stderr(exc.error_message)
        pipeable.stderr('Try `etiquette_cli.py init` to create the database.')
        return 1

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
