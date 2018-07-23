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
    console.log("Loading photo clipboard.");
    var stored = localStorage.getItem("photo_clipboard");
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

    for (var index = 0; index < photo_clipboard.on_load_hooks.length; index += 1)
    {
        photo_clipboard.on_load_hooks[index]();
    }

    return photo_clipboard.clipboard;
}

photo_clipboard.save_clipboard =
function save_clipboard()
{
    console.log("Saving photo clipboard.");
    var serialized = JSON.stringify(Array.from(photo_clipboard.clipboard));
    localStorage.setItem("photo_clipboard", serialized);
    photo_clipboard.update_pagestate();

    for (var index = 0; index < photo_clipboard.on_save_hooks.length; index += 1)
    {
        photo_clipboard.on_save_hooks[index]();
    }
}

// Card management /////////////////////////////////////////////////////////////////////////////////

photo_clipboard.apply_check =
function apply_check(photo_card)
{
    /*
    Given a photo card div, set its checkbox to the correct value based on
    whether the clipboard contains this card's ID.
    */
    var checkbox = photo_card.getElementsByClassName("photo_card_selector_checkbox")[0];
    if (photo_clipboard.clipboard.has(photo_card.dataset.id))
    {
        checkbox.checked = true;
    }
    else
    {
        checkbox.checked = false;
    }
}

photo_clipboard.apply_check_all =
function apply_check_all()
{
    /*
    Run through all the photo cards on the page and set their checkbox to the
    correct value.
    */
    var photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(photo_clipboard.apply_check);
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
        var current_photo_div = event.target.parentElement;
        var previous_photo_div = photo_clipboard.previous_photo_select.target.parentElement;
        var photo_divs = Array.from(current_photo_div.parentElement.children);

        var current_index = photo_divs.indexOf(current_photo_div);
        var previous_index = photo_divs.indexOf(previous_photo_div);

        var slice;
        if (current_index == previous_index)
        {
            slice = [current_photo_div];
        }
        else if (previous_index < current_index)
        {
            slice = photo_divs.slice(previous_index, current_index + 1);
        }
        else
        {
            slice = photo_divs.slice(current_index, previous_index + 1);
        }

        slice.forEach(action);
    }
    else
    {
        var photo_div = event.target.parentElement;
        action(photo_div);
    }
    photo_clipboard.previous_photo_select = event;
    photo_clipboard.save_clipboard();
}

photo_clipboard.select_photo =
function select_photo(photo_div)
{
    photo_div.getElementsByClassName("photo_card_selector_checkbox")[0].checked = true;
    photo_clipboard._action_select(photo_div);
    photo_clipboard.save_clipboard();
}

photo_clipboard.unselect_photo =
function unselect_photo(photo_div)
{
    photo_div.getElementsByClassName("photo_card_selector_checkbox")[0].checked = false;
    photo_clipboard._action_unselect(photo_div)
    photo_clipboard.save_clipboard();
}

photo_clipboard.select_all_photos =
function select_all_photos()
{
    var photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(photo_clipboard._action_select);
    photo_clipboard.apply_check_all();
    photo_clipboard.save_clipboard();
}

photo_clipboard.unselect_all_photos =
function unselect_all_photos()
{
    var photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(photo_clipboard._action_unselect);
    photo_clipboard.apply_check_all()
    photo_clipboard.previous_photo_select = null;
    photo_clipboard.save_clipboard();
}

// Tray management /////////////////////////////////////////////////////////////////////////////////

photo_clipboard.clipboard_tray_collapse =
function clipboard_tray_collapse()
{
    var tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.add("hidden");
}

photo_clipboard.clipboard_tray_uncollapse =
function clipboard_tray_uncollapse()
{
    var tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.remove("hidden");
    photo_clipboard.update_clipboard_tray();
}

photo_clipboard.clipboard_tray_collapse_toggle =
function clipboard_tray_collapse_toggle()
{
    /*
    Show or hide the clipboard.
    */
    var tray_body = document.getElementById("clipboard_tray_body");
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

photo_clipboard.on_tray_delete_button =
function on_tray_delete_button(event)
{
    /*
    Remove the clicked row from the clipboard.
    */
    var clipboard_line = event.target.parentElement;
    var photo_id = clipboard_line.dataset.id;
    photo_clipboard.clipboard.delete(photo_id);
    photo_clipboard.save_clipboard();
}

photo_clipboard.update_clipboard_tray =
function update_clipboard_tray()
{
    /*
    Rebuild the rows if the tray is open.
    */
    var clipboard_tray = document.getElementById("clipboard_tray");
    if (clipboard_tray === null)
    {
        return;
    }

    if (photo_clipboard.clipboard.size == 0)
    {
        photo_clipboard.clipboard_tray_collapse();
    }

    var tray_lines = document.getElementById("clipboard_tray_lines");
    if (!clipboard_tray.classList.contains("hidden"))
    {
        common.delete_all_children(tray_lines);
        var photo_ids = Array.from(photo_clipboard.clipboard);
        photo_ids.sort();
        for (var i = 0; i < photo_ids.length; i += 1)
        {
            var clipboard_line = document.createElement("div");
            clipboard_line.classList.add("clipboard_tray_line");
            clipboard_line.dataset.id = photo_ids[i];

            var clipboard_line_delete_button = document.createElement("button");
            clipboard_line_delete_button.classList.add("remove_tag_button_perm");
            clipboard_line_delete_button.classList.add("red_button");
            clipboard_line_delete_button.onclick = photo_clipboard.on_tray_delete_button;

            var clipboard_line_link = document.createElement("a");
            clipboard_line_link.target = "_blank";
            clipboard_line_link.href = "/photo/" + photo_ids[i];
            clipboard_line_link.innerText = photo_ids[i];

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
    var url = "/clipboard";
    window.open(url, "full_clipboard");
}

photo_clipboard.update_clipboard_count =
function update_clipboard_count()
{
    var elements = document.getElementsByClassName("clipboard_count");
    for (var index = 0; index < elements.length; index += 1)
    {
        elements[index].innerText = photo_clipboard.clipboard.size;
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
    photo_clipboard.update_clipboard_count();
    photo_clipboard.update_clipboard_tray();
    photo_clipboard.apply_check_all();
}

photo_clipboard.on_pageload =
function on_pageload()
{
    window.addEventListener("storage", photo_clipboard.on_storage_event, false);
    register_hotkey("a", 1, 0, 0, photo_clipboard.select_all_photos, "Select all photos.");
    register_hotkey("d", 1, 0, 0, photo_clipboard.unselect_all_photos, "Deselect all photos.");
    register_hotkey("c", 0, 0, 0, photo_clipboard.clipboard_tray_collapse_toggle, "Toggle clipboard tray.");
    register_hotkey("c", 0, 1, 0, photo_clipboard.open_full_clipboard_tab, "Open full clipboard page.");
    photo_clipboard.load_clipboard();
    photo_clipboard.update_pagestate();
}
document.addEventListener("DOMContentLoaded", photo_clipboard.on_pageload);
