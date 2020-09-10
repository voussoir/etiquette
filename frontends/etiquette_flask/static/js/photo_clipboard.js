var photo_clipboard = {};

photo_clipboard.clipboard = new Set();
photo_clipboard.on_load_hooks = [];
photo_clipboard.on_save_hooks = [];

// Load save ///////////////////////////////////////////////////////////////////////////////////////

photo_clipboard.clear_clipboard =
function clear_clipboard()
{
    photo_clipboard.clipboard.clear();
    photo_clipboard.save_clipboard();
}

photo_clipboard.load_clipboard =
function load_clipboard(event)
{
    console.log("Loading photo clipboard from localstorage.");
    let stored = localStorage.getItem("photo_clipboard");
    if (stored === null)
    {
        if (photo_clipboard.clipboard.size != 0)
        {
            photo_clipboard.clipboard = new Set();
        }
    }
    else
    {
        photo_clipboard.clipboard = new Set(JSON.parse(stored));
    }

    for (const on_load_hook of photo_clipboard.on_load_hooks)
    {
        on_load_hook();
    }

    return photo_clipboard.clipboard;
}

photo_clipboard.save_clipboard =
function save_clipboard()
{
    console.log("Saving photo clipboard to localstorage.");
    let serialized = JSON.stringify(Array.from(photo_clipboard.clipboard));
    localStorage.setItem("photo_clipboard", serialized);
    photo_clipboard.update_pagestate();

    for (const on_save_hook of photo_clipboard.on_save_hooks)
    {
        on_save_hook();
    }
}

// Card management /////////////////////////////////////////////////////////////////////////////////

photo_clipboard.apply_check =
function apply_check(checkbox)
{
    /*
    Check the checkbox if this photo ID is on the clipboard.

    There are two valid scenarios:
    1. The checkbox is a child of a photo_card div, and that div has data-id
       containing the photo id. That div will receive the CSS class
       photo_card_selected or photo_card_unselected.
       This is the most common usage.
    2. The checkbox has its own data-photo-id, and the parent element will be
       ignored. This is used only if the checkbox needs to be displayed outside
       of a photo card, such as on the /photo/id page where it makes no sense
       to put a photo card of the photo you're already looking at.
    */
    let photo_id;
    let photo_card;
    if (checkbox.dataset.photoId)
    {
        photo_id = checkbox.dataset.photoId;
    }
    else
    {
        photo_card = checkbox.parentElement;
        photo_id = photo_card.dataset.id;
    }
    checkbox.checked = photo_clipboard.clipboard.has(photo_id);
    if (! photo_card)
    {
        return;
    }
    if (checkbox.checked)
    {
        photo_card.classList.remove("photo_card_unselected");
        photo_card.classList.add("photo_card_selected");
    }
    else
    {
        photo_card.classList.remove("photo_card_selected");
        photo_card.classList.add("photo_card_unselected");
    }
}

photo_clipboard.apply_check_all =
function apply_check_all()
{
    /*
    Run through all the photo cards on the page and set their checkbox to the
    correct value.
    */
    let checkboxes = document.getElementsByClassName("photo_card_selector_checkbox");
    for (let checkbox of checkboxes)
    {
        photo_clipboard.apply_check(checkbox);
    }
}

photo_clipboard._action_select =
function(photo_div){photo_clipboard.clipboard.add(photo_div.dataset.id)}

photo_clipboard._action_unselect =
function(photo_div){photo_clipboard.clipboard.delete(photo_div.dataset.id)}

photo_clipboard.previous_photo_select = null;

photo_clipboard.on_photo_select =
function on_photo_select(event)
{
    /*
    Select or unselect the clicked photo, with support for Shift-click to action
    everything between the previous click and this one inclusively.

    Those middle items will be set to the same state as the new state of the
    clicked item.
    */
    if (event.target.checked)
    {
        action = photo_clipboard._action_select;
    }
    else
    {
        action = photo_clipboard._action_unselect;
    }

    if (event.shiftKey && photo_clipboard.previous_photo_select)
    {
        let current_photo_div = event.target.parentElement;
        let previous_photo_div = photo_clipboard.previous_photo_select.target.parentElement;
        let photo_divs = Array.from(current_photo_div.parentElement.children);

        let current_index = photo_divs.indexOf(current_photo_div);
        let previous_index = photo_divs.indexOf(previous_photo_div);

        let slice;
        if (current_index == previous_index)
        {
            slice = [current_photo_div];
        }
        else
        {
            let left = Math.min(previous_index, current_index);
            let right = Math.max(previous_index, current_index);
            slice = photo_divs.slice(left, right + 1);
        }

        slice.forEach(action);
    }
    else
    {
        let photo_div = event.target.parentElement;
        action(photo_div);
    }
    photo_clipboard.previous_photo_select = event;
    photo_clipboard.save_clipboard();
}

photo_clipboard.select_all_photos =
function select_all_photos()
{
    let photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(photo_clipboard._action_select);
    photo_clipboard.apply_check_all();
    photo_clipboard.save_clipboard();
}

photo_clipboard.unselect_all_photos =
function unselect_all_photos()
{
    let photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(photo_clipboard._action_unselect);
    photo_clipboard.apply_check_all()
    photo_clipboard.previous_photo_select = null;
    photo_clipboard.save_clipboard();
}

