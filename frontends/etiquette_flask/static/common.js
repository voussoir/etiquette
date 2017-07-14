function Editor(elements, on_open, on_save, on_cancel)
{
    /*
    This class wraps around display elements like headers and paragraphs, and
    creates inputs / textareas to edit them with.

    The placeholder text for the edit elements comes from the
    data-editor-placeholder attribute of the display elements if available.

    The on_open, on_save and on_cancel callbacks will receive two arguments:
        1. This editor object.
        2. the edit elements as either:
            If the display elements ALL have data-editor-id attributes,
            then a dictionary of {data-editor-id: edit_element, ...}.
            Otherwise, an array of [edit_element, ...] in their original order.

    When your callbacks are used, the default `open`, `save`, `cancel`
    methods are not called automatically. You should call them from within
    your function.
    */
    this.cancel = function()
    {
        this.close();
    };

    this.close = function()
    {
        for (var index = 0; index < this.display_elements.length; index += 1)
        {
            this.display_elements[index].classList.remove("hidden");
            this.edit_elements[index].classList.add("hidden");
        }
        this.open_button.classList.remove("hidden")
        this.save_button.classList.add("hidden");
        this.cancel_button.classList.add("hidden");
    };

    this.hide_spinner = function()
    {
        this.spinner.classList.add("hidden");
    };

    this.open = function()
    {
        for (var index = 0; index < this.display_elements.length; index += 1)
        {
            var display_element = this.display_elements[index];
            var edit_element = this.edit_elements[index];
            display_element.classList.add("hidden");
            edit_element.classList.remove("hidden");

            var empty_text = display_element.dataset.editorEmptyText;
            if (empty_text !== undefined && display_element.innerText == empty_text)
            {
                edit_element.value = "";
            }
            else
            {
                edit_element.value = display_element.innerText;
            }
        }
        this.open_button.classList.add("hidden")
        this.save_button.classList.remove("hidden");
        this.cancel_button.classList.remove("hidden");
    };

    this.save = function()
    {
        for (var index = 0; index < this.display_elements.length; index += 1)
        {
            var display_element = this.display_elements[index];
            var edit_element = this.edit_elements[index];

            if (display_element.dataset.editorEmptyText !== undefined && edit_element.value == "")
            {
                display_element.innerText = display_element.dataset.editorEmptyText;
            }
            else
            {
                display_element.innerText = edit_element.value;
            }
        }

        this.close();
    };

    this.show_spinner = function()
    {
        this.spinner.classList.remove("hidden");
    };

    this.display_elements = [];
    this.edit_elements = [];
    this.can_use_element_map = true;
    this.edit_element_map = {};

    this.misc_data = {};

    for (var index = 0; index < elements.length; index += 1)
    {
        var display_element = elements[index];
        var edit_element;
        if (display_element.tagName == "P")
        {
            edit_element = document.createElement("textarea");
            edit_element.rows = 6;
        }
        else
        {
            edit_element = document.createElement("input");
            edit_element.type = "text";
        }
        edit_element.classList.add("editor_input");
        edit_element.classList.add("hidden");
        if (display_element.dataset.editorPlaceholder !== undefined)
        {
            edit_element.placeholder = display_element.dataset.editorPlaceholder;
        }
        if (this.can_use_element_map)
        {
            if (display_element.dataset.editorId !== undefined)
            {
                this.edit_element_map[display_element.dataset.editorId] = edit_element;
            }
            else
            {
                this.can_use_element_map = false;
                this.edit_element_map = null;
            }
        }

        display_element.parentElement.insertBefore(edit_element, display_element.nextSibling);

        this.display_elements.push(display_element);
        this.edit_elements.push(edit_element);
    }

    var self = this;
    var binder = function(func, fallback)
    {
        if (func == undefined)
        {
            return fallback;
        }

        var bound = function()
        {
            if (this.can_use_element_map)
            {
                func(self, self.edit_element_map);
            }
            else
            {
                func(self, self.edit_elements);
            }
        }
        return bound;
    }

    this.bound_open = binder(on_open, this.open);
    this.bound_save = binder(on_save, this.save);
    this.bound_cancel = binder(on_cancel, this.cancel);

    var last_element = this.edit_elements[this.edit_elements.length - 1];
    var toolbox = document.createElement("div");
    last_element.parentElement.insertBefore(toolbox, last_element.nextSibling);

    this.open_button = document.createElement("button");
    this.open_button.innerText = "Edit";
    this.open_button.classList.add("editor_button");
    this.open_button.classList.add("editor_open_button");
    this.open_button.onclick = this.bound_open.bind(this);
    toolbox.appendChild(this.open_button);

    this.save_button = document.createElement("button");
    this.save_button.innerText = "Save";
    this.save_button.classList.add("editor_button");
    this.save_button.classList.add("editor_save_button");
    this.save_button.classList.add("hidden");
    this.save_button.onclick = this.bound_save.bind(this);
    toolbox.appendChild(this.save_button);

    this.cancel_button = document.createElement("button");
    this.cancel_button.innerText = "Cancel";
    this.cancel_button.classList.add("editor_button");
    this.cancel_button.classList.add("editor_cancel_button");
    this.cancel_button.classList.add("hidden");
    this.cancel_button.onclick = this.bound_cancel.bind(this);
    toolbox.appendChild(this.cancel_button);

    this.spinner = document.createElement("span");
    this.spinner.innerText = "Submitting...";
    this.spinner.classList.add("editor_spinner");
    this.spinner.classList.add("hidden");
    toolbox.appendChild(this.spinner);

    for (var index = 0; index < this.edit_elements.length; index += 1)
    {
        var edit_element = this.edit_elements[index];
        if (edit_element.tagName == "TEXTAREA")
        {
            bind_box_to_button(edit_element, this.save_button, true);
        }
        else
        {
            bind_box_to_button(edit_element, this.save_button, false);
        }
    }
}

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

function post(url, data, callback)
{
    var request = new XMLHttpRequest();
    request.onreadystatechange = function()
    {
        if (request.readyState == 4)
        {
            if (callback != null)
            {
                var text = request.responseText;
                var response = JSON.parse(text);
                response["_request_url"] = url;
                response["_status"] = request.status;
                callback(response);
            }
        }
    };
    var asynchronous = true;
    request.open("POST", url, asynchronous);
    request.send(data);
}

function bind_box_to_button(box, button, ctrl_enter)
{
    box.onkeydown=function()
    {
        // Thanks Yaroslav Yakovlev
        // http://stackoverflow.com/a/9343095
        if (
            (event.keyCode == 13 || event.keyCode == 10) &&
            ((ctrl_enter && event.ctrlKey) || (!ctrl_enter))
        )
        {
            button.click();
        }
    };
}

function create_album_and_follow(parent)
{
    var url = "/albums/create_album";
    var data = new FormData();
    if (parent !== undefined)
    {
        data.append("parent", parent);
    }
    function receive_callback(response)
    {
        window.location.href = "/album/" + response["id"];
    }
    post(url, data, receive_callback);
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
