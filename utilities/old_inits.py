V11 = '''
PRAGMA cache_size = 10000;
PRAGMA count_changes = OFF;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 11;

----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users(
    id TEXT PRIMARY KEY NOT NULL,
    username TEXT NOT NULL COLLATE NOCASE,
    password BLOB NOT NULL,
    created INT
);
CREATE INDEX IF NOT EXISTS index_users_id on users(id);
CREATE INDEX IF NOT EXISTS index_users_username on users(username COLLATE NOCASE);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS albums(
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS index_albums_id on albums(id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks(
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    url TEXT,
    author_id TEXT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_bookmarks_id on bookmarks(id);
CREATE INDEX IF NOT EXISTS index_bookmarks_author on bookmarks(author_id);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photos(
    id TEXT PRIMARY KEY NOT NULL,
    filepath TEXT COLLATE NOCASE,
    override_filename TEXT COLLATE NOCASE,
    extension TEXT,
    width INT,
    height INT,
    ratio REAL,
    area INT,
    duration INT,
    bytes INT,
    created INT,
    thumbnail TEXT,
    tagged_at INT,
    author_id TEXT,
    searchhidden INT,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS index_photos_id on photos(id);
CREATE INDEX IF NOT EXISTS index_photos_filepath on photos(filepath COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_override_filename on
    photos(override_filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS index_photos_created on photos(created);
CREATE INDEX IF NOT EXISTS index_photos_extension on photos(extension);
CREATE INDEX IF NOT EXISTS index_photos_author_id on photos(author_id);
CREATE INDEX IF NOT EXISTS index_photos_searchhidden on photos(searchhidden);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags(
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT
);
CREATE INDEX IF NOT EXISTS index_tags_id on tags(id);
CREATE INDEX IF NOT EXISTS index_tags_name on tags(name);
----------------------------------------------------------------------------------------------------


----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_associated_directories(
    albumid TEXT NOT NULL,
    directory TEXT NOT NULL COLLATE NOCASE,
    FOREIGN KEY(albumid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_albumid on
    album_associated_directories(albumid);
CREATE INDEX IF NOT EXISTS index_album_associated_directories_directory on
    album_associated_directories(directory);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_group_rel(
    parentid TEXT NOT NULL,
    memberid TEXT NOT NULL,
    FOREIGN KEY(parentid) REFERENCES albums(id),
    FOREIGN KEY(memberid) REFERENCES albums(id)
);
CREATE INDEX IF NOT EXISTS index_album_group_rel_parentid on album_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_album_group_rel_memberid on album_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS album_photo_rel(
    albumid TEXT NOT NULL,
    photoid TEXT NOT NULL,
    FOREIGN KEY(albumid) REFERENCES albums(id),
    FOREIGN KEY(photoid) REFERENCES photos(id)
);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_albumid on album_photo_rel(albumid);
CREATE INDEX IF NOT EXISTS index_album_photo_rel_photoid on album_photo_rel(photoid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_numbers(
    tab TEXT NOT NULL,
    last_id TEXT NOT NULL
);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS photo_tag_rel(
    photoid TEXT NOT NULL,
    tagid TEXT NOT NULL,
    FOREIGN KEY(photoid) REFERENCES photos(id),
    FOREIGN KEY(tagid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_photoid on photo_tag_rel(photoid);
CREATE INDEX IF NOT EXISTS index_photo_tag_rel_tagid on photo_tag_rel(tagid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_group_rel(
    parentid TEXT NOT NULL,
    memberid TEXT NOT NULL,
    FOREIGN KEY(parentid) REFERENCES tags(id),
    FOREIGN KEY(memberid) REFERENCES tags(id)
);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_parentid on tag_group_rel(parentid);
CREATE INDEX IF NOT EXISTS index_tag_group_rel_memberid on tag_group_rel(memberid);
----------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag_synonyms(
    name TEXT NOT NULL,
    mastername TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS index_tag_synonyms_name on tag_synonyms(name);
----------------------------------------------------------------------------------------------------
'''
