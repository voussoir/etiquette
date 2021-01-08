const api = {};

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

    const data = new FormData();

    if (Array.isArray(photo_ids))
        { photo_ids = photo_ids.join(","); }
    data.append("photo_id", photo_ids);

    common.post(url, data, callback);
}

api.albums.add_child =
function add_child(album_id, child_id, callback)
{
    const url = `/album/${album_id}/add_child`;
    const data = new FormData();
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
    const url = "/albums/create_album";
    const data = new FormData();
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
    const url = `/album/${album_id}/delete`;
    common.post(url, null, callback);
}

api.albums.get_all_albums =
function get_all_albums(callback)
{
    const url = "/all_albums.json";
    common.get(url, callback);
}

api.albums.edit =
function edit(album_id, title, description, callback)
{
    const url = `/album/${album_id}/edit`;
    const data = new FormData();
    data.append("title", title);
    data.append("description", description);
    common.post(url, data, callback);
}

api.albums.refresh_directories =
function refresh_directories(album_id, callback)
{
    const url = `/album/${album_id}/refresh_directories`;
    common.post(url, null, callback);
}

api.albums.remove_child =
function remove_child(album_id, child_id, callback)
{
    const url = `/album/${album_id}/remove_child`;
    const data = new FormData();
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
    if ((response.meta.status !== 200) || (! response.meta.json_ok) || (! response.data.id))
    {
        alert(JSON.stringify(response));
        return;
    }
    window.location.href = "/album/" + response.data.id;
}

api.albums.callback_go_to_albums =
function callback_go_to_albums(response)
{
    if (response.meta.status !== 200)
    {
        alert(JSON.stringify(response));
        return;
    }
    window.location.href = "/albums";
}

/**************************************************************************************************/
api.bookmarks = {};

api.bookmarks.create =
function create(b_url, title, callback)
{
    const url = "/bookmarks/create_bookmark";
    const data = new FormData();
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
    const url = `/bookmark/${bookmark_id}/delete`;
    common.post(url, null, callback);
}

api.bookmarks.edit =
function edit(bookmark_id, title, b_url, callback)
{
    const url = `/bookmark/${bookmark_id}/edit`;
    const data = new FormData();
    data.append("title", title.trim());
    data.append("url", b_url.trim());
    common.post(url, data, callback);
}

/**************************************************************************************************/
api.photos = {};

