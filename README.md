Etiquette
=========

I am currently running a read-only demonstration copy of Etiquette at http://etiquette.voussoir.net where you can browse around.

### What am I looking at

Etiquette is a tag-based file organization system with a web interface, built with Flask and SQLite3. Tag-based systems solve problems that a traditional folder hierarchy can't: *which folder should a file go in if it equally belongs in both?* and *how do I make my files searchable without littering the filenames themselves with keywords?*

Etiquette is unique because the tags themselves are hierarchical. By tagging one of your vacation photos with the `family.parents.dad` tag, it will automatically appear in searches for `family.parents` and `family` as well. A traditional folder system, here called albums, is available to bundle files that always belong together without creating a bespoke tag to represent that bundle. Regardless, the files on disk are never modified.

### Setting up

<details><summary><strong>Click to view setup instructions</strong></summary>

First, use `pip install -r requirements.txt`. If you think you may have an older version of my voussoirkit, I'd also recommend `pip install voussoirkit --upgrade`.

As you'll see below, Etiquette has a core backend package and multiple frontends that use it. These frontend applications will use `import etiquette` to access the backend code. Therefore, the `etiquette` package needs to be in the right place for Python to find it for `import`.

Normally, Python packages use a setup.py to do this automatically. But I like running directly out of the git repository so I haven't made a setup.py yet.

<details><summary><strong>Setting up via symlink</strong></summary>

- The repository you're looking at right now is `D:\Git\Etiquette` or `/Git/Etiquette`. The toplevel `etiquette` folder is the main package. We want this package to be a child of our existing lib directory. So, we're going to put a symlink inside our Python lib folder that actually points to the code folder in this repository.
- The easiest way to find your lib path is `python -c "import os; print(os)"`. You should see something like `<module 'os' from 'C:\Python36\Lib\os.py'>` or `<module 'os' from '/usr/local/lib/python3.6/os.py'>`
- Make the junction or symlink:

  Windows: `mklink /J fakepath realpath`  
  for example `mklink /J "C:\Python36\Lib\etiquette" "D:\Git\Etiquette\etiquette"`

  Linux: `ln --symbolic realpath fakepath`  
  for example `ln --symbolic "/Git/Etiquette/etiquette" "/usr/local/lib/python3.6/etiquette"`

- Run `python -c "import etiquette; print(etiquette)"` to confirm. You should see something like `<module 'etiquette' from 'C:\Python36\Lib\etiquette\__init__.py'>` or `<module 'etiquette' from '/usr/local/lib/python3.6/etiquette/__init__.py'>`

</details>

<details><summary><strong>Setting up via pythonpath</strong></summary>

- The repository you're looking at right now is `D:\Git\Etiquette` or `/Git/Etiquette`. The toplevel `etiquette` folder is the main package.
- The PYTHONPATH environment variable contains a list of directories that *contain* the packages you need to import, not the packages themselves. Therefore we want to add the repository's path, because it contains the package.
- Set the pythonpath:

  Windows: `set "PYTHONPATH=%PYTHONPATH%;D:\Git\Etiquette"`  
  Note the semicolon to delimit paths.  
  This only applies to the current cmd session. To make it permanent, use Windows's Environment Variable editor or the `setx` command. The editor is easier to use.

  Linux: `PYTHONPATH="$PYTHONPATH:/Git/Etiquette"`  
  Note the colon to delimit paths.  
  This only applies to the current terminal session. To make it permanent, add the export to your bashrc.

- Run `echo %PYTHONPATH%` or `echo $PYTHONPATH` to confirm.
- Close your terminal and re-open it so that it uses the new environment variables.
- Run `python -c "import etiquette; print(etiquette)"` to confirm. You should see something like `<module 'etiquette' from 'D:\Git\Etiquette\etiquette\__init__.py'>` or `<module 'etiquette' from '/Git/Etiquette/etiquette/__init__.py'>`.

</details>
</details>

### Running

<details><summary><strong>Click to view run instructions</strong></summary>

In order to prevent the accidental creation of Etiquette databases, you must use `etiquette_cli.py init` to create your database.

<details><summary><strong>Running Etiquette CLI</strong></summary>

- Run `python etiquette_cli.py` to launch the script. You should see a help message describing each of the commands.

- Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher.

      Windows:
      D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_cli.py

      Linux:
      /somewhere $ python /Git/Etiquette/frontends/etiquette_cli.py

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

<details><summary><strong>Running Etiquette Flask locally</strong></summary>

