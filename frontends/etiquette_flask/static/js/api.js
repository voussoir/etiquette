var api = {};

/**************************************************************************************************/
api.albums = {};

api.albums._add_remove_photos =
function _add_remove_photos(album_id, photo_ids, add_or_remove, callback)
{
    let url;
    if (add_or_remove === "add")
        { url = `/album/${album_id}/add_photo`; }
    else if (add_or_remove === "remove")
        { url = `/album/${album_id}/remove_photo`; }
    else
        { throw `should be 'add' or 'remove', not ${add_or_remove}.`; }

    let data = new FormData();

    if (Array.isArray(photo_ids))
        { photo_ids = photo_ids.join(","); }
    data.append("photo_id", photo_ids);

    common.post(url, data, callback);
}

api.albums.add_child =
function add_child(album_id, child_id, callback)
{
    let url = `/album/${album_id}/add_child`;
    let data = new FormData();
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
    let url = "/albums/create_album";
    let data = new FormData();
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
    let url = `/album/${album_id}/delete`;
    common.post(url, null, callback);
}

api.albums.edit =
function edit(album_id, title, description, callback)
{
    let url = `/album/${album_id}/edit`;
    let data = new FormData();
    data.append("title", title);
    data.append("description", description);
    common.post(url, data, callback);
}

api.albums.refresh_directories =
function refresh_directories(album_id, callback)
{
    let url = `/album/${album_id}/refresh_directories`;
    common.post(url, null, callback);
}

api.albums.remove_child =
function remove_child(album_id, child_id, callback)
{
    let url = `/album/${album_id}/remove_child`;
    let data = new FormData();
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
    let url = "/bookmarks/create_bookmark";
    let data = new FormData();
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
    let url = `/bookmark/${bookmark_id}/delete`;
    common.post(url, null, callback);
}

api.bookmarks.edit =
function edit(bookmark_id, title, b_url, callback)
{
    let url = `/bookmark/${bookmark_id}/edit`;
    let data = new FormData();
    data.append("title", title.trim());
    data.append("url", b_url.trim());
    common.post(url, data, callback);
}

/**************************************************************************************************/
api.photos = {};

api.photos.add_tag =
function add_tag(photo_id, tagname, callback)
{
    let url = `/photo/${photo_id}/add_tag`;
    let data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

api.photos.batch_add_tag =
function batch_add_tag(photo_ids, tagname, callback)
{
    let url = "/batch/photos/add_tag";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    data.append("tagname", tagname);
    common.post(url, data, add_remove_tag_callback);
}

api.photos.batch_refresh_metadata =
function batch_refresh_metadata(photo_ids, callback)
{
    let url = "/batch/photos/refresh_metadata";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.batch_remove_tag =
function batch_remove_tag(photo_ids, tagname, callback)
{
    let url = "/batch/photos/remove_tag";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    data.append("tagname", tagname);
    common.post(url, data, add_remove_tag_callback);
}

api.photos.batch_set_searchhidden =
function batch_set_searchhidden(photo_ids, callback)
{
    let url = "/batch/photos/set_searchhidden";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.batch_unset_searchhidden =
function batch_unset_searchhidden(photo_ids, callback)
{
    let url = "/batch/photos/unset_searchhidden";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.delete =
function _delete(photo_id, delete_file, callback)
{
    let url = `/photo/${photo_id}/delete`;
    let data = new FormData();
    data.append("delete_file", delete_file);
    common.post(url, data, callback);
}

api.photos.generate_thumbnail =
function generate_thumbnail(photo_id, special, callback)
{
    let url = `/photo/${photo_id}/generate_thumbnail`
    let data = new FormData();
    for (x in special)
    {
        data.append(x, special[x]);
    }
    common.post(url, data, callback);
}

api.photos.get_download_zip_token =
function get_download_zip_token(photo_ids, callback)
{
    let url = "/batch/photos/download_zip";
    let data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.download_zip =
function download_zip(zip_token)
{
    let url = `/batch/photos/download_zip/${zip_token}.zip`;
    window.location.href = url;
}

api.photos.callback_download_zip =
function callback_download_zip(response)
{
    let zip_token = response.data.zip_token;
    api.photos.download_zip(zip_token);
}

api.photos.refresh_metadata =
function refresh_metadata(photo_id, callback)
{
    let url = `/photo/${photo_id}/refresh_metadata`;
    common.post(url, null, callback);
}

api.photos.remove_tag =
function remove_tag(photo_id, tagname, callback)
{
    let url = `/photo/${photo_id}/remove_tag`;
    let data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

api.photos.callback_go_to_search =
function callback_go_to_albums(response)
{
    if (response["meta"]["status"] == 200)
    {
        window.location.href = "/search";
    }
    else
    {
        console.log(response);
    }
}

/**************************************************************************************************/
api.tags = {};

api.tags.add_child =
function add_child(tag_name, child_name, callback)
{
    let url = `/tag/${tag_name}/add_child`;
    let data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.create =
function create(name, description, callback)
{
    let url = `/tags/create_tag`;
    let data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.delete =
function _delete(tag_name, callback)
{
    let url = `/tag/${tag_name}/delete`;
    common.post(url, null, callback);
}

api.tags.easybake =
function easybake(easybake_string, callback)
{
    let url = "/tags/easybake";
    let data = new FormData();
    data.append("easybake_string", easybake_string);
    common.post(url, data, callback);
}

api.tags.edit =
function edit(tag_name, name, description, callback)
{
    let url = `/tag/${tag_name}/edit`;
    let data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.remove_child =
function remove_child(tag_name, child_name, callback)
{
    let url = `/tag/${tag_name}/remove_child`;
    let data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.remove_synonym =
function remove_synonym(tag_name, syn_name, callback)
{
    let url = `/tag/${tag_name}/remove_synonym`;
    let data = new FormData();
    data.append("syn_name", syn_name);
    common.post(url, data, callback);
}

api.tags.callback_go_to_tags =
function callback_go_to_tags(response)
{
    if (response["meta"]["status"] == 200)
    {
        window.location.href = "/tags";
    }
    else
    {
        console.log(response);
    }
}

/**************************************************************************************************/
api.users = {};

api.users.login =
function login(username, password, callback)
{
    let url = "/login";
    let data = new FormData();
    data.append("username", username);
    data.append("password", password);
    common.post(url, data, callback);
}

api.users.logout =
function logout(callback)
{
    let url = "/logout";
    common.post(url, null, callback);
}

api.users.register =
function register(username, display_name, password_1, password_2, callback)
{
    let url = "/register";
    let data = new FormData();
    data.append("username", username);
    data.append("display_name", display_name);
    data.append("password_1", password_1);
    data.append("password_2", password_2);
    common.post(url, data, callback);
}
