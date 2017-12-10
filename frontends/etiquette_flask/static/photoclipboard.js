var photo_clipboard = new Set();

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

    var photo_divs = Array.from(document.getElementsByClassName("photo_card"));
    photo_divs.forEach(apply_check);
    return photo_clipboard;
}

function save_photo_clipboard()
{
    console.log("Saving photo clipboard");
    var serialized = JSON.stringify(Array.from(photo_clipboard));
    localStorage.setItem("photo_clipboard", serialized);
}

function apply_check(photo_div)
{
    var checkbox = photo_div.getElementsByClassName("photo_card_selector_checkbox")[0];
    if (photo_clipboard.has(photo_div.dataset.id))
    {
        checkbox.checked = true;
    }
    else
    {
        checkbox.checked = false;
    }
}

var previous_photo_select;
function on_photo_select(event)
{
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

function onpageload()
{
    window.addEventListener("storage", load_photo_clipboard, false);
    load_photo_clipboard();
}
document.addEventListener("DOMContentLoaded", onpageload);
