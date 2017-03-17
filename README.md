Etiquette
=========

I am currently running a demonstration copy of Etiquette at http://etiquette.voussoir.net where you can browse around. This is not yet permanent.

### To do list
- Make the wording between "new", "create", "add"; and "remove", "delete" more consistent.
- User account system, permission levels, private pages.
- Improve the "tags on this page" list. Maybe add separate buttons for must/may/forbid on each.
- Some way for the database to re-identify a file that was moved / renamed (lost & found). Maybe file hash of the first few mb is good enough.
- Debate whether the `UserMixin.login` method should accept usernames or I should standardize the usage of IDs only internally.
- Album size is calculated every time you refresh the page. For large albums this is very slow. Consider caching? Or saving to db?
- Organize the tag exporter functions better.

### Changelog

- **[addition]** A new feature was added.
- **[bugfix]** Incorrect behavior was fixed.
- **[change]** An existing feature was slightly modified or parameters were renamed.
- **[cleanup]** Code was improved, comments were added, or other changes with minor impact on the interface.
- **[removal]** An old feature was removed.

&nbsp;
