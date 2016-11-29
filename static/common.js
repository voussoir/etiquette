function create_message_bubble(message_positivity, message_text, lifespan)
{
    if (lifespan === undefined)
    {
        lifespan = 8000;
    }
    var message = document.createElement("div");
    message.className = message_positivity;
    var span = document.createElement("span");
    span.innerHTML = message_text;
    message.appendChild(span);
    message_area.appendChild(message);
    setTimeout(function(){message_area.removeChild(message);}, lifespan);
}
function add_album_tag(albumid, tagname, callback)
{
    if (tagname === ""){return}
    var url = "/album/" + albumid;
    data = new FormData();
    data.append("add_tag", tagname);
    return post(url, data, callback);
}
function add_photo_tag(photoid, tagname, callback)
{
    if (tagname === ""){return}
    var url = "/photo/" + photoid;
    data = new FormData();
    data.append("add_tag", tagname);
    return post(url, data, callback);
}
function remove_photo_tag(photoid, tagname, callback)
{
    if (tagname === ""){return}
    var url = "/photo/" + photoid;
    data = new FormData();
    data.append("remove_tag", tagname);
    return post(url, data, callback);
}

function edit_tags(action, name, callback)
{
    if (name === ""){return}
    var url = "/tags";
    data = new FormData();
    data.append(action, name);
    return post(url, data, callback);    
}
function delete_tag_synonym(name, callback)
{
    return edit_tags("delete_tag_synonym", name, callback);
}
function delete_tag(name, callback)
{
    return edit_tags("delete_tag", name, callback);
}
function create_tag(name, callback)
{
    return edit_tags("create_tag", name, callback);
}

function post(url, data, callback)
{
    var request = new XMLHttpRequest();
    request.answer = null;
    request.onreadystatechange = function()
    {
        if (request.readyState == 4)
        {
            var text = request.responseText;
            if (callback != null)
            {
                console.log(text);
                callback(JSON.parse(text));
            }
        }
    };
    var asynchronous = true;
    request.open("POST", url, asynchronous);
    request.send(data);
}

function bind_box_to_button(box, button)
{
    box.onkeydown=function()
    {
        if (event.keyCode == 13)
        {
            button.click();
        }
    };
}
function entry_with_history_hook(box, button)
{
    //console.log(event.keyCode);
    if (box.entry_history === undefined)
    {box.entry_history = [];}
    if (box.entry_history_pos === undefined)
    {box.entry_history_pos = -1;}
    if (event.keyCode == 13)
    {
        /* Enter */
        box.entry_history.push(box.value);
        button.click();
        box.value = "";
    }
    else if (event.keyCode == 38)
    {

        /* Up arrow */
        if (box.entry_history.length == 0)
        {return}
        if (box.entry_history_pos == -1)
        {
            box.entry_history_pos = box.entry_history.length - 1;
        }
        else if (box.entry_history_pos > 0)
        {
            box.entry_history_pos -= 1;
        }
        box.value = box.entry_history[box.entry_history_pos];
    }
    else if (event.keyCode == 27)
    {
        box.value = "";
    }
    else
    {
        box.entry_history_pos = -1;
    }
}