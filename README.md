Etiquette
=========

I am currently running a read-only demonstration copy of Etiquette at https://etiquette.voussoir.net where you can browse around.

## What am I looking at

Etiquette is a tag-based file organization system with a web interface, built with Flask and SQLite3. Tag-based systems solve problems that a traditional folder hierarchy can't: *which folder should a file go in if it equally belongs in both?* and *how do I make my files searchable without littering the filenames themselves with keywords?*

Etiquette is unique because the tags themselves are hierarchical. By tagging one of your vacation photos with the `family.parents.dad` tag, it will automatically appear in searches for `family.parents` and `family` as well. A traditional folder system, here called albums, is available to bundle files that always belong together without creating a bespoke tag to represent that bundle. Regardless, the files on disk are never modified.

## Setting up

As you'll see below, Etiquette has a core backend package and multiple frontends that use it. These frontend applications will use `import etiquette` to access the backend code. Therefore, the `etiquette` package needs to be in the right place for Python to find it for `import`.

1. Run `pip install -r requirements.txt --upgrade`.

2. Make a new folder somewhere on your computer, and add this folder to your `PYTHONPATH` environment variable. For example, I might use `D:\pythonpath` or `~/pythonpath`. Close and re-open your Command Prompt / Terminal so it reloads the environment variables.

3. Add a symlink to the etiquette folder into that folder:

    The repository you are looking at now is `D:\Git\Etiquette` or `~/Git/Etiquette`. You can see the folder called `etiquette`.

    Windows: `mklink /d fakepath realpath`  
    for example `mklink /d "D:\pythonpath\etiquette" "D:\Git\Etiquette\etiquette"`

    Linux: `ln --symbolic realpath fakepath`  
    for example `ln --symbolic "~/Git/Etiquette/etiquette" "~/pythonpath/etiquette"`

4. Run `python -c "import etiquette; print(etiquette)"` to confirm.

## Running

In order to prevent the accidental creation of Etiquette databases, you must first use `etiquette_cli.py init` to create your database.

### Running Etiquette CLI

1. `cd` to the folder where you'd like to create the Etiquette database.

2. Run `python frontends/etiquette_cli.py --help` to learn about the available commands.

3. Run `python frontends/etiquette_cli.py init` to create a database in the current directory.

Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher. For example:

    Windows:
    D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_cli.py

    Linux:
    /somewhere $ python /Git/Etiquette/frontends/etiquette_cli.py

It is expected that you create a shortcut file or launch script so you don't have to type the whole filepath every time.

### Running Etiquette Flask locally

1. Use `etiquette_cli init` to create the database in the desired directory.

2. Run `python frontends/etiquette_flask/etiquette_flask_dev.py [port]` to launch the flask server. Port defaults to 5000 if not provided.

3. Open your web browser to `localhost:<port>`.

Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher. For example:

    Windows:
    D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_flask\etiquette_flask_dev.py 5001

    Linux:
    /somewhere $ python /Git/Etiquette/frontends/etiquette_flask/etiquette_flask_dev.py 5001

Add `--help` to learn the arguments.

It is expected that you create a shortcut file or launch script so you don't have to type the whole filepath every time.

### Running Etiquette Flask with Gunicorn

You already know that the frontend code imports the backend code. But now, gunicorn needs to import the frontend code.

1. Use `etiquette_cli init` to create the database in the desired directory.

2. Add a symlink to the `frontends/etiquette_flask` folder into the folder you added to your `PYTHONPATH` earlier.

   `ln --symbolic realpath fakepath`  
    for example `ln --symbolic "~/Git/Etiquette/frontends/etiquette_flask" "~/pythonpath/etiquette_flask"`

3. Add a symlink to `frontends/etiquette_flask/etiquette_flask_prod.py` into the folder you added to your `PYTHONPATH`, **or** into the folder from which you will run gunicorn.

   `ln --symbolic realpath fakepath`  
    for example `ln --symbolic "~/Git/Etiquette/frontends/etiquette_flask/etiquette_flask_prod.py" "~/pythonpath/etiquette_flask_prod.py"`

    **or**

    `ln --symbolic "~/Git/Etiquette/frontends/etiquette_flask/etiquette_flask_prod.py" "./etiquette_flask_prod.py"`

    where `./` is the location from which you will run gunicorn.

