Etiquette
=========

I am currently running a demonstration copy of Etiquette at http://etiquette.voussoir.net where you can browse around. This is not yet permanent.

### What am I looking at

Etiquette is a tag-based file organization system with a web front-end.

Documentation is still a work in progress. In general, I use:

- `python etiquette_flask_launch.py [port]` to launch the flask server. Port defaults to 5000 if not provided.
- `python -i etiquette_repl.py` to launch the Python interpreter with the PhotoDB pre-loaded into a variable called `P`. Try things like `P.new_photo` or `P.digest_directory`.

### Project stability

You may notice that Etiquette doesn't have a version number anywhere. That's because I don't think it's ready for one. I am using this project to learn and practice, and breaking changes are very common.

### Contributing

If you are interested in helping, please raise an issue before making any pull requests!


### To do list
- Make the wording between "new", "create", "add"; and "remove", "delete" more consistent.
- User account system, permission levels, private pages.
- Improve the "tags on this page" list. Maybe add separate buttons for must/may/forbid on each.
- Some way for the database to re-identify a file that was moved / renamed (lost & found). Maybe file hash of the first few mb is good enough.
- Debate whether the `UserMixin.login` method should accept usernames or I should standardize the usage of IDs only internally.
- Ability to access user photos by user's ID, not just username.
- Should album size be cached on disk?
- Replace columns like area, ratio, bitrate by using expression indices or views (`width * height` etc).
- Add some way to support large image albums without flooding the search results. Considering a "hidden" property so that a handful of representative images can appear in the search results, and the rest can be found on the actual Album page.
- Add a `Photo.merge` to combine duplicate entries.
- Generate thumbnails for vector files without falling victim to bombs.
- Allow photos to have nonstandard, orderby-able properties like "release year". How?
- Make the FFmpeg path configurable. Some kind of global config? Or part of the database config file? It's not like every photodb needs a separate one.
- Improve the appearance of album page. Too many section headers and the "Create album" interface should allow giving a title immediately.
- When users have '%' or '#', etc. in their username, it is difficult to access their /user/ URL. I would prefer to fix it without simply blacklisting those characters.

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

### Changelog

- **[addition]** A new feature was added.
- **[bugfix]** Incorrect behavior was fixed.
- **[change]** An existing feature was slightly modified or parameters were renamed.
- **[cleanup]** Code was improved, comments were added, or other changes with minor impact on the interface.
- **[removal]** An old feature was removed.

&nbsp;
