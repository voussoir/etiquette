Etiquette
=========

I am currently running a demonstration copy of Etiquette at http://etiquette.voussoir.net where you can browse around. This is not yet permanent.

### What am I looking at

Etiquette is a tag-based file organization system with a web front-end.

Documentation is still a work in progress. In general, I use:

- `python etiquette_flask_launch.py [port]` to launch the flask server. Port defaults to 5000 if not provided.
- `python -i etiquette_repl.py` to launch the Python interpreter with the PhotoDB pre-loaded into a variable called `P`. Try things like `P.new_photo` or `P.digest_directory`.

### To do list
- Make the wording between "new", "create", "add"; and "remove", "delete" more consistent.
- User account system, permission levels, private pages.
- Improve the "tags on this page" list. Maybe add separate buttons for must/may/forbid on each.
- Some way for the database to re-identify a file that was moved / renamed (lost & found). Maybe file hash of the first few mb is good enough.
- Debate whether the `UserMixin.login` method should accept usernames or I should standardize the usage of IDs only internally.
- Ability to access user page and user photos by user's ID, not just username.
- Should album size be cached on disk?
- Replace columns like area, ratio, bitrate by using expression indices or views (`width * height` etc).
- Add some way to support large image albums without flooding the search results. Considering a "hidden" property so that a handful of representative images can appear in the search results, and the rest can be found on the actual Album page.
- Add a `Photo.merge` to combine duplicate entries.

### Changelog

- **[addition]** A new feature was added.
- **[bugfix]** Incorrect behavior was fixed.
- **[change]** An existing feature was slightly modified or parameters were renamed.
- **[cleanup]** Code was improved, comments were added, or other changes with minor impact on the interface.
- **[removal]** An old feature was removed.

&nbsp;
