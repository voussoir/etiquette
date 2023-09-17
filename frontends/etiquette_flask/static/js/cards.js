const cards = {};

/******************************************************************************/
cards.albums = {};

cards.albums.create =
function create({
    album,
    view="grid",
    unlink_parent=null,
    draggable=false,
})
{
    const viewparam = view == "list" ? "?view=list" : "";

    const album_card = document.createElement("div");
    album_card.classList.add("album_card");
    album_card.classList.add(`album_card_${view}`);
    album_card.dataset.id = album == "root" ? "root" : album.id;
    album_card.ondragstart = cards.albums.drag_start
    album_card.ondragend = cards.albums.drag_end
    album_card.ondragover = cards.albums.drag_over
    album_card.ondrop = cards.albums.drag_drop
    album_card.draggable = draggable && album != "root";

    const thumbnail_link = document.createElement("a");
    thumbnail_link.classList.add("album_card_thumbnail");
    thumbnail_link.draggable = false;
    album_card.append(thumbnail_link);

    const thumbnail_img = document.createElement("img");
    thumbnail_img.loading = "lazy";
    thumbnail_img.draggable = false;
    thumbnail_link.append(thumbnail_img);

    let href;
    if (album == "root")
    {
        href = `/albums${viewparam}`;
    }
    else
    {
        href = `/album/${album.id}${viewparam}`
    }
    thumbnail_link.href = href;

    if (album == "root")
    {
        thumbnail_img.src = "/static/basic_thumbnails/album.png";
    }
    else
    {
        if (album.thumbnail_photo)
        {
            thumbnail_img.src = `/photo/${album.thumbnail_photo}/thumbnail/${album.thumbnail_photo.id}.jpg`;
        }
        else
        {
            thumbnail_img.src = "/static/basic_thumbnails/album.png";
        }
    }

    const album_title = document.createElement("a");
    album_card.append(album_title);
    album_title.classList.add("album_card_title");
    album_title.draggable = false;
    album_title.href = href;
    if (album == "root")
    {
        album_title.innerText = "Albums";
    }
    else
    {
        album_title.innerText = album.display_name;
    }

    const album_metadata = document.createElement("div");
    album_metadata.classList.add("album_card_metadata");
    album_card.append(album_metadata);
    if (album != "root")
    {
        const child_count = document.createElement("span");
        child_count.classList.add("album_card_child_count");
        child_count.title = `${album.children_count} child albums`;
        child_count.innerText = album.children_count;
        album_metadata.append(child_count);

        album_metadata.append(" | ");

        const photo_count = document.createElement("span");
        photo_count.classList.add("album_card_photo_count");
        photo_count.title = `${album.photos_count} photos`;
        photo_count.innerText = album.photos_count;
        album_metadata.append(photo_count);
    }

    const album_tools = document.createElement("div");
    album_tools.classList.add("album_card_tools");
    album_card.append(album_tools);

    if (unlink_parent !== null)
    {
        const unlink_button = document.createElement("button");
        unlink_button.classList.add("remove_child_button");
        unlink_button.classList.add("red_button");

        unlink_button.classList.add("button_with_confirm");
        unlink_button.dataset.prompt = "Remove child?";
        unlink_button.dataset.holderClass = "remove_child_button";
        unlink_button.dataset.confirmClass = "red_button";
        unlink_button.dataset.cancelClass = "gray_button";
        unlink_button.innerText = "Unlink";

        unlink_button.addEventListener("click", function(event)
        {
            return api.albums.remove_child(
                unlink_parent,
                album.id,
                common.refresh_or_alert
            );
        });
        album_tools.append(unlink_button);
    }
    return album_card;
}

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
function create({
    bookmark,
    add_author=false,
    add_delete_button=false,
    add_url_element=false,
})
{
    const bookmark_card = document.createElement("div");
    bookmark_card.className = "bookmark_card"
    bookmark_card.dataset.id = bookmark.id;

    const h2 = document.createElement("h2");
    const bookmark_title = document.createElement("a");
    bookmark_title.className = "bookmark_title";
    bookmark_title.href = bookmark.url;
    bookmark_title.innerText = bookmark.display_name;
    h2.appendChild(bookmark_title);
    bookmark_card.appendChild(h2);

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

    if (add_author && bookmark.author !== null)
    {
        const p = document.createElement("p");
        const authorlink = document.createElement("a");
        authorlink.href = "/userid/" + bookmark.author.id;
        authorlink.innerText = bookmark.author.display_name;
        p.append(authorlink);
        bookmark_card.append(p);
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
        return `/photo/${photo.id}/download/${photo.id}${photo.dot_extension}`;
    }
    const basename = escape(photo.filename);
    return `/photo/${photo.id}/download/${basename}`;
}