- Run `python etiquette_flask_dev.py [port]` to launch the flask server. Port defaults to 5000 if not provided.

- Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher.

      Windows:
      D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_flask\etiquette_flask_dev.py 5001

      Linux:
      /somewhere $ python /Git/Etiquette/frontends/etiquette_flask/etiquette_flask_dev.py 5001

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

<details><summary><strong>Running Etiquette Flask with Gunicorn</strong></summary>

1. Use the PYTHONPATH technique to make both `etiquette` and the flask `backend` importable. You already know that the frontend code imports the backend code. But now, gunicorn needs to import the frontend code! And the server relies on static files which are relative to the code's location. So, the symlink technique doesn't work very well here, and PYTHONPATH is preferred.

   Remember that the Pythonpath points to directories that *contain* the packages you need to import, not to the packages themselves. Therefore we point to the etiquette and etiquette_flask directories.

       PYTHONPATH="$PYTHONPATH:/Git/Etiquette:/Git/Etiquette/frontends/etiquette_flask

2. To run non-daemonized, on a specific port, with logging to the terminal, I use:

       gunicorn etiquette_flask_prod:site --bind "0.0.0.0:PORT" --access-logfile "-"

</details>

<details><summary><strong>Running Etiquette REPL</strong></summary>

- Run `python etiquette_repl.py` to launch the Python interpreter with the PhotoDB pre-loaded into a variable called `P`. Try things like `P.new_photo` or `P.digest_directory`.

- Note: Do not `cd` into the frontends folder. Stay in the folder that contains your `_etiquette` database and specify the full path of the frontend launcher.

      Windows:
      D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_repl.py

      Linux:
      /somewhere $ python /Git/Etiquette/frontends/etiquette_repl.py

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

</details>

### Basic usage

Let's say you store your photos in `D:\Documents\Photos`, and you want to tag the files with Etiquette. You can get started with these steps:

1. Open a Command Prompt / Terminal. Decide where your Etiquette database will be stored, and `cd` to that location. `cd D:\Documents\Photos` is probably fine.
2. Run `etiquette_cli.py init` to create the database. A folder called `_etiquette` will appear.
3. Run `etiquette_cli.py digest . --ratelimit 1 --glob-filenames *.jpg` to add the files into the database. You can use `etiquette_cli.py digest --help` to learn about this command.
4. Run `etiquette_flask_dev.py 5000` to start the webserver on port 5000.
5. Open your web browser to `localhost:5000` and begin browsing.

### Why does Etiquette hash files?

When adding new files to the database or reloading their metadata, Etiquette will create SHA256 hashes of the files. If you are using Etiquette to organize large media files, this may take a while. I was hesitant to add hashing and incur this slowdown, but the hashes greatly improve Etiquette's ability to detect when a file has been renamed or moved, which is important when you have invested your valuable time into adding tags to them. I hope that the hash time is perceived as a worthwhile tradeoff.

### Maintaining your database with Etiquette CLI

I highly recommend storing batch/bash scripts of your favorite `etiquette_cli` invocations, so that you can quickly sync the database with the state of the disk in the future. Here are some suggestions for what you might like to include in such a script:

- `digest`: Storing all your digest invocations in a single file makes ingesting new files very easy. For your digests, I recommend including `--ratelimit` to stop Photos from having the exact same created timestamp, and `--hash-bytes-per-second` to reduce IO load. In addition, you don't want to forget your favorite `--glob-filenames` patterns.
- `reload-metadata`: In order for Etiquette's hash-based rename detection to work properly, the file hashes need to be up to date. If you're using Etiquette to track files which are being modified, you may want to get in the habit of reloading metadata regularly. By default, this will only reload metadata for files whose mtime and/or byte size have changed, so it should not be very expensive. You may add `--hash-bytes-per-second` to reduce IO load.
- `purge-deleted-files` & `purge-empty-albums`: You should only do this after a `digest`, because if a file has been moved / renamed you want the digest to pick up on that before purging it as a dead filepath. The Photo purge should come first, so that an album containing entirely deleted photos will be empty when it comes time for the Album purge.

### Project stability

You may notice that Etiquette doesn't have a version number anywhere. That's because I don't think it's ready for one. I am using this project to learn and practice, and breaking changes are very common.

### Project structure

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

### To do list
- Make the wording between "new", "create", "add"; and "remove", "delete" more consistent.
- User account system, permission levels, private pages.
- Ability to access user photos by user's ID, not just username.
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

### To do list: User permissions
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
