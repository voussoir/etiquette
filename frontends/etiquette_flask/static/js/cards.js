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

/******************************************************************************/
cards.photos = {};

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