cards.photos.create =
function create({photo, view="grid"})
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
            thumbnail_src = `/photo/${photo.id}/thumbnail/${photo.id}.jpg`;
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

    let tag_names_title = new Set();
    let tag_names_inner = "";
    for (const photo_tag of photo.tags)
    {
        tag_names_title.add(photo_tag.tag_name);
        tag_names_inner = "T";
    }
    const photo_card_tags = document.createElement("span");
    photo_card_tags.className = "photo_card_tags";
    photo_card_tags.title = Array.from(tag_names_title).join(",");
    photo_card_tags.innerText = tag_names_inner;
    photo_card.appendChild(photo_card_tags);

    if (window.photo_clipboard !== undefined)
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

cards.photos.photo_contextmenu = null;
cards.photos.set_contextmenu =
function set_contextmenu(element, build_function)
{
    element.classList.add("photo_card_contextmenu");
    element.classList.add("contextmenu");
    element.onclick = "event.stopPropagation(); return;";
    cards.photos.photo_contextmenu = element;
    cards.photos.build_photo_contextmenu = build_function;
    contextmenus.hide_open_menus();
}

cards.photos.right_clicked_photo = null;
cards.photos.photo_rightclick =
function photo_rightclick(event)
{
    if (["A", "IMG"].includes(event.target.tagName))
    {
        return true;
    }
    if (cards.photos.photo_contextmenu === null)
    {
        return true;
    }
    if (event.ctrlKey || event.shiftKey || event.altKey)
    {
        return true;
    }
    const photo_card = event.target.closest(".photo_card");
    if (! photo_card)
    {
        cards.photos.right_clicked_photo = null;
        contextmenus.hide_open_menus();
        return true;
    }
    if (contextmenus.menu_is_open())
    {
        contextmenus.hide_open_menus();
    }
    cards.photos.right_clicked_photo = photo_card;
    const menu = cards.photos.photo_contextmenu;
    cards.photos.build_photo_contextmenu(photo_card, menu);
    setTimeout(() => {contextmenus.show_menu(event, menu);}, 0);
    event.stopPropagation();
    event.preventDefault();
    return false;
}

/******************************************************************************/
cards.photo_tags = {};

cards.photo_tags.create =
function create({photo_tag, timestamp_onclick=null, remove_button_onclick=null})
{
    const photo_tag_card = document.createElement("div");
    console.log(photo_tag);
    photo_tag_card.dataset.id = photo_tag.id;
    photo_tag_card.classList.add("photo_tag_card");

    const tag = {"id": photo_tag.tag_id, "name": photo_tag.tag_name};
    const tag_card = cards.tags.create({tag: tag});
    photo_tag_card.append(tag_card);

    if (photo_tag.timestamp !== null)
    {
        const timestamp = document.createElement("a");
        timestamp.innerText = " " + common.seconds_to_hms({seconds: photo_tag.timestamp});
        timestamp.addEventListener("click", timestamp_onclick);
        photo_tag_card.append(timestamp)
    }
    if (remove_button_onclick !== null)
    {
        const remove_button = document.createElement("button");
        remove_button.classList.add("remove_tag_button");
        remove_button.classList.add("red_button");
        remove_button.addEventListener("click", remove_button_onclick);
        photo_tag_card.append(remove_button);
    }
    return photo_tag_card;
}

/******************************************************************************/
cards.tags = {};

cards.tags.create =
function create({tag, extra_classes=[], link="info", innertext=null, add_alt_description=false})
{
    const tag_card = document.createElement("div");
    tag_card.dataset.id = tag.id;
    tag_card.classList.add("tag_card");
    for (const cls of extra_classes)
    {
        tag_card.classList.add(cls);
    }

    const a_or_span = link === null ? "span" : "a";
    const tag_text = document.createElement(a_or_span);
    tag_text.innerText = innertext || tag.name;
    if (add_alt_description && tag.description != "")
    {
        tag_text.title = tag.description;
    }
    tag_card.append(tag_text);

    const href_options = {
        "search": `/search?tag_musts=${encodeURIComponent(tag.name)}`,
        "search_musts":`/search?tag_musts=${encodeURIComponent(tag.name)}`,
        "search_mays": `/search?tag_mays=${encodeURIComponent(tag.name)}`,
        "search_forbids": `/search?tag_forbids=${encodeURIComponent(tag.name)}`,
        "info": `/tag/${encodeURIComponent(tag.name)}`,
    };
    const href = href_options[link] || null;
    if (href !== null)
    {
        tag_text.href = href;
    }

    return tag_card;
}
