const common = {};

common.INPUT_TYPES = new Set(["INPUT", "TEXTAREA"]);

////////////////////////////////////////////////////////////////////////////////////////////////////
// UTILS ///////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

common.create_message_bubble =
function create_message_bubble(message_area, message_positivity, message_text, lifespan)
{
    if (lifespan === undefined)
    {
        lifespan = 8000;
    }
    const message = document.createElement("div");
    message.className = "message_bubble " + message_positivity;
    const span = document.createElement("span");
    span.innerHTML = message_text;
    message.appendChild(span);
    message_area.appendChild(message);
    setTimeout(function(){message_area.removeChild(message);}, lifespan);
}

common.is_narrow_mode =
function is_narrow_mode()
{
    return getComputedStyle(document.documentElement).getPropertyValue("--narrow").trim() === "1";
}

common.is_wide_mode =
function is_wide_mode()
{
    return getComputedStyle(document.documentElement).getPropertyValue("--wide").trim() === "1";
}

common.go_to_root =
function go_to_root()
{
    window.location.href = "/";
}

common.refresh =
function refresh()
{
    window.location.reload();
}

common.refresh_or_alert =
function refresh_or_alert(response)
{
    if (response.meta.status !== 200)
    {
        alert(JSON.stringify(response));
        return;
    }
    window.location.reload();
}

////////////////////////////////////////////////////////////////////////////////////////////////////
// STRING TOOLS ////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

common.join_and_trail =
function join_and_trail(list, separator)
{
    if (list.length === 0)
    {
        return "";
    }
    return list.join(separator) + separator
}

common.hms_render_colons =
function hms_render_colons(hours, minutes, seconds)
{
    const parts = [];
    if (hours !== null)
    {
        parts.push(hours.toLocaleString(undefined, {minimumIntegerDigits: 2}));
    }
    if (minutes !== null)
    {
        parts.push(minutes.toLocaleString(undefined, {minimumIntegerDigits: 2}));
    }
    parts.push(seconds.toLocaleString(undefined, {minimumIntegerDigits: 2}));
    return parts.join(":")
}

common.seconds_to_hms =
function seconds_to_hms(seconds, args)
{
    args = args || {};
    const renderer = args["renderer"] || common.hms_render_colons;
    const force_minutes = args["force_minutes"] || false;
    const force_hours = args["force_hours"] || false;

    if (seconds > 0 && seconds < 1)
    {
        seconds = 1;
    }
    else
    {
        seconds = Math.round(seconds);
    }
    let minutes = Math.floor(seconds / 60);
    seconds = seconds % 60;
    let hours = Math.floor(minutes / 60);
    minutes = minutes % 60;

    if (hours == 0 && force_hours == false)
    {
        hours = null;
    }
    if (minutes == 0 && force_minutes == false)
    {
        minutes = null;
    }
    return renderer(hours, minutes, seconds);
}

////////////////////////////////////////////////////////////////////////////////////////////////////
// HTML & DOM //////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

common.delete_all_children =
function delete_all_children(element)
{
    while (element.firstChild)
    {
        element.removeChild(element.firstChild);
    }
}

common.html_to_element =
function html_to_element(html)
{
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    return template.content.firstElementChild;
}

common.size_iframe_to_content =
function size_iframe_to_content(iframe)
{
    iframe.style.height = iframe.contentWindow.document.documentElement.scrollHeight + 'px';
}

