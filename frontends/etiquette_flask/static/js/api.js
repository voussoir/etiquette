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

api.bookmarks.create =
function create(b_url, title, callback)
{
    var url = "/bookmarks/create_bookmark";
    var data = new FormData();
    data.append("url", b_url.trim());
    title = title.trim();
    if (title)
    {
        data.append("title", title);
    }
    common.post(url, data, callback);
}

api.bookmarks.delete =
function _delete(bookmark_id, callback)
{
    var url = `/bookmark/${bookmark_id}/delete`;
    common.post(url, null, callback);
}

api.bookmarks.edit =
function edit(bookmark_id, title, url, callback)
{
    var url = `/bookmark/${bookmark_id}/edit`;
    var data = new FormData();
    data.append("title", title.trim());
    data.append("url", url.trim());
    common.post(url, data, callback);
}

/**************************************************************************************************/
api.photos = {};

api.photos.add_tag =
function add_tag(photo_id, tagname, callback)
{
    var url = `/photo/${photo_id}/add_tag`;
    var data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

api.photos.refresh_metadata =
function refresh_metadata(photo_id, callback)
{
    var url = `/photo/${photo_id}/refresh_metadata`;
    common.post(url, null, callback);
}

api.photos.remove_tag =
function remove_tag(photo_id, tagname, callback)
{
    var url = `/photo/${photo_id}/remove_tag`;
    var data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

/**************************************************************************************************/
api.tags = {};

api.tags.add_child =
function add_child(tag_name, child_name, callback)
{
    var url = `/tag/${tag_name}/add_child`;
    var data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.create =
function create(name, description, callback)
{
    var url = `/tags/create_tag`;
    var data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.delete =
function _delete(tag_name, callback)
{
    var url = `/tag/${tag_name}/delete`;
    common.post(url, null, callback);
}

api.tags.easybake =
function easybake(easybake_string, callback)
{
    var url = "/tags/easybake";
    var data = new FormData();
    data.append("easybake_string", easybake_string);
    common.post(url, data, callback);
}

api.tags.edit =
function edit(tag_name, name, description, callback)
{
    var url = `/tag/${tag_name}/edit`;
    var data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.remove_child =
function remove_child(tag_name, child_name, callback)
{
    var url = `/tag/${tag_name}/remove_child`;
    var data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.remove_synonym =
function remove_synonym(tag_name, syn_name, callback)
{
    var url = `/tag/${tag_name}/remove_synonym`;
    var data = new FormData();
    data.append("syn_name", syn_name);
    common.post(url, data, callback);
}


/**************************************************************************************************/
api.users = {};

api.users.login =
function login(username, password, callback)
{
    var url = "/login";
    data = new FormData();
    data.append("username", username);
    data.append("password", password);
    common.post(url, data, callback);
}

api.users.logout =
function logout(callback)
{
    var url = "/logout";
    common.post(url, null, callback);
}

api.users.register =
function register(username, password_1, password_2, callback)
{
    var url = "/register";
    data = new FormData();
    data.append("username", username);
    data.append("password_1", password_1);
    data.append("password_2", password_2);
    common.post(url, data, callback);
}
