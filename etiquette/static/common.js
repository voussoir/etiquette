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