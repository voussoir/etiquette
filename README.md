Etiquette
=========

I am currently running a demonstration copy of Etiquette at http://etiquette.voussoir.net where you can browse around. This is not yet permanent.

### What am I looking at

Etiquette is a tag-based file organization system with a web interface, built with Flask and SQLite3. Tag-based systems solve problems that a traditional folder hierarchy can't: *which folder should a file go in if it equally belongs in both?* and *how do I make my files searchable without littering the filenames themselves with keywords?*

Etiquette is unique because *the tags themselves are hierarchical*. By tagging one of your vacation photos with the `family.parents.dad` tag, it will automatically appear in searches for `family.parents` and `family` as well. A traditional folder system, here called albums, is available to bundle files that always belong together without creating a bespoke tag to represent that bundle. Regardless, the files on disk are never modified.

### Setting up

<details><summary><strong>Click to view setup instructions</strong></summary>
I have not made a setup.py yet. So I use a filesystem junction / symlink to make etiquette appear in my python lib folder.

<details><summary><strong>Setting up via symlink</strong></summary>

- The repository you're looking at right now is `D:\Git\Etiquette` or `/Git/Etiquette`. The toplevel `etiquette` folder is the main package. We want this package to be a child of our existing lib directory.
- The easiest way to find your lib path is `python -c "import os; print(os)"`.
- Make the junction or symlink:

  Windows: `mklink /J fakepath realpath`  
  for example `mklink /J "C:\Python36\Lib\etiquette" "D:\Git\Etiquette\etiquette"`

  Linux: `ln --symbolic realpath fakepath`  
  for example `ln --symbolic "/Git/Etiquette/etiquette" "/usr/local/lib/python3.6/etiquette"`

- Run `python -c "import etiquette; print(etiquette)"` to confirm.

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
- Run `python -c "import etiquette; print(etiquette)"` to confirm.

</details>
</details>

### Running

<details><summary><strong>Click to view run instructions</strong></summary>
<details><summary><strong>Running Flask locally</strong></summary>

- Run `python etiquette_flask_dev.py [port]` to launch the flask server. Port defaults to 5000 if not provided.
- Note: Do not `cd` into the frontends folder. Stay wherever you want the photodb to be created, and start the frontend by specifying full file path of the launch file.

      Windows:
      D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_flask\etiquette_flask_dev.py 5001

      Linux:
      /somewhere $ python /Git/Etiquette/frontends/etiquette_flask/etiquette_flask_dev.py 5001

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

<details><summary><strong>Running Flask with Gunicorn</strong></summary>

1. Use the PYTHONPATH technique to make both `etiquette` and the flask `backend` importable. Symlinking into the lib is not as convenient here because the server relies on the static files and jinja templates relative to the code's location.

   Remember that the Pythonpath points to directories that *contain* the packages you need to import, not to the packages themselves. Therefore we point to the etiquette and etiquette_flask repositories.

       PYTHONPATH="$PYTHONPATH:/Git/Etiquette:/Git/Etiquette/frontends/etiquette_flask

2. To run non-daemonized, on a specific port, with logging to the terminal, use:

       gunicorn etiquette_flask_prod:site --bind "0.0.0.0:PORT" --access-logfile "-"

</details>

<details><summary><strong>Running Etiquette REPL</strong></summary>

- Run `python -i etiquette_repl.py` to launch the Python interpreter with the PhotoDB pre-loaded into a variable called `P`. Try things like `P.new_photo` or `P.digest_directory`.
- Note: Do not `cd` into the frontends folder. Stay wherever you want the photodb to be created, and start the frontend by specifying full file path of the launch file.

      Windows:
      D:\somewhere> python -i D:\Git\Etiquette\frontends\etiquette_repl.py

      Linux:
      /somewhere $ python -i /Git/Etiquette/frontends/etiquette_repl.py

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

<details><summary><strong>Running Etiquette CLI</strong></summary>

- Run `python -i etiquette_cli.py` to launch the script.
- Note: Do not `cd` into the frontends folder. Stay wherever you want the photodb to be created, and start the frontend by specifying full file path of the launch file.

      Windows:
      D:\somewhere> python D:\Git\Etiquette\frontends\etiquette_cli.py

      Linux:
      /somewhere $ python /Git/Etiquette/frontends/etiquette_cli.py

- In practice, I have a shortcut file on my PATH which runs this command.

</details>

</details>

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
        Provides a web interface to browse, search, and manipulate the database.
    - `etiquette_repl`  
        Preloads a few variables into the interpreter so you can quickly test functions within the Python REPL itself.
    - `etiquette_cli`  
        To be run on the command line for fast and scriptable search and manipulation.
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
- Fix album size cache when photo reload metadata and generally improve that validation.
- Better bookmark url validation.
- Extension currently does not believe in the override filename. On one hand this is kind of good because if they override the name to have no extension, we can still provide a downloadable file with the correct extension by remembering it. But on the other hand it does break the illusion of override_filename.
- When batch fetching objects, consider whether or not a NoSuch should be raised. Perhaps a warningbag should be used.
- Find a way to batch the fetching of photo tags in a way that isn't super ugly (e.g. on an album page, the photos themselves are batched, but then the `photo.get_tags()` on each one is not. In order to batch this we would have to have a separate function that fetches a whole bunch of tags and assigns them to the photo object).
- Consider using executemany for some of the batch operations.
- Check for embedded cover art when thumbnailing audio files.
- Similarly, rename all "tag_object" to tag card and unify that experience a bit.
- Batch movement of Albums... but without winding up with a second clipboard system?
- Overall, more dynamism with cards and tag objects and updating page without requiring refresh.
- Absolute consistency of CSS classes for divs that hold photo cards.
- Serve RSS/Atom forms of search results.

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

https://github.com/voussoir/etiquette

https://gitlab.com/voussoir/etiquette
