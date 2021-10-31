const cards = {};

/******************************************************************************/
cards.albums = {};

cards.albums.drag_start =
function drag_start(event)
{
    const album_card = event.target.closest(".album_card");
    event.dataTransfer.setData("text/plain", album_card.id);
}

cards.albums.drag_end =
function drag_end(event)
{
}

cards.albums.drag_over =
function drag_over(event)
{
    event.preventDefault();
}

cards.albums.drag_drop =
function drag_drop(event)
{
    const child = document.getElementById(event.dataTransfer.getData("text"));
    const child_id = child.dataset.id;
    const parent = event.currentTarget;
    const parent_id = parent.dataset.id;
    event.dataTransfer.clearData();

    if (child_id == parent_id)
    {
        return;
    }

    let prompt;
    if (parent_id === "root")
    {
        const child_title = child.querySelector('.album_card_title').textContent.trim();
        prompt = `Remove child\n${child_title}?`;
    }
    else
    {
        const child_title = child.querySelector('.album_card_title').textContent.trim();
        const parent_title = parent.querySelector('.album_card_title').textContent.trim();
        prompt = `Move\n${child_title}\ninto\n${parent_title}?`;
    }

    if (! confirm(prompt))
    {
        return;
    }

    if (parent_id === "root")
    {
        api.albums.remove_child(ALBUM_ID, child_id, common.refresh_or_alert);
    }
    else if (ALBUM_ID)
    {
        api.albums.add_child(parent_id, child_id, null);
        api.albums.remove_child(ALBUM_ID, child_id, common.refresh_or_alert);
    }
    else
    {
        api.albums.add_child(parent_id, child_id, common.refresh_or_alert);
    }
}

/******************************************************************************/
cards.bookmarks = {};

cards.bookmarks.create =
function create(bookmark, add_author, add_delete_button, add_url_element)
{
    const bookmark_card = document.createElement("div");
    bookmark_card.className = "bookmark_card"
    bookmark_card.dataset.id = bookmark.id;

    const bookmark_title = document.createElement("a");
    bookmark_title.className = "bookmark_title";
    bookmark_title.href = bookmark.url;
    bookmark_title.innerText = bookmark.display_name;
    bookmark_card.appendChild(bookmark_title);

    // The URL element is always display:none, but its presence is useful in
    // facilitating the Editor object. If this bookmark will not be editable,
    // there is no need for it.
    if (add_url_element)
    {
        const bookmark_url = document.createElement("a");
        bookmark_url.className = "bookmark_url";
        bookmark_url.href = bookmark.url;
        bookmark_url.innerText = bookmark.url;
        bookmark_card.appendChild(bookmark_url);
    }

    // If more tools are added, this will become an `or`.
    // I just want to have the structure in place now.
    if (add_delete_button)
    {
        const bookmark_toolbox = document.createElement("div");
        bookmark_toolbox.className = "bookmark_toolbox"
        bookmark_card.appendChild(bookmark_toolbox);

        if (add_delete_button)
        {
            const delete_button = document.createElement("button");
            delete_button.className = "red_button button_with_confirm";
            delete_button.dataset.onclick = "return delete_bookmark_form(event);";
            delete_button.dataset.prompt = "Delete Bookmark?";
            delete_button.dataset.cancelClass = "gray_button";
            delete_button.innerText = "Delete";
            bookmark_toolbox.appendChild(delete_button);
            common.init_button_with_confirm(delete_button);
        }
    }

    return bookmark_card;
}

/******************************************************************************/
cards.photos = {};

cards.photos.MIMETYPE_THUMBNAILS = {
    "svg": "svg",

    "application/zip": "archive",
    "application/x-tar": "archive",

    "archive": "archive",
    "audio": "audio",
    "image": "image",
    "video": "video",
    "text": "txt",
};

cards.photos.file_link =
function file_link(photo, short)
{
    if (short)
    {
        return `/file/${photo.id}${photo.dot_extension}`;
    }
    const basename = escape(photo.filename);
    return `/file/${photo.id}/${basename}`;
}

