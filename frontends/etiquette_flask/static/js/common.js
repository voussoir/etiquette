var common = {};

common.INPUT_TYPES = new Set(["INPUT", "TEXTAREA"]);

common._request =
function _request(method, url, callback)
{
    let request = new XMLHttpRequest();
    let response = {
        "completed": false,
    };

    request.onreadystatechange = function()
    {
        if (request.readyState != 4)
            {return;}

        if (callback == null)
            {return;}

        if (request.status != 0)
        {
            response.completed = true;
            response.data = JSON.parse(request.responseText);
        }
        response.meta = {
            "request_url": url,
            "status": request.status
        }
        callback(response);
    };
    let asynchronous = true;
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
    /*
    Bind a textbox to a button so that pressing Enter within the textbox is the
    same as clicking the button.

    If `ctrl_enter` is true, then you must press ctrl+Enter to trigger the
    button, which is important for textareas.

    Thanks Yaroslav Yakovlev
    http://stackoverflow.com/a/9343095
    */
    let bound_box_hook = function(event)
    {
        if (event.key !== "Enter")
            {return;}

        ctrl_success = !ctrl_enter || (event.ctrlKey);

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
    let message = document.createElement("div");
    message.className = "message_bubble " + message_positivity;
    let span = document.createElement("span");
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
    let box = event.target;

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

common.html_to_element =
function html_to_element(html)
{
    let template = document.createElement("template");
    template.innerHTML = html;
    return template.content.firstChild;
}

common.init_atag_merge_params =
function init_atag_merge_params()
{
    /*
    To create an <a> tag where the ?parameters written on the href are merged
    with the parameters of the current page URL, give it the class
    "merge_params". If the URL and href contain the same parameter, the href
    takes priority.

    Example:
        URL: ?filter=hello&orderby=score
        href: "?orderby=date"
        Result: "?filter=hello&orderby=date"
    */
    page_params = new URLSearchParams(window.location.search);
    let as = Array.from(document.getElementsByClassName("merge_params"));
    for (const a of as)
    {
        let a_params = new URLSearchParams(a.search);
        let new_params = new URLSearchParams();
        page_params.forEach(function(value, key) {new_params.set(key, value); });
        a_params.forEach(function(value, key) {new_params.set(key, value); });
        a.search = new_params.toString();
        a.classList.remove("merge_params");
    }
}

common.init_button_with_confirm =
function init_button_with_confirm()
{
    /*
    To create a button that requires a second confirmation step, assign it the
    class "button_with_confirm".

    Required:
        data-onclick: String that would normally be the button's onclick.
            This is done so that if the button_with_confirm fails to initialize,
            the button will be non-operational as opposed to being operational
            but with no confirmation. For dangerous actions I think this is a
            worthwhile move though it could lead to feature downtime.

    Optional:
        data-prompt: Text that appears next to the confirm button. Default is
            "Are you sure?".

        data-prompt-class: CSS class for the prompt span.

        data-confirm: Text inside the confirm button. Default is to inherit the
            original button's text.

        data-confirm-class: CSS class for the confirm button. Default is to
            inheret all classes of the original button, except for
            "button_with_confirm" of course.

        data-cancel: Text inside the cancel button. Default is "Cancel".

        data-cancel-class: CSS class for the cancel button.

        data-holder-class: CSS class for the new span that holds the menu.
    */
    let buttons = Array.from(document.getElementsByClassName("button_with_confirm"));
    for (const button of buttons)
    {
        button.classList.remove("button_with_confirm");

        let holder = document.createElement("span");
        holder.classList.add("confirm_holder");
        holder.classList.add(button.dataset.holderClass || "confirm_holder");
        button.parentElement.insertBefore(holder, button);
        button.parentElement.removeChild(button);

        let holder_stage1 = document.createElement("span");
        holder_stage1.classList.add("confirm_holder_stage1");
        holder_stage1.appendChild(button);
        holder.appendChild(holder_stage1);

        let holder_stage2 = document.createElement("span");
        holder_stage2.classList.add("confirm_holder_stage2");
        holder_stage2.classList.add("hidden");
        holder.appendChild(holder_stage2);

        let prompt;
        let input_source;
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

        let button_confirm = document.createElement("button");
        button_confirm.innerText = (button.dataset.confirm || button.innerText).trim();
        if (button.dataset.confirmClass === undefined)
        {
            button_confirm.className = button.className;
            button_confirm.classList.remove("button_with_confirm");
        }
        else
        {
            button_confirm.className = button.dataset.confirmClass;
        }
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

        let button_cancel = document.createElement("button");
        button_cancel.innerText = button.dataset.cancel || "Cancel";
        button_cancel.className = button.dataset.cancelClass || "";
        holder_stage2.appendChild(button_cancel);
        delete button.dataset.cancel;
        delete button.dataset.cancelClass;

        // If this is stupid, let me know.
        let confirm_onclick = button.dataset.onclick + `
            ;
            let holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
        `
        button_confirm.onclick = Function(confirm_onclick);
        button.removeAttribute("onclick");
        button.onclick = function(event)
        {
            let holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.add("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.remove("hidden");
            let input = holder.getElementsByTagName("input")[0];
            if (input)
            {
                input.focus();
            }
        }

        button_cancel.onclick = function(event)
        {
            let holder = event.target.parentElement.parentElement;
            holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
            holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
        }
        delete button.dataset.onclick;
    }
}

common.init_enable_on_pageload =
function init_enable_on_pageload()
{
    /*
    To create an input element which is disabled at first, and is enabled when
    the DOM has completed loading, give it the disabled attribute and the
    class "enable_on_pageload".
    */
    let elements = Array.from(document.getElementsByClassName("enable_on_pageload"));
    for (const element of elements)
    {
        element.disabled = false;
        element.classList.remove("enable_on_pageload");
    }
}

common.init_entry_with_history =
function init_entry_with_history()
{
    const inputs = Array.from(document.getElementsByClassName("entry_with_history"));
    for (const input of inputs)
    {
        input.addEventListener("keyup", common.entry_with_history_hook);
        input.classList.remove("entry_with_history");
    }
}

common.init_tabbed_container =
function init_tabbed_container()
{
    let switch_tab =
    function switch_tab(event)
    {
        let tab_button = event.target;
        if (tab_button.classList.contains("tab_button_active"))
            { return; }

        let tab_id = tab_button.dataset.tabId;
        let tab_buttons = tab_button.parentElement.getElementsByClassName("tab_button");
        let tabs = tab_button.parentElement.parentElement.getElementsByClassName("tab");
        for (const tab_button of tab_buttons)
        {
            if (tab_button.dataset.tabId === tab_id)
            {
                tab_button.classList.remove("tab_button_inactive");
                tab_button.classList.add("tab_button_active");
            }
            else
            {
                tab_button.classList.remove("tab_button_active");
                tab_button.classList.add("tab_button_inactive");
            }
        }
        for (const tab of tabs)
        {
            if (tab.dataset.tabId === tab_id)
                { tab.classList.remove("hidden"); }
            else
                { tab.classList.add("hidden"); }
        }
    }

    let tabbed_containers = Array.from(document.getElementsByClassName("tabbed_container"));
    for (const tabbed_container of tabbed_containers)
    {
        let button_container = document.createElement("div");
        button_container.className = "tab_buttons";
        tabbed_container.prepend(button_container);
        let tabs = Array.from(tabbed_container.getElementsByClassName("tab"));
        for (const tab of tabs)
        {
            tab.classList.add("hidden");
            let tab_id = tab.dataset.tabId || tab.dataset.tabTitle;
            tab.dataset.tabId = tab_id;
            tab.style.borderTopColor = "transparent";

            let button = document.createElement("button");
            button.className = "tab_button tab_button_inactive";
            button.onclick = switch_tab;
            button.innerText = tab.dataset.tabTitle;
            button.dataset.tabId = tab_id;
            button_container.append(button);
        }
        tabs[0].classList.remove("hidden");
        button_container.firstElementChild.classList.remove("tab_button_inactive");
        button_container.firstElementChild.classList.add("tab_button_active");
    }
}

common.refresh =
function refresh()
{
    window.location.reload();
}

common.on_pageload =
function on_pageload()
{
    common.init_atag_merge_params();
    common.init_button_with_confirm();
    common.init_enable_on_pageload();
    common.init_entry_with_history();
    common.init_tabbed_container();
}
document.addEventListener("DOMContentLoaded", common.on_pageload);
