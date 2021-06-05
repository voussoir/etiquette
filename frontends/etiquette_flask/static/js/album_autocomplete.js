const album_autocomplete = {};

album_autocomplete.albums = {};

album_autocomplete.DATALIST_ID = "album_autocomplete_datalist";
album_autocomplete.datalist = null;
album_autocomplete.on_load_hooks = [];

////////////////////////////////////////////////////////////////////////////////////////////////////

album_autocomplete.init_datalist =
function init_datalist()
{
    if (album_autocomplete.datalist)
    {
        return;
    }
    console.log("Init album_autocomplete datalist.");
    const datalist = document.createElement("datalist");
    datalist.id = album_autocomplete.DATALIST_ID;
    document.body.appendChild(datalist);

    const fragment = document.createDocumentFragment();
    for (const album_id in album_autocomplete.albums)
    {
        const album_name = album_autocomplete.albums[album_id];
        const option = document.createElement("option");
        option.value = album_id;
        option.innerText = album_name;
        fragment.appendChild(option);
    }
    datalist.appendChild(fragment);
    album_autocomplete.datalist = datalist;

    for (const hook of album_autocomplete.on_load_hooks)
    {
        hook(datalist);
    }
}

album_autocomplete.get_all_albums_callback =
function get_all_albums_callback(response)
{
    if (response.meta.status !== 200)
    {
        console.error(response);
        return;
    }

    album_autocomplete.albums = response.data.albums;
    setTimeout(album_autocomplete.init_datalist, 0);
}

album_autocomplete.on_pageload =
function on_pageload()
{
    setTimeout(() => api.albums.get_all_albums(album_autocomplete.get_all_albums_callback), 0);
}
document.addEventListener("DOMContentLoaded", album_autocomplete.on_pageload);