4. If you are using a proxy like NGINX, make sure you are setting X-Forwarded-For so that Etiquette sees the user's real IP, and not the proxy's own (127.0.0.1) IP. For example:

    ```
    location / {
        ...
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        ...
    }
    ```

5. To run non-daemonized, on a specific port, with logging to the terminal, I use:

    ```
    ~/cmd/python ~/cmd/gunicorn_py etiquette_flask_prod:site --bind "0.0.0.0:6667" --access-logfile "-" --access-logformat "%(h)s | %(t)s | %(r)s | %(s)s %(b)s"
    ```

It is expected that you create a shortcut file or launch script so you don't have to type the whole filepath every time.

### Running Etiquette REPL

1. Use `etiquette_cli init` to create the database in the desired directory.

2. Run `python frontends/etiquette_repl.py` to launch the Python interpreter with the PhotoDB pre-loaded into a variable called `P`. Try things like `P.new_photo` or `P.digest_directory`.

Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher. For example:

    Windows:
    D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_repl.py

    Linux:
    /somewhere $ python /Git/Etiquette/frontends/etiquette_repl.py

It is expected that you create a shortcut file or launch script so you don't have to type the whole filepath every time.

## Basic usage

Let's say you store your photos in `D:\Documents\Photos`, and you want to tag the files with Etiquette. You can get started with these steps:

1. Open a Command Prompt / Terminal. Decide where your Etiquette database will be stored, and `cd` to that location. `cd D:\Documents\Photos` is probably fine.
2. Run `etiquette_cli.py init` to create the database. A folder called `_etiquette` will appear.
3. Run `etiquette_cli.py digest . --ratelimit 1 --glob-filenames *.jpg` to add the files into the database. You can use `etiquette_cli.py digest --help` to learn about this command.
4. Run `etiquette_flask_dev.py 5000` to start the webserver on port 5000.
5. Open your web browser to `localhost:5000` and begin browsing.

## Why does Etiquette hash files?

When adding new files to the database or reloading their metadata, Etiquette will create SHA256 hashes of the files. If you are using Etiquette to organize large media files, this may take a while. I was hesitant to add hashing and incur this slowdown, but the hashes greatly improve Etiquette's ability to detect when a file has been renamed or moved, which is important when you have invested your valuable time into adding tags to them. I hope that the hash time is perceived as a worthwhile tradeoff.

## Maintaining your database with Etiquette CLI

I highly recommend storing batch/bash scripts of your favorite `etiquette_cli` invocations, so that you can quickly sync the database with the state of the disk in the future. Here are some suggestions for what you might like to include in such a script:

- `digest`: Storing all your digest invocations in a single file makes ingesting new files very easy. For your digests, I recommend including `--ratelimit` to stop Photos from having the exact same created timestamp, and `--hash-bytes-per-second` to reduce IO load. In addition, you don't want to forget your favorite `--glob-filenames` patterns.
- `reload-metadata`: In order for Etiquette's hash-based rename detection to work properly, the file hashes need to be up to date. If you're using Etiquette to track files which may be modified, you may want to get in the habit of reloading metadata regularly. By default, this will only reload metadata for files whose mtime and/or byte size have changed, so it should not be very expensive. You may add `--hash-bytes-per-second` to reduce IO load.
- `purge-deleted-files` & `purge-empty-albums`: You should only do this after a `digest`, because if a file has been moved / renamed you want the digest to pick up on that before purging it as a dead filepath. The Photo purge should come first, so that an album containing entirely deleted photos will be empty when it comes time for the Album purge.

## Project stability

You may notice that Etiquette doesn't have a version number anywhere. That's because I don't think it's ready for one. I am using this project to learn and practice, and breaking changes are very common.

## Project structure

Here is a brief overview of the project to help you learn your way around:

- `etiquette`  
    The core backend package.
    - `objects`  
        Definition of the Etiquette data objects like Photos and Tags.
    - `photodb`  
        Definition of the PhotoDB class and its Mixins.
