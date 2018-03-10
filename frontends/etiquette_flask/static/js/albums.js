var create_child_prompt_button;
var create_child_title_entry;
var create_child_submit_button;
var create_child_cancel_button;

console.log(create_child_title_entry);
function on_pageload()
{
    create_child_prompt_button = document.getElementById("create_child_prompt_button");
    create_child_title_entry = document.getElementById("create_child_title_entry");
    create_child_submit_button = document.getElementById("create_child_submit_button");
    create_child_cancel_button = document.getElementById("create_child_cancel_button");
    bind_box_to_button(create_child_title_entry, create_child_submit_button);
}
document.addEventListener("DOMContentLoaded", on_pageload);


function open_creator_prompt(event)
{
    create_child_prompt_button.classList.add("hidden");
    create_child_title_entry.classList.remove("hidden");
    create_child_title_entry.focus();
    create_child_submit_button.classList.remove("hidden");
    create_child_cancel_button.classList.remove("hidden");
}

function cancel_create_child(event)
{
    create_child_prompt_button.classList.remove("hidden");
    create_child_title_entry.value = "";
    create_child_title_entry.classList.add("hidden");
    create_child_submit_button.classList.add("hidden");
    create_child_cancel_button.classList.add("hidden");
}

function create_album_and_follow(title, parent)
{
    var url = "/albums/create_album";
    var data = new FormData();
    if (title !== undefined)
    {
        data.append("title", title);
    }
    if (parent !== undefined)
    {
        data.append("parent", parent);
    }
    function receive_callback(response)
    {
        if (response["meta"]["status"] == 200 && response["data"]["id"])
        {
            window.location.href = "/album/" + response["data"]["id"];
        }
        else
        {
            console.log(response);
        }
    }
    post(url, data, receive_callback);
}

function submit_create_child(event)
{
    var title = document.getElementById("create_child_title_entry").value;
    if (! title)
    {
        title = undefined;
    }
    var parent_id = ALBUM_ID;
    create_album_and_follow(title, parent_id);
}