// Tray management /////////////////////////////////////////////////////////////////////////////////

photo_clipboard.clipboard_tray_collapse =
function clipboard_tray_collapse()
{
    let tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.add("hidden");
}

photo_clipboard.clipboard_tray_uncollapse =
function clipboard_tray_uncollapse()
{
    let tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.remove("hidden");
    photo_clipboard.update_clipboard_tray();
}

photo_clipboard.clipboard_tray_collapse_toggle =
function clipboard_tray_collapse_toggle()
{
    /*
    Show or hide the clipboard.
    */
    let tray_body = document.getElementById("clipboard_tray_body");
    if (!tray_body)
    {
        return;
    }

    if (tray_body.classList.contains("hidden") && photo_clipboard.clipboard.size > 0)
    {
        photo_clipboard.clipboard_tray_uncollapse();
    }
    else
    {
        photo_clipboard.clipboard_tray_collapse();
    }
}

photo_clipboard.ingest_toolbox_items =
function ingest_toolbox_items()
{
    /*
    The page may provide divs with the class "my_clipboard_tray_toolbox", and
    we will migrate all the elements into the real clipboard tray toolbox.
    */
    let toolbox = document.getElementById("clipboard_tray_toolbox");
    let moreboxes = document.getElementsByClassName("my_clipboard_tray_toolbox");

    for (const morebox of moreboxes)
    {
        while (morebox.firstElementChild)
        {
            toolbox.appendChild(morebox.firstElementChild);
        }
        morebox.parentElement.removeChild(morebox);
    }
}

photo_clipboard.on_tray_delete_button =
function on_tray_delete_button(event)
{
    /*
    Remove the clicked row from the clipboard.
    */
    let clipboard_line = event.target.parentElement;
    let photo_id = clipboard_line.dataset.id;
    photo_clipboard.clipboard.delete(photo_id);
    photo_clipboard.save_clipboard();
}

photo_clipboard.update_clipboard_tray =
function update_clipboard_tray()
{
    /*
    Rebuild the rows if the tray is open.
    */
    let clipboard_tray = document.getElementById("clipboard_tray");
    if (clipboard_tray === null)
    {
        return;
    }

    if (photo_clipboard.clipboard.size == 0)
    {
        photo_clipboard.clipboard_tray_collapse();
    }

    let tray_lines = document.getElementById("clipboard_tray_lines");
    if (!clipboard_tray.classList.contains("hidden"))
    {
        common.delete_all_children(tray_lines);
        let photo_ids = Array.from(photo_clipboard.clipboard);
        photo_ids.sort();
        for (const photo_id of photo_ids)
        {
            let clipboard_line = document.createElement("div");
            clipboard_line.classList.add("clipboard_tray_line");
            clipboard_line.dataset.id = photo_id;

            let clipboard_line_delete_button = document.createElement("button");
            clipboard_line_delete_button.classList.add("remove_tag_button_perm");
            clipboard_line_delete_button.classList.add("red_button");
            clipboard_line_delete_button.onclick = photo_clipboard.on_tray_delete_button;

            let clipboard_line_link = document.createElement("a");
            clipboard_line_link.target = "_blank";
            clipboard_line_link.href = "/photo/" + photo_id;
            clipboard_line_link.innerText = photo_id;

            clipboard_line.appendChild(clipboard_line_delete_button);
            clipboard_line.appendChild(clipboard_line_link);
            tray_lines.appendChild(clipboard_line);
        }
    }
}

// Page and event management ///////////////////////////////////////////////////////////////////////

photo_clipboard.open_full_clipboard_tab =
function open_full_clipboard_tab()
{
    window.open("/clipboard");
}

photo_clipboard.update_clipboard_count =
function update_clipboard_count()
{
    let elements = document.getElementsByClassName("clipboard_count");
    for (const element of elements)
    {
        element.innerText = photo_clipboard.clipboard.size;
    }
}

photo_clipboard.on_storage_event =
function on_storage_event()
{
    /*
    Receive storage events from other tabs and update our state to match.
    */
    photo_clipboard.load_clipboard();
    photo_clipboard.update_pagestate();
}

photo_clipboard.update_pagestate =
function update_pagestate()
{
    /*
    Update all relevant DOM elements to match internal state.
    */
    photo_clipboard.update_clipboard_count();
    photo_clipboard.update_clipboard_tray();
    photo_clipboard.apply_check_all();
}

photo_clipboard.on_pageload =
function on_pageload()
{
    window.addEventListener("storage", photo_clipboard.on_storage_event, false);
    hotkeys.register_hotkey("ctrl a", photo_clipboard.select_all_photos, "Select all photos.");
    hotkeys.register_hotkey("ctrl d", photo_clipboard.unselect_all_photos, "Deselect all photos.");
    hotkeys.register_hotkey("c", photo_clipboard.clipboard_tray_collapse_toggle, "Toggle clipboard tray.");
    hotkeys.register_hotkey("shift c", photo_clipboard.open_full_clipboard_tab, "Open full clipboard page.");
    photo_clipboard.ingest_toolbox_items();
    photo_clipboard.load_clipboard();
    photo_clipboard.update_pagestate();
}
document.addEventListener("DOMContentLoaded", photo_clipboard.on_pageload);