- `frontends`  
    The Etiquette library is designed to be usable through a variety of interfaces. The Flask interface is my primary focus and does, admittedly, have an influence on the design of the backend, but other interfaces should have no trouble integrating with Etiquette. Every folder here is essentially a completely separate project which imports etiquette just like any other dependency.
    - `etiquette_flask`  
        Runs a web server which you can visit in your browser. There is a basic account system, but it is not ready to be used as a public service. You'll notice that my demo site has all editing disabled.
    - `etiquette_repl`  
        Preloads a few variables into the interpreter so you can quickly test functions within the Python REPL itself.
    - `etiquette_cli`  
        To be run on the command line for fast and scriptable search & ingest.
- `utilities`  
    For other scripts that will be used with etiquette databases, but are not part of the library itself.

## To do list

- Make the wording between "new", "create", "add"; and "remove", "delete" more consistent.
- User account system, permission levels, private pages.
- Replace columns like area, ratio, bitrate by using expression indices or views (`width * height` etc).
- Add a `Photo.merge` to combine duplicate entries.
- Generate thumbnails for vector files without falling victim to bombs.
- Allow photos to have nonstandard, orderby-able properties like "release year". How?
- Currently, the Jinja templates are having a tangling influence on the backend objects, because Jinja cannot import my other modules like bytestring, but it can access the methods of the objects I pass into the template. As a result, the objects have excess helper methods. Consider making them into Jinja filters instead. Which is also kind of ugly but will move that pollution out of the backend at least.
- Perhaps instead of actually deleting objects, they should just have a `deleted` flag, to make easy restoration possible. Also consider regrouping the children of restored Groupables if those children haven't already been reassigned somewhere else.
- Add a new table to store permanent history of add/remove of tags on photos, so that accidents or trolling can be reversed.
- Better (any) bookmark url validation.
- The photo.extension does not reflect the override filename. On one hand this is kind of good because if they override the name to have no extension, we can still provide a downloadable file with the correct extension by remembering it. But on the other hand it does break the illusion of override_filename.
- When batch fetching objects, consider whether or not a NoSuch should be raised. Perhaps a warningbag should be used.
- Find a way to batch the fetching of photo tags in a way that isn't super ugly (e.g. on an album page, the photos themselves are batched, but then the `photo.get_tags()` on each one is not. In order to batch this we would have to have a separate function that fetches a whole bunch of tags and assigns them to the photo object).
- Check for embedded cover art when thumbnailing audio files.
- Batch movement of Albums... but without winding up with a second clipboard system?
- Overall, more dynamism with cards and tag objects and updating page without requiring refresh.
- Serve RSS/Atom forms of search results.
- Caching!! I want more caching of photo's tags and albums, album's children and photos, tag's children, etc. At the moment I don't trust myself to implement it correctly with respect to deletion, relationship changes, and the possibility of two object instances (like an album holding on to a photo, but the photo itself falls out of photodb's get_cached_instance cache, then later a new instance of the photo is created, modified, deleted...)

## To do list: User permissions

Here are some thoughts about the kinds of features that need to exist within the permission system. I don't know how I'll actually manage it just yet. Possibly a `permissions` table in the database with `user_id | permission` where `permission` is some reliably-formatted string.

- Preventing logged out users from viewing any page except root and /login.
- Uploading photos (`can_upload`)
    - File extension restrictions
- Add / remove tags from photo
    - My own photos (`can_tag_own`)
    - Explicit individual allow / deny (`can_tag_photo:<photo_id>`)
    - General allow / deny (`can_tag`)
- Deleting photos
    - etc
- Creating albums
    - As children of my own albums
- Add / remove photos from album, edit title / desc.
    - My own albums (`can_edit_album_own`)
    - Explicit (`can_edit_album:<album_id>`)
    - General (`can_edit_album`)
- Deleting albums
    - etc
- Creating tags (`can_create_tag`)
- Deleting tags (`can_delete_tag`)
    - Only those that I have created (`can_delete_tag_own`)
    - Any time vs. only if they are not in use (`can_delete_tag_in_use`)

## Mirrors

https://github.com/voussoir/etiquette

https://gitlab.com/voussoir/etiquette

https://codeberg.org/voussoir/etiquette
