function create_message_bubble(message_area, message_positivity, message_text, lifespan)
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

function post(url, data, callback)
{
    var request = new XMLHttpRequest();
    request.answer = null;
    request.onreadystatechange = function()
    {
        if (request.readyState == 4)
        {
            if (callback != null)
            {
                var text = request.responseText;
                console.log(request);
                console.log(text);
                var response = JSON.parse(text);
                response["_request_url"] = url;
                response["_status"] = status;
                callback(response);
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
        setTimeout(function(){box.selectionStart = box.value.length;}, 0);
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