api.photos.add_tag =
function add_tag(photo_id, tagname, callback)
{
    const url = `/photo/${photo_id}/add_tag`;
    const data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

api.photos.batch_add_tag =
function batch_add_tag(photo_ids, tagname, callback)
{
    const url = "/batch/photos/add_tag";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    data.append("tagname", tagname);
    common.post(url, data, add_remove_tag_callback);
}

api.photos.batch_refresh_metadata =
function batch_refresh_metadata(photo_ids, callback)
{
    const url = "/batch/photos/refresh_metadata";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.batch_remove_tag =
function batch_remove_tag(photo_ids, tagname, callback)
{
    const url = "/batch/photos/remove_tag";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    data.append("tagname", tagname);
    common.post(url, data, add_remove_tag_callback);
}

api.photos.batch_set_searchhidden =
function batch_set_searchhidden(photo_ids, callback)
{
    const url = "/batch/photos/set_searchhidden";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.batch_unset_searchhidden =
function batch_unset_searchhidden(photo_ids, callback)
{
    const url = "/batch/photos/unset_searchhidden";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.delete =
function _delete(photo_id, delete_file, callback)
{
    const url = `/photo/${photo_id}/delete`;
    const data = new FormData();
    data.append("delete_file", delete_file);
    common.post(url, data, callback);
}

api.photos.generate_thumbnail =
function generate_thumbnail(photo_id, special, callback)
{
    const url = `/photo/${photo_id}/generate_thumbnail`
    const data = new FormData();
    for (x in special)
    {
        data.append(x, special[x]);
    }
    common.post(url, data, callback);
}

api.photos.get_download_zip_token =
function get_download_zip_token(photo_ids, callback)
{
    const url = "/batch/photos/download_zip";
    const data = new FormData();
    data.append("photo_ids", photo_ids.join(","));
    common.post(url, data, callback);
}

api.photos.download_zip =
function download_zip(zip_token)
{
    const url = `/batch/photos/download_zip/${zip_token}.zip`;
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
    const url = `/photo/${photo_id}/refresh_metadata`;
    common.post(url, null, callback);
}

api.photos.remove_tag =
function remove_tag(photo_id, tagname, callback)
{
    const url = `/photo/${photo_id}/remove_tag`;
    const data = new FormData();
    data.append("tagname", tagname);
    common.post(url, data, callback);
}

api.photos.set_searchhidden =
function set_searchhidden(photo_id, callback)
{
    const url = `/photo/${photo_id}/set_searchhidden`;
    common.post(url, null, callback);
}

api.photos.unset_searchhidden =
function unset_searchhidden(photo_id, callback)
{
    const url = `/photo/${photo_id}/unset_searchhidden`;
    common.post(url, null, callback);
}

api.photos.callback_go_to_search =
function callback_go_to_search(response)
{
    if (response.meta.status !== 200)
    {
        alert(JSON.stringify(response));
        return;
    }
    window.location.href = "/search";
}

/**************************************************************************************************/
api.tags = {};

api.tags.add_child =
function add_child(tag_name, child_name, callback)
{
    const url = `/tag/${tag_name}/add_child`;
    const data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.add_synonym =
function add_synonym(tag_name, syn_name, callback)
{
    const url = `/tag/${tag_name}/add_synonym`;
    const data = new FormData();
    data.append("syn_name", syn_name);
    common.post(url, data, callback);
}

api.tags.create =
function create(name, description, callback)
{
    const url = `/tags/create_tag`;
    const data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.delete =
function _delete(tag_name, callback)
{
    const url = `/tag/${tag_name}/delete`;
    common.post(url, null, callback);
}

api.tags.easybake =
function easybake(easybake_string, callback)
{
    const url = "/tags/easybake";
    const data = new FormData();
    data.append("easybake_string", easybake_string);
    common.post(url, data, callback);
}

api.tags.edit =
function edit(tag_name, name, description, callback)
{
    const url = `/tag/${tag_name}/edit`;
    const data = new FormData();
    data.append("name", name);
    data.append("description", description);
    common.post(url, data, callback);
}

api.tags.get_all_tags =
function get_all_tags(callback)
{
    const url = "/all_tags.json";
    common.get(url, callback);
}

api.tags.remove_child =
function remove_child(tag_name, child_name, callback)
{
    const url = `/tag/${tag_name}/remove_child`;
    const data = new FormData();
    data.append("child_name", child_name);
    common.post(url, data, callback);
}

api.tags.remove_synonym =
function remove_synonym(tag_name, syn_name, callback)
{
    const url = `/tag/${tag_name}/remove_synonym`;
    const data = new FormData();
    data.append("syn_name", syn_name);
    common.post(url, data, callback);
}

api.tags.callback_go_to_tags =
function callback_go_to_tags(response)
{
    if (response.meta.status !== 200)
    {
        alert(JSON.stringify(response));
        return;
    }
    window.location.href = "/tags";
}

/**************************************************************************************************/
api.users = {};

api.users.edit =
function edit(username, display_name, callback)
{
    const url = `/user/${username}/edit`;
    const data = new FormData();
    data.append("display_name", display_name);
    common.post(url, data, callback);
}

api.users.login =
function login(username, password, callback)
{
    const url = "/login";
    const data = new FormData();
    data.append("username", username);
    data.append("password", password);
    common.post(url, data, callback);
}

api.users.logout =
function logout(callback)
{
    const url = "/logout";
    common.post(url, null, callback);
}

api.users.register =
function register(username, display_name, password_1, password_2, callback)
{
    const url = "/register";
    const data = new FormData();
    data.append("username", username);
    data.append("display_name", display_name);
    data.append("password_1", password_1);
    data.append("password_2", password_2);
    common.post(url, data, callback);
}
