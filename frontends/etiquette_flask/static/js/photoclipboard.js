var photo_clipboard = new Set();
var on_clipboard_load_hooks = [];
var on_clipboard_save_hooks = [];

// Load save ///////////////////////////////////////////////////////////////////////////////////////

function clear_photo_clipboard()
{
    photo_clipboard.clear();
    save_photo_clipboard();
}

function load_photo_clipboard(event)
{
    console.log("Loading photo clipboard");
    var stored = localStorage.getItem("photo_clipboard");
    if (stored === null)
    {
        if (photo_clipboard.size != 0)
        {
            photo_clipboard = new Set();
        }
    }
    else
    {
        photo_clipboard = new Set(JSON.parse(stored));
    }

    for (var index = 0; index < on_clipboard_load_hooks.length; index += 1)
    {
        on_clipboard_load_hooks[index]();
    }

    return photo_clipboard;
}

function save_photo_clipboard()
{
    console.log("Saving photo clipboard");
    var serialized = JSON.stringify(Array.from(photo_clipboard));
    localStorage.setItem("photo_clipboard", serialized);
    update_pagestate();

    for (var index = 0; index < on_clipboard_save_hooks.length; index += 1)
    {
        on_clipboard_save_hooks[index]();
    }
}


// Card management /////////////////////////////////////////////////////////////////////////////////

function apply_check(photo_card)
{
    /*
    Given a photo card div, set its checkbox to the correct value based on
    whether the clipboard contains this card's ID.
    */
    var checkbox = photo_card.getElementsByClassName("photo_card_selector_checkbox")[0];
    if (photo_clipboard.has(photo_card.dataset.id))
    {
        checkbox.checked = true;
    }
    else
    {
        checkbox.checked = false;
    }
}

function apply_check_all()
{
    /*
    Run through all the photo cards on the page and set their checkbox to the
    correct value.
    */
    var photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(apply_check);
}

var previous_photo_select;
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
        action = function(photo_div)
        {
            photo_div.getElementsByClassName("photo_card_selector_checkbox")[0].checked = true;
            photo_clipboard.add(photo_div.dataset.id);
        }
    }
    else
    {
        action = function(photo_div)
        {
            photo_div.getElementsByClassName("photo_card_selector_checkbox")[0].checked = false;
            photo_clipboard.delete(photo_div.dataset.id);
        }
    }

    if (event.shiftKey && previous_photo_select !== undefined)
    {
        var current_photo_div = event.target.parentElement;
        var previous_photo_div = previous_photo_select.target.parentElement;
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
    previous_photo_select = event;
    save_photo_clipboard();
}


// Tray management /////////////////////////////////////////////////////////////////////////////////

function clipboard_tray_collapse()
{
    var tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.add("hidden");
}
function clipboard_tray_uncollapse()
{
    var tray_body = document.getElementById("clipboard_tray_body");
    tray_body.classList.remove("hidden");
    update_clipboard_tray();
}
function clipboard_tray_collapse_toggle()
{
    /*
    Show or hide the clipboard.
    */
    var tray_body = document.getElementById("clipboard_tray_body");
    if (tray_body.classList.contains("hidden") && photo_clipboard.size > 0)
    {
        clipboard_tray_uncollapse();
    }
    else
    {
        clipboard_tray_collapse();
    }
}

function on_tray_delete_button(event)
{
    /*
    Remove the clicked row from the clipboard.
    */
    var clipboard_line = event.target.parentElement;
    var photo_id = clipboard_line.dataset.id;
    photo_clipboard.delete(photo_id);
    save_photo_clipboard();
}

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

    if (photo_clipboard.size == 0)
    {
        clipboard_tray_collapse();
    }

    var tray_lines = document.getElementById("clipboard_tray_lines");
    if (!clipboard_tray.classList.contains("hidden"))
    {
        delete_all_children(tray_lines);
        var photo_ids = Array.from(photo_clipboard);
        photo_ids.sort();
        for (var i = 0; i < photo_ids.length; i += 1)
        {
            var clipboard_line = document.createElement("div");
            clipboard_line.classList.add("clipboard_tray_line");
            clipboard_line.dataset.id = photo_ids[i];

            var clipboard_line_delete_button = document.createElement("button");
            clipboard_line_delete_button.classList.add("remove_tag_button_perm");
            clipboard_line_delete_button.classList.add("red_button");
            clipboard_line_delete_button.onclick = on_tray_delete_button;

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

function update_clipboard_count()
{
    var elements = document.getElementsByClassName("clipboard_count");
    for (var index = 0; index < elements.length; index += 1)
    {
        elements[index].innerText = photo_clipboard.size;
    }
}
function on_storage()
{
    /*
    Receive storage events from other tabs and update our state to match.
    */
    load_photo_clipboard();
    update_pagestate();
}
function update_pagestate()
{
    update_clipboard_count();
    update_clipboard_tray();
    apply_check_all();
}
function on_pageload()
{
    window.addEventListener("storage", on_storage, false);
    on_storage();
}
document.addEventListener("DOMContentLoaded", on_pageload);
