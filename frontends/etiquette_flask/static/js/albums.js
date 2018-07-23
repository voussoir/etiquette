var albums = {};

albums.create_child_prompt_button = null;
albums.create_child_title_entry = null;
albums.create_child_submit_button = null;
albums.create_child_cancel_button = null;

albums.open_creator_prompt =
function open_creator_prompt(event)
{
    albums.create_child_prompt_button.classList.add("hidden");
    albums.create_child_title_entry.classList.remove("hidden");
    albums.create_child_title_entry.focus();
    albums.create_child_submit_button.classList.remove("hidden");
    albums.create_child_cancel_button.classList.remove("hidden");
}

albums.cancel_create_child =
function cancel_create_child(event)
{
    albums.create_child_prompt_button.classList.remove("hidden");
    albums.create_child_title_entry.value = "";
    albums.create_child_title_entry.classList.add("hidden");
    albums.create_child_submit_button.classList.add("hidden");
    albums.create_child_cancel_button.classList.add("hidden");
}

albums.create_album_and_follow =
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
    common.post(url, data, receive_callback);
}

albums.submit_create_child =
function submit_create_child(event)
{
    var title = document.getElementById("create_child_title_entry").value;
    if (! title)
    {
        title = undefined;
    }
    var parent_id = ALBUM_ID;
    albums.create_album_and_follow(title, parent_id);
}

albums.on_pageload =
function on_pageload()
{
    albums.create_child_prompt_button = document.getElementById("create_child_prompt_button");
    albums.create_child_title_entry = document.getElementById("create_child_title_entry");
    albums.create_child_submit_button = document.getElementById("create_child_submit_button");
    albums.create_child_cancel_button = document.getElementById("create_child_cancel_button");
    common.bind_box_to_button(albums.create_child_title_entry, albums.create_child_submit_button);
}
document.addEventListener("DOMContentLoaded", albums.on_pageload);
