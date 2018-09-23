var api = {};

/**************************************************************************************************/
api.albums = {};

api.albums._add_remove_photos =
function _add_remove_photos(album_id, photo_ids, add_or_remove, callback)
{
    var url;
    if (add_or_remove === "add")
        { url = `/album/${album_id}/add_photo`; }
    else if (add_or_remove === "remove")
        { url = `/album/${album_id}/remove_photo`; }
    else
        { throw `should be 'add' or 'remove', not ${add_or_remove}.`; }

    var data = new FormData();

    if (Array.isArray(photo_ids))
        { photo_ids = photo_ids.join(","); }
    data.append("photo_id", photo_ids);

    common.post(url, data, callback);
}

api.albums.add_child =
function add_child(album_id, child_id, callback)
{
    var url = `/album/${album_id}/add_child`;
    var data = new FormData();
    data.append("child_id", child_id);
    common.post(url, data, callback);
}

api.albums.add_photos =
function add_photos(album_id, photo_ids, callback)
{
    api.albums._add_remove_photos(album_id, photo_ids, "add", callback);
}

api.albums.create =
function create(title, parent_id, callback)
{
    var url = "/albums/create_album";
    var data = new FormData();
    if (title !== undefined)
    {
        data.append("title", title);
    }
    if (parent_id !== undefined)
    {
        data.append("parent_id", parent_id);
    }
    common.post(url, data, callback);
}

api.albums.delete =
function _delete(album_id, callback)
{
    var url = `/album/${album_id}/delete`;
    common.post(url, null, callback);
}

api.albums.edit =
function edit(album_id, title, description, callback)
{
    var url = `/album/${album_id}/edit`;
    var data = new FormData();
    data.append("title", title);
    data.append("description", description);
    common.post(url, data, callback);
}

api.albums.remove_child =
function remove_child(album_id, child_id, callback)
{
    var url = `/album/${album_id}/remove_child`;
    var data = new FormData();
    data.append("child_id", child_id);
    common.post(url, data, callback);
}

api.albums.remove_photos =
function remove_photos(album_id, photo_ids, callback)
{
    api.albums._add_remove_photos(album_id, photo_ids, "remove", callback);
}

api.albums.callback_follow =
function callback_follow(response)
{
    if (response["meta"]["status"] == 200 && response["data"]["id"])
    {
        window.location.href = "/album/" + response["data"]["id"];
    }
    else
    {
        console.log(response);
    }
}

api.albums.callback_go_to_albums =
function callback_go_to_albums(response)
{
    if (response["meta"]["status"] == 200)
    {
        window.location.href = "/albums";
    }
    else
    {
        console.log(response);
    }
}

/**************************************************************************************************/
api.bookmarks = {};

/**************************************************************************************************/
api.photos = {};

/**************************************************************************************************/
api.tags = {};

/**************************************************************************************************/
api.users = {};