common.update_dynamic_elements =
function update_dynamic_elements(class_name, text)
{
    /*
    Find all elements with this class and set their innertext to this text.
    */
    const elements = document.getElementsByClassName(class_name);
    for (const element of elements)
    {
        element.innerText = text;
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////
// HOOKS & ADD-ONS /////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

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
    const bound_box_hook = function(event)
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

////////////////////////////////////////////////////////////////////////////////////////////////////
// CSS-JS CLASSES //////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_atag_merge_params =
function init_atag_merge_params(a)
{
    /*
    To create an <a> tag where the ?parameters written on the href are merged
    with the parameters of the current page URL, give it the class
    "merge_params". If the URL and href contain the same parameter, the href
    takes priority.

    Optional:
        data-merge-params: A whitelist of parameter names, separated by commas
            or spaces. Only these parameters will be merged from the page URL.

        data-merge-params-except: A blacklist of parameter names, separated by
            commas or spaces. All parameters except these will be merged from
            the page URL.

    Example:
        URL: ?filter=hello&orderby=score
        href: "?orderby=date"
        Result: "?filter=hello&orderby=date"
    */
    const page_params = Array.from(new URLSearchParams(window.location.search));
    let to_merge;

    if (a.dataset.mergeParams)
    {
        const keep = new Set(a.dataset.mergeParams.split(/[\s,]+/));
        to_merge = page_params.filter(key_value => keep.has(key_value[0]));
        delete a.dataset.mergeParams;
    }
    else if (a.dataset.mergeParamsExcept)
    {
        const remove = new Set(a.dataset.mergeParamsExcept.split(/[\s,]+/));
        to_merge = page_params.filter(key_value => (! remove.has(key_value[0])));
        delete a.dataset.mergeParamsExcept;
    }
    else
    {
        to_merge = page_params;
    }

    to_merge = to_merge.concat(Array.from(new URLSearchParams(a.search)));
    const new_params = new URLSearchParams();
    for (const [key, value] of to_merge)
        { new_params.set(key, value); }
    a.search = new_params.toString();
    a.classList.remove("merge_params");
}

common.init_all_atag_merge_params =
function init_all_atag_merge_params()
{
    const page_params = Array.from(new URLSearchParams(window.location.search));
    const as = Array.from(document.getElementsByClassName("merge_params"));
    for (const a of as)
    {
        setTimeout(() => common.init_atag_merge_params(a), 0);
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_button_with_confirm =
function init_button_with_confirm(button)
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
    button.classList.remove("button_with_confirm");

    const holder = document.createElement("span");
    holder.className = ("confirm_holder " + (button.dataset.holderClass || "")).trim();
    delete button.dataset.holderClass;
    if (button.dataset.holderId)
    {
        holder.id = button.dataset.holderId;
        delete button.dataset.holderId;
    }
    button.parentElement.insertBefore(holder, button);

    const holder_stage1 = document.createElement("span");
    holder_stage1.className = "confirm_holder_stage1";
    holder_stage1.appendChild(button);
    holder.appendChild(holder_stage1);

    const holder_stage2 = document.createElement("span");
    holder_stage2.className = "confirm_holder_stage2 hidden";
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
    if (button.dataset.promptClass)
    {
        prompt.className = button.dataset.promptClass;
    }
    holder_stage2.appendChild(prompt)
    delete button.dataset.prompt;
    delete button.dataset.promptClass;

    const button_confirm = document.createElement("button");
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

    const button_cancel = document.createElement("button");
    button_cancel.innerText = button.dataset.cancel || "Cancel";
    button_cancel.className = button.dataset.cancelClass || "";
    holder_stage2.appendChild(button_cancel);
    delete button.dataset.cancel;
    delete button.dataset.cancelClass;

    // If this is stupid, let me know.
    const confirm_onclick = `
        let holder = event.target.parentElement.parentElement;
        holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
        holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
    ` + button.dataset.onclick;
    button_confirm.onclick = Function(confirm_onclick);

    button.removeAttribute("onclick");
    button.onclick = function(event)
    {
        const holder = event.target.parentElement.parentElement;
        holder.getElementsByClassName("confirm_holder_stage1")[0].classList.add("hidden");
        holder.getElementsByClassName("confirm_holder_stage2")[0].classList.remove("hidden");
        const input = holder.getElementsByTagName("input")[0];
        if (input)
        {
            input.focus();
        }
    }

    button_cancel.onclick = function(event)
    {
        const holder = event.target.parentElement.parentElement;
        holder.getElementsByClassName("confirm_holder_stage1")[0].classList.remove("hidden");
        holder.getElementsByClassName("confirm_holder_stage2")[0].classList.add("hidden");
    }
    delete button.dataset.onclick;
}

common.init_all_button_with_confirm =
function init_all_button_with_confirm()
{
    const buttons = Array.from(document.getElementsByClassName("button_with_confirm"));
    for (const button of buttons)
    {
        setTimeout(() => common.init_button_with_confirm(button), 0);
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_all_input_bind_to_button =
function init_all_input_bind_to_button()
{
    for (const input of document.querySelectorAll("*[data-bind-enter-to-button]"))
    {
        const button = document.getElementById(input.dataset.bindEnterToButton);
        if (button)
        {
            common.bind_box_to_button(input, button, false);
            delete input.dataset.bindEnterToButton;
        }
    }
    for (const input of document.querySelectorAll("*[data-bind-ctrl-enter-to-button]"))
    {
        const button = document.getElementById(input.dataset.bindCtrlEnterToButton);
        if (button)
        {
            common.bind_box_to_button(input, button, true);
            delete input.dataset.bindCtrlEnterToButton;
        }
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_enable_on_pageload =
function init_enable_on_pageload(element)
{
    /*
    To create an input element which is disabled at first, and is enabled when
    the DOM has completed loading, give it the disabled attribute and the
    class "enable_on_pageload".

    For example:
    <input type="text" class="enable_on_pageload" disabled/>
    <button class="enable_on_pageload" disabled>Action</button>
    */
    element.disabled = false;
    element.classList.remove("enable_on_pageload");
}

common.init_all_enable_on_pageload =
function init_all_enable_on_pageload()
{
    const elements = Array.from(document.getElementsByClassName("enable_on_pageload"));
    for (const element of elements)
    {
        setTimeout(() => common.init_enable_on_pageload(element), 0);
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_entry_with_history =
function init_entry_with_history(input)
{
    input.addEventListener("keydown", common.entry_with_history_hook);
    input.classList.remove("entry_with_history");
}

common.init_all_entry_with_history =
function init_all_entry_with_history()
{
    const inputs = Array.from(document.getElementsByClassName("entry_with_history"));
    for (const input of inputs)
    {
        setTimeout(() => common.init_entry_with_history(input), 0);
    }
}

common.entry_with_history_hook =
function entry_with_history_hook(event)
{
    const box = event.target;

    if (box.entry_history === undefined)
        {box.entry_history = [];}

    if (box.entry_history_pos === undefined)
        {box.entry_history_pos = null;}

    if (event.key === "Enter")
    {
        if (box.value === "")
            {return;}
        box.entry_history.push(box.value);
        box.entry_history_pos = null;
    }
    else if (event.key === "Escape")
    {
        box.entry_history_pos = null;
        box.value = "";
    }

    if (box.entry_history.length == 0)
        {return}

    if (box.entry_history_pos !== null && box.value !== box.entry_history[box.entry_history_pos])
        {return;}

    if (event.key === "ArrowUp")
    {
        if (box.entry_history_pos === null)
            {box.entry_history_pos = box.entry_history.length - 1;}
        else if (box.entry_history_pos == 0)
            {;}
        else
            {box.entry_history_pos -= 1;}

        if (box.entry_history_pos === null)
            {box.value = "";}
        else
            {box.value = box.entry_history[box.entry_history_pos];}

        setTimeout(function(){box.selectionStart = box.value.length;}, 0);
    }
    else if (event.key === "ArrowDown")
    {
        if (box.entry_history_pos === null)
            {;}
        else if (box.entry_history_pos == box.entry_history.length-1)
            {box.entry_history_pos = null;}
        else
            {box.entry_history_pos += 1;}

        if (box.entry_history_pos === null)
            {box.value = "";}
        else
            {box.value = box.entry_history[box.entry_history_pos];}

        setTimeout(function(){box.selectionStart = box.value.length;}, 0);
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.init_tabbed_container =
function init_tabbed_container(tabbed_container)
{
    const button_container = document.createElement("div");
    button_container.className = "tab_buttons";
    tabbed_container.prepend(button_container);
    const tabs = Array.from(tabbed_container.getElementsByClassName("tab"));
    for (const tab of tabs)
    {
        tab.classList.add("hidden");
        const tab_id = tab.dataset.tabId || tab.dataset.tabTitle;
        tab.dataset.tabId = tab_id;
        tab.style.borderTopColor = "transparent";

        const button = document.createElement("button");
        button.className = "tab_button tab_button_inactive";
        button.onclick = common.tabbed_container_switcher;
        button.innerText = tab.dataset.tabTitle;
        button.dataset.tabId = tab_id;
        button_container.append(button);
    }
    tabs[0].classList.remove("hidden");
    tabbed_container.dataset.activeTabId = tabs[0].dataset.tabId;
    button_container.firstElementChild.classList.remove("tab_button_inactive");
    button_container.firstElementChild.classList.add("tab_button_active");
}

common.init_all_tabbed_container =
function init_all_tabbed_container()
{
    const tabbed_containers = Array.from(document.getElementsByClassName("tabbed_container"));
    for (const tabbed_container of tabbed_containers)
    {
        setTimeout(() => common.init_tabbed_container(tabbed_container), 0);
    }
}

common.tabbed_container_switcher =
function tabbed_container_switcher(event)
{
    const tab_button = event.target;
    if (tab_button.classList.contains("tab_button_active"))
        { return; }

    const tab_id = tab_button.dataset.tabId;
    const tab_buttons = tab_button.parentElement.getElementsByClassName("tab_button");
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
    const tabbed_container = tab_button.closest(".tabbed_container");
    tabbed_container.dataset.activeTabId = tab_id;
    const tabs = tabbed_container.getElementsByClassName("tab");
    for (const tab of tabs)
    {
        if (tab.dataset.tabId === tab_id)
            { tab.classList.remove("hidden"); }
        else
            { tab.classList.add("hidden"); }
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////

common.on_pageload =
function on_pageload()
{
    common.init_all_atag_merge_params();
    common.init_all_button_with_confirm();
    common.init_all_enable_on_pageload();
    common.init_all_entry_with_history();
    common.init_all_input_bind_to_button();
    common.init_all_tabbed_container();
}
document.addEventListener("DOMContentLoaded", common.on_pageload);
