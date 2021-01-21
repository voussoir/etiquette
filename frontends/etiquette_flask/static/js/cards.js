const cards = {};

/******************************************************************************/
cards.albums = {};

/******************************************************************************/
cards.bookmarks = {};

/******************************************************************************/
cards.photos = {};

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