cards.photos.create =
function create(photo, view)
{
    if (view !== "list" && view !== "grid")
    {
        view = "grid";
    }

    const photo_card = document.createElement("div");
    photo_card.id = `photo_card_${photo.id}`;
    photo_card.dataset.id = photo.id;
    photo_card.className = `photo_card photo_card_${view} photo_card_unselected`
    if (photo.searchhidden)
    {
        photo_card.classList.add("photo_card_searchhidden");
    }
    photo_card.ondragstart = "return cards.photos.drag_start(event);";
    photo_card.ondragend = "return cards.photos.drag_end(event);";
    photo_card.ondragover = "return cards.photos.drag_over(event);";
    photo_card.ondrop = "return cards.photos.drag_drop(event);";
    photo_card.draggable = true;

    const photo_card_filename = document.createElement("div");
    photo_card_filename.className = "photo_card_filename";
    const filename_link = document.createElement("a");
    filename_link.target = "_blank";
    filename_link.href = `/photo/${photo.id}`;
    filename_link.draggable = false;
    filename_link.innerText = photo.filename;
    photo_card_filename.appendChild(filename_link);
    photo_card.appendChild(photo_card_filename);

    const photo_card_metadata = document.createElement("span");
    photo_card_metadata.className = "photo_card_metadata";
    const metadatas = [];
    if (photo.width)
    {
        metadatas.push(`${photo.width}&times;${photo.height}`);
    }
    if (photo.duration)
    {
        metadatas.push(`${photo.duration_string}`);
    }
    photo_card_metadata.innerHTML = common.join_and_trail(metadatas, ", ");
    const filesize_file_link = document.createElement("a");
    filesize_file_link.href = cards.photos.file_link(photo);
    filesize_file_link.target = "_blank";
    filesize_file_link.draggable = false;
    filesize_file_link.innerText = photo.bytes_string;
    photo_card_metadata.append(filesize_file_link);
    photo_card.appendChild(photo_card_metadata);

    if (view == "grid")
    {
        let thumbnail_src;
        if (photo.has_thumbnail)
        {
            thumbnail_src = `/thumbnail/${photo.id}.jpg`;
        }
        else
        {
            thumbnail_src =
            cards.photos.MIMETYPE_THUMBNAILS[photo.extension] ||
            cards.photos.MIMETYPE_THUMBNAILS[photo.mimetype] ||
            cards.photos.MIMETYPE_THUMBNAILS[photo.simple_mimetype] ||
            "other";
            thumbnail_src = `/static/basic_thumbnails/${thumbnail_src}.png`;
        }

        const photo_card_thumbnail = document.createElement("a");
        photo_card_thumbnail.className = "photo_card_thumbnail";
        photo_card_thumbnail.target = "_blank";
        photo_card_thumbnail.href = `/photo/${photo.id}`;
        photo_card_thumbnail.draggable = false;
        const thumbnail_img = document.createElement("img");
        thumbnail_img.loading = "lazy";
        thumbnail_img.src = thumbnail_src;
        thumbnail_img.draggable = false;
        photo_card_thumbnail.appendChild(thumbnail_img);
        photo_card.appendChild(photo_card_thumbnail);
    }

    let tag_names_title = [];
    let tag_names_inner = "";
    for (const tag of photo.tags)
    {
        tag_names_title.push(tag.name);
        tag_names_inner = "T";
    }
    const photo_card_tags = document.createElement("span");
    photo_card_tags.className = "photo_card_tags";
    photo_card_tags.title = tag_names_title.join(",");
    photo_card_tags.innerText = tag_names_inner;
    photo_card.appendChild(photo_card_tags);

    const toolbutton = document.createElement("button");
    toolbutton.className = "photo_card_toolbutton hidden";
    toolbutton.onclick = "return cards.photos.show_tools(event);";
    photo_card.appendChild(toolbutton);

    const photo_card_tools = document.createElement("div");
    photo_card_tools.className = "photo_card_tools";
    photo_card_tools.onclick = "event.stopPropagation(); return;";
    photo_card.appendChild(photo_card_tools);

    if (photo_clipboard)
    {
        const clipboard_checkbox = photo_clipboard.give_checkbox(photo_card);
        photo_clipboard.apply_check(clipboard_checkbox);
    }

    return photo_card;
}

cards.photos.drag_start =
function drag_start(event)
{
}

cards.photos.drag_end =
function drag_end(event)
{
}

cards.photos.drag_over =
function drag_over(event)
{
}

cards.photos.drag_drop =
function drag_drop(event)
{
}

cards.photos.show_tools =
function show_tools(event)
{
    event.stopPropagation();
    event.preventDefault();
    const photo_card = event.target.closest(".photo_card");
    const toolbox = photo_card.getElementsByClassName("photo_card_tools")[0];
    if (toolbox.childElementCount === 0)
    {
        return;
    }
    contextmenus.show_menu(event, toolbox);
    return false;
}

/******************************************************************************/
cards.tags = {};
