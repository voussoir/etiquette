function create_message_bubble(message_area, message_positivity, message_text, lifespan)
{
    if (lifespan === undefined)
    {
        lifespan = 8000;
    }
    var message = document.createElement("div");
    message.className = "message_bubble " + message_positivity;
    var span = document.createElement("span");
    span.innerHTML = message_text;
    message.appendChild(span);
    message_area.appendChild(message);
    setTimeout(function(){message_area.removeChild(message);}, lifespan);
}

function _request(method, url, callback)
{
    var request = new XMLHttpRequest();
    request.onreadystatechange = function()
    {
        if (request.readyState == 4)
        {
            if (callback != null)
            {
                var text = request.responseText;
                var response = {
                    "data": JSON.parse(text),
                    "meta": {}
                };
                response["meta"]["request_url"] = url;
                response["meta"]["status"] = request.status;
                callback(response);
            }
        }
    };
    var asynchronous = true;
    request.open(method, url, asynchronous);
    return request;
}
function get(url, callback)
{
    request = _request("GET", url, callback);
    request.send();
}
function post(url, data, callback)
{
    request = _request("POST", url, callback);
    request.send(data);
}

function delete_all_children(element)
{
    while (element.firstChild)
    {
        element.removeChild(element.firstChild);
    }
}

function bind_box_to_button(box, button, ctrl_enter)
{
    // Thanks Yaroslav Yakovlev
    // http://stackoverflow.com/a/9343095
    var bound_box_hook = function(event)
    {
        if (event.key !== "Enter")
            {return;}

        ctrl_success = !ctrl_enter || (event.ctrlKey)

        if (! ctrl_success)
            {return;}

        button.click();
    }
    box.addEventListener("keyup", bound_box_hook);
}

function entry_with_history_hook(event)
{
    //console.log(event);
    var box = event.target;

    if (box.entry_history === undefined)
        {box.entry_history = [];}

    if (box.entry_history_pos === undefined)
        {box.entry_history_pos = -1;}

    if (event.key === "Enter")
    {
        box.entry_history.push(box.value);
    }
    else if (event.key === "ArrowUp")
    {
        if (box.entry_history.length == 0)
            {return}

        if (box.entry_history_pos == -1)
            {box.entry_history_pos = box.entry_history.length - 1;}
        else if (box.entry_history_pos > 0)
            {box.entry_history_pos -= 1;}

        box.value = box.entry_history[box.entry_history_pos];
        setTimeout(function(){box.selectionStart = box.value.length;}, 0);
    }
    else if (event.key === "Escape")
    {
        box.value = "";
    }
    else
    {
        box.entry_history_pos = -1;
    }
}

function html_to_element(html)
{
    var template = document.createElement("template");
    template.innerHTML = html;
    return template.content.firstChild;
}
