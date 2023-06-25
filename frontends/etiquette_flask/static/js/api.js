const api = {};

/**************************************************************************************************/
api.admin = {};

api.admin.clear_sessions =
function clear_sessions(callback)
{
    return http.post({
        url: "/admin/clear_sessions",
        callback: callback,
    });
}

api.admin.reload_config =
function reload_config(callback)
{
    return http.post({
        url: "/admin/reload_config",
        callback: callback,
    });
}

api.admin.uncache =
function uncache(callback)
{
    return http.post({
        url: "/admin/uncache",
        callback: callback,
    });
}

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

    if (Array.isArray(photo_ids))
        { photo_ids = photo_ids.join(","); }

    return http.post({
        url: url,
        data: {"photo_id": photo_ids},
        callback: callback
    });
}

api.albums.add_child =
function add_child(album_id, child_id, callback)
{
    return http.post({
        url: `/album/${album_id}/add_child`,
        data: {"child_id": child_id},
        callback: callback,
    });
}

api.albums.add_photos =
function add_photos(album_id, photo_ids, callback)
{
    return api.albums._add_remove_photos(album_id, photo_ids, "add", callback);
}

api.albums.create =
function create(title, parent_id, callback)
{
    return http.post({
        url: "/albums/create_album",
        data: {"title": title, "parent_id": parent_id},
        callback: callback,
    });
}

api.albums.delete =
function _delete(album_id, callback)
{
    return http.post({
        url: `/album/${album_id}/delete`,
        callback: callback,
    });
}

api.albums.get_all_albums =
function get_all_albums(callback)
{
    return http.get({
        url: "/all_albums.json",
        callback: callback,
    });
}

api.albums.edit =
function edit(album_id, title, description, callback)
{
    return http.post({
        url: `/album/${album_id}/edit`,
        data: {"title": title, "description": description},
        callback: callback,
    });
}

api.albums.refresh_directories =
function refresh_directories(album_id, callback)
{
    return http.post({
        url: `/album/${album_id}/refresh_directories`,
        callback: callback,
    });
}

api.albums.remove_child =
function remove_child(album_id, child_id, callback)
{
    return http.post({
        url: `/album/${album_id}/remove_child`,
        data: {"child_id": child_id},
        callback: callback,
    });
}

api.albums.remove_photos =
function remove_photos(album_id, photo_ids, callback)
{
    return api.albums._add_remove_photos(album_id, photo_ids, "remove", callback);
}

api.albums.remove_thumbnail_photo =
function remove_thumbnail_photo(album_id, callback)
{
    return http.post({
        url: `/album/${album_id}/remove_thumbnail_photo`,
        data: {},
        callback: callback,
    });
}

api.albums.set_thumbnail_photo =
function set_thumbnail_photo(album_id, photo_id, callback)
{
    return http.post({
        url: `/album/${album_id}/set_thumbnail_photo`,
        data: {"photo_id": photo_id},
        callback: callback,
    });
}

api.albums.show_in_folder =
function show_in_folder(album_id, callback)
{
    return http.post({
        url: `/album/${album_id}/show_in_folder`,
        callback: callback,
    });
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
    return http.post({
        url: "/bookmarks/create_bookmark",
        data: {"url": b_url.trim(), "title": title},
        callback: callback,
    });
}

api.bookmarks.delete =
function _delete(bookmark_id, callback)
{
    return http.post({
        url: `/bookmark/${bookmark_id}/delete`,
        data: {},
        callback: callback,
    });
}

api.bookmarks.edit =
function edit(bookmark_id, title, b_url, callback)
{
    return http.post({
        url: `/bookmark/${bookmark_id}/edit`,
        data: {"title": title.trim(), "url": b_url.trim()},
        callback: callback,
    });
}

/**************************************************************************************************/
api.photos = {};

api.photos.add_tag =
function add_tag(photo_id, tagname, callback)
{
    return http.post({
        url: `/photo/${photo_id}/add_tag`,
        data: {"tagname": tagname},
        callback: callback,
    });
}

api.photos.batch_add_tag =
function batch_add_tag(photo_ids, tagname, callback)
{
    return http.post({
        url: "/batch/photos/add_tag",
        data: {"photo_ids": photo_ids.join(","), "tagname": tagname},
        callback: callback,
    });
}

api.photos.batch_generate_thumbnail =
function batch_generate_thumbnail(photo_ids, callback)
{
    return http.post({
        url: "/batch/photos/generate_thumbnail",
        data: {"photo_ids": photo_ids.join(",")},
        callback: callback,
    });
}

api.photos.batch_refresh_metadata =
function batch_refresh_metadata(photo_ids, callback)
{
    return http.post({
        url: "/batch/photos/refresh_metadata",
        data: {"photo_ids": photo_ids.join(",")},
        callback: callback,
    });
}

api.photos.batch_remove_tag =
function batch_remove_tag(photo_ids, tagname, callback)
{
    return http.post({
        url: "/batch/photos/remove_tag",
        data: {"photo_ids": photo_ids.join(","), "tagname": tagname},
        callback: callback,
    });
}

api.photos.batch_set_searchhidden =
function batch_set_searchhidden(photo_ids, callback)
{
    return http.post({
        url: "/batch/photos/set_searchhidden",
        data: {"photo_ids": photo_ids.join(",")},
        callback: callback,
    });
}

api.photos.batch_unset_searchhidden =
function batch_unset_searchhidden(photo_ids, callback)
{
    return http.post({
        url: "/batch/photos/unset_searchhidden",
        data: {"photo_ids": photo_ids.join(",")},
        callback: callback,
    });
}

api.photos.copy_tags =
function copy_tags(photo_id, other_photo, callback)
{
    return http.post({
        url: `/photo/${photo_id}/copy_tags`,
        data: {"other_photo": other_photo},
        callback: callback,
    });
}

api.photos.delete =
function _delete(photo_id, delete_file, callback)
{
    return http.post({
        url: `/photo/${photo_id}/delete`,
        data: {"delete_file": delete_file},
        callback: callback,
    });
}

api.photos.generate_thumbnail =
function generate_thumbnail(photo_id, special, callback)
{
    return http.post({
        url: `/photo/${photo_id}/generate_thumbnail`,
        data: special,
        callback: callback,
    });
}

api.photos.get_download_zip_token =
function get_download_zip_token(photo_ids, callback)
{
    return http.post({
        url: "/batch/photos/download_zip",
        data: {"photo_ids": photo_ids.join(",")},
        callback: callback,
    });
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
    return http.post({
        url: `/photo/${photo_id}/refresh_metadata`,
        callback: callback,
    });
}

api.photos.remove_tag =
function remove_tag(photo_id, tagname, callback)
{
    return http.post({
        url: `/photo/${photo_id}/remove_tag`,
        data: {"tagname": tagname},
        callback: callback,
    });
}

api.photos.search =
function search(parameters, callback)
{
    parameters = parameters.toString();
    let url = "/search.json";
    if (parameters !== "" )
    {
        url += "?" + parameters;
    }
    return http.get({
        url: url,
        callback: callback,
    });
}

api.photos.set_searchhidden =
function set_searchhidden(photo_id, callback)
{
    return http.post({
        url: `/photo/${photo_id}/set_searchhidden`,
        callback: callback,
    });
}

api.photos.unset_searchhidden =
function unset_searchhidden(photo_id, callback)
{
    return http.post({
        url: `/photo/${photo_id}/unset_searchhidden`,
        callback: callback,
    });
}

api.photos.show_in_folder =
function show_in_folder(photo_id, callback)
{
    return http.post({
        url: `/photo/${photo_id}/show_in_folder`,
        callback: callback,
    });
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
    return http.post({
        url: `/tag/${tag_name}/add_child`,
        data: {"child_name": child_name},
        callback: callback,
    });
}

api.tags.add_synonym =
function add_synonym(tag_name, syn_name, callback)
{
    return http.post({
        url: `/tag/${tag_name}/add_synonym`,
        data: {"syn_name": syn_name},
        callback: callback,
    });
}

api.tags.create =
function create(name, description, callback)
{
    return http.post({
        url: `/tags/create_tag`,
        data: {"name": name, "description": description},
        callback: callback,
    });
}

api.tags.delete =
function _delete(tag_name, callback)
{
    return http.post({
        url: `/tag/${tag_name}/delete`,
        callback: callback,
    });
}

api.tags.easybake =
function easybake(easybake_string, callback)
{
    return http.post({
        url: "/tags/easybake",
        data: {"easybake_string": easybake_string},
        callback: callback,
    });
}

api.tags.edit =
function edit(tag_name, name, description, callback)
{
    return http.post({
        url: `/tag/${tag_name}/edit`,
        data: {"name": name, "description": description},
        callback: callback,
    });
}

api.tags.get_all_tags =
function get_all_tags(callback)
{
    return http.get({
        url: "/all_tags.json",
        callback: callback,
    });
}

api.tags.remove_child =
function remove_child(tag_name, child_name, callback)
{
    return http.post({
        url: `/tag/${tag_name}/remove_child`,
        data: {"child_name": child_name},
        callback: callback,
    });
}

api.tags.remove_synonym =
function remove_synonym(tag_name, syn_name, callback)
{
    return http.post({
        url: `/tag/${tag_name}/remove_synonym`,
        data: {"syn_name": syn_name},
        callback: callback,
    });
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
    return http.post({
        url: `/user/${username}/edit`,
        data: {"display_name": display_name},
        callback: callback,
    });
}

api.users.login =
function login(username, password, callback)
{
    return http.post({
        url: "/login",
        data: {"username": username, "password": password},
        callback: callback,
    });
}

api.users.logout =
function logout(callback)
{
    return http.post({
        url: "/logout",
        callback: callback,
    });
}

api.users.register =
function register(username, display_name, password_1, password_2, callback)
{
    const data = {
        "username": username,
        "display_name": display_name,
        "password_1": password_1,
        "password_2": password_2,
    };
    return http.post({
        url: "/register",
        data: data,
        callback: callback,
    });
}
