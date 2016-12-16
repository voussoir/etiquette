Etiquette
=========

This is the readme file.

### To do list
- User account system, permission levels, private pages.
- Bookmark system. Maybe the ability to submit URLs as photo objects.
- Generalize the filename expression filter so it can work with any strings.
- Improve the "tags on this page" list. Maybe add separate buttons for must/may/forbid on each.
- Some way for the database to re-identify a file that was moved / renamed (lost & found). Maybe file hash of the first few mb is good enough.
- Move out more helpers
- Create objects.py
- Debate whether the `UserMixin.login` method should accept usernames or I should standardize the usage of IDs only internally.

### Changelog

- **[addition]** A new feature was added.
- **[bugfix]** Incorrect behavior was fixed.
- **[change]** An existing feature was slightly modified or parameters were renamed.
- **[cleanup]** Code was improved, comments were added, or other changes with minor impact on the interface.
- **[removal]** An old feature was removed.

&nbsp;

- 2016 11 28
    - **[addition]** Added `etiquette_upgrader.py`. When an update causes the anatomy of the etiquette database to change, I will increment the `phototagger.DATABASE_VERSION` variable, and add a new function to this script that should automatically make all the necessary changes. Until the database is upgraded, phototagger will not start. Don't forget to make backups just in case.

- 2016 11 05
    - **[addition]** Added the ability to download an album as a `.tar` file. No compression is used. I still need to do more experiments to make sure this is working perfectly.

