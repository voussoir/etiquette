var common = {};

common.INPUT_TYPES = new Set(["INPUT", "TEXTAREA"]);

common._request =
function _request(method, url, callback)
{
    var request = new XMLHttpRequest();
    request.onreadystatechange = function()
    {
        if (request.readyState == 4)
        {
            if (callback != null)
            {
                var response = {
                    "meta": {},
                    "data": JSON.parse(request.responseText)
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

common.get =
function get(url, callback)
{
    request = common._request("GET", url, callback);
    request.send();
}

common.post =
function post(url, data, callback)
{
    request = common._request("POST", url, callback);
    request.send(data);
}

common.bind_box_to_button =
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

common.create_message_bubble =
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

common.delete_all_children =
function delete_all_children(element)
{
    while (element.firstChild)
    {
        element.removeChild(element.firstChild);
    }
}

common.entry_with_history_hook =
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

common.entry_with_tagname_replacements =
function entry_with_tagname_replacements(event)
{
    var cursor_position = event.target.selectionStart;
    var new_value = common.tagname_replacements(event.target.value);
    if (new_value != event.target.value)
    {
        event.target.value = new_value;
        event.target.selectionStart = cursor_position;
        event.target.selectionEnd = cursor_position;
    }
}

common.html_to_element =
function html_to_element(html)
{
    var template = document.createElement("template");
    template.innerHTML = html;
    return template.content.firstChild;
}

common.init_button_with_confirm =
function init_button_with_confirm()
{
    /*
    To create a button that requires a second confirmation step, assign it the
    class "button_with_confirm".

    Required:
        data-onclick: String that would normally be the button's onclick.

    Optional:
        data-prompt: Text that appears next to the confirm button. Default is
            "Are you sure?".
        data-prompt-class

        data-confirm: Text inside the confirm button. Default is to inherit the
            original button's text.
        data-confirm-class

        data-cancel: Text inside the cancel button. Default is "Cancel".
        data-cancel-class

        data-holder-class: CSS class for the new span that holds the menu.
    */
    var buttons = Array.from(document.getElementsByClassName("button_with_confirm"));
    buttons.forEach(function(button)
    {
        button.classList.remove("button_with_confirm");

        var holder = document.createElement("span");
        holder.classList.add("confirm_holder");
        holder.classList.add(button.dataset.holderClass || "confirm_holder");
        button.parentElement.insertBefore(holder, button);
        button.parentElement.removeChild(button);

        var holder_stage1 = document.createElement("span");
        holder_stage1.classList.add("confirm_holder_stage1");
        holder_stage1.appendChild(button);
        holder.appendChild(holder_stage1);

        var holder_stage2 = document.createElement("span");
        holder_stage2.classList.add("confirm_holder_stage2");
        holder_stage2.classList.add("hidden");
        holder.appendChild(holder_stage2);

        var prompt;
        var input_source;
        if (button.dataset.isInput)
        {
            prompt = document.createElement("input");
            prompt.placeholder = button.dataset.prompt || "";
            input_source = prompt;
        }
        else
        {
            prompt = document.createElement("span");
            prompt.innerText = (button.dataset.prompt || "Are you sure?") + " ";
            input_source = undefined;
        }
        prompt.className = button.dataset.promptClass || "";
        holder_stage2.appendChild(prompt)
        delete button.dataset.prompt;
        delete button.dataset.promptClass;

        var button_confirm = document.createElement("button");
        button_confirm.innerText = (button.dataset.confirm || button.innerText).trim();
        button_confirm.className = button.dataset.confirmClass || "";
        button_confirm.input_source = input_source;
        holder_stage2.appendChild(button_confirm);
        holder_stage2.appendChild(document.createTextNode(" "));
        if (button.dataset.isInput)
        {
            common.bind_box_to_button(prompt, button_confirm);
        }
        delete button.dataset.confirm;
        delete button.dataset.confirmClass;
        delete button.dataset.isInput;

        var button_cancel = document.createElement("button");
        button_cancel.innerText = button.dataset.cancel || "Cancel";
        button_cancel.className = button.dataset.cancelClass || "";
        holder_stage2.appendChild(button_cancel);
        delete button.dataset.cancel;
        delete button.dataset.cancelClass;

        // If this is stupid, let me know.
        var confirm_onclick = button.dataset.onclick + `
            ;
            var holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
        `
        button_confirm.onclick = Function(confirm_onclick);
        button.removeAttribute("onclick");
        button.onclick = function(event)
        {
            var holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.add("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.remove("hidden");
            var input = holder.getElementsByTagName("input")[0];
            if (input)
            {
                input.focus();
            }
        }

        button_cancel.onclick = function(event)
        {
            var holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
        }
        delete button.dataset.onclick;
    });
}

common.spinner_button_index = 0;
common.button_spinner_groups = {};
// When a group member is closing, it will call the closer on all other members
// in the group. Of course, this would recurse forever without some kind of
// flagging, so this dict will hold group_id:true if a close is in progress,
// and be empty otherwise.
common.spinner_group_closing = {};

common.add_to_spinner_group =
function add_to_spinner_group(group_id, button)
{
    if (!(group_id in common.button_spinner_groups))
    {
        common.button_spinner_groups[group_id] = [];
    }
    common.button_spinner_groups[group_id].push(button);
}

common.close_grouped_spinners =
function close_grouped_spinners(group_id)
{
    if (group_id && !(common.spinner_group_closing[group_id]))
    {
        common.spinner_group_closing[group_id] = true;
        common.button_spinner_groups[group_id].forEach(function(button)
        {
            window[button.dataset.spinnerCloser]();
        });
        delete common.spinner_group_closing[group_id];
    }
}

common.open_grouped_spinners =
function open_grouped_spinners(group_id)
{
    common.button_spinner_groups[group_id].forEach(function(button)
    {
        window[button.dataset.spinnerOpener]();
    });
}

common.init_button_with_spinner =
function init_button_with_spinner()
{
    /*
    To create a button that has a spinner, and cannot be clicked again while
    the action is running, assign it the class "button_with_spinner".
    When you're ready for the spinner to disappear, call
    window[button.dataset.spinnerCloser]().

    Required:
        data-onclick: The string that would normally be the button's onclick.

    Optional:
        data-spinner-id: If you want to use your own element as the spinner,
            give its ID here. Otherwise a new one will be created.

        data-spinner-delay: The number of milliseconds to wait before the
            spinner appears. For tasks that you expect to run very quickly,
            this helps prevent a pointlessly short spinner.

        data-holder-class: CSS class for the new span that holds the menu.

        data-spinner-group: An opaque string. All button_with_spinner that have
            the same group will go into spinner mode when any of them is
            clicked. Useful if you want to have two copies of a button on the
            page, or two buttons which do opposite things and you only want one
            to run at a time.
    */
    var buttons = Array.from(document.getElementsByClassName("button_with_spinner"));
    buttons.forEach(function(button)
    {
        button.classList.remove("button_with_spinner");
        button.innerHTML = button.innerHTML.trim();

        var holder = document.createElement("span");
        holder.classList.add("spinner_holder");
        holder.classList.add(button.dataset.holderClass || "spinner_holder");
        button.parentElement.insertBefore(holder, button);
        button.parentElement.removeChild(button);
        holder.appendChild(button);

        var spinner_element;
        if (button.dataset.spinnerId)
        {
            spinner_element = document.getElementById(button.dataset.spinnerId);
        }
        else
        {
            spinner_element = document.createElement("span");
            spinner_element.innerText = "Working...";
            spinner_element.classList.add("hidden");
            holder.appendChild(spinner_element);
        }

        if (button.dataset.spinnerGroup)
        {
            common.add_to_spinner_group(button.dataset.spinnerGroup, button);
        }

        var spin = new spinner.Spinner(spinner_element);
        var spin_delay = parseFloat(button.dataset.spinnerDelay) || 0;

        button.dataset.spinnerOpener = "spinner_opener_" + common.spinner_button_index;
        window[button.dataset.spinnerOpener] = function spinner_opener()
        {
            spin.show(spin_delay);
            button.disabled = true;
        }
        // It is expected that the function referenced by data-onclick will call
        // window[button.dataset.spinnerCloser]() when appropriate, since from
        // our perspective we cannot be sure when to close the spinner.
        button.dataset.spinnerCloser = "spinner_closer_" + common.spinner_button_index;
        window[button.dataset.spinnerCloser] = function spinner_closer()
        {
            common.close_grouped_spinners(button.dataset.spinnerGroup);
            spin.hide();
            button.disabled = false;
        }

        var wrapped_onclick = Function(button.dataset.onclick);
        button.onclick = function()
        {
            if (button.dataset.spinnerGroup)
            {
                common.open_grouped_spinners(button.dataset.spinnerGroup);
            }
            else
            {
                window[button.dataset.spinnerOpener]();
            }
            return wrapped_onclick();
        }
        delete button.dataset.onclick;

        common.spinner_button_index += 1;
    });
}

common.normalize_tagname =
function normalize_tagname(tagname)
{
    tagname = tagname.trim();
    tagname = tagname.toLocaleLowerCase();
    tagname = tagname.split(".");
    tagname = tagname[tagname.length-1];
    tagname = tagname.split("+")[0];
    tagname = common.tagname_replacements(tagname);
    return tagname;
}

common.tagname_replacements =
function tagname_replacements(tagname)
{
    tagname = tagname.replace(new RegExp(" ", 'g'), "_");
    tagname = tagname.replace(new RegExp("-", 'g'), "_");
    return tagname;
}

common.refresh =
function refresh()
{
    window.location.reload();
}

common.on_pageload =
function on_pageload()
{
    common.init_button_with_confirm();
    common.init_button_with_spinner();
}
document.addEventListener("DOMContentLoaded", common.on_pageload);
