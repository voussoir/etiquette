const spinners = {};

/*
In general, spinners are used for functions that launch a callback, and the
callback will close the spinner after it runs. But, if your initial function
decides not to launch the callback (insufficient parameters, failed clientside
checks, etc.), you can have it return spinners.BAIL and the spinners will close
immediately. Of course, you're always welcome to use
spinners.close_button_spinner(button), but this return value means you don't
need to pull the button into a variable, as long as you weren't using the
return value anyway.
*/
spinners.BAIL = "spinners.BAIL";

spinners.Spinner =
function Spinner(element)
{
    this.show = function(delay)
    {
        clearTimeout(this.delayed_showing_timeout);

        if (delay)
        {
            this.delayed_showing_timeout = setTimeout(function(thisthis){thisthis.show()}, delay, this);
        }
        else
        {
            this.delayed_showing_timeout = null;
            this.element.classList.remove("hidden");
        }
    }

    this.hide = function()
    {
        clearTimeout(this.delayed_showing_timeout);
        this.delayed_showing_timeout = null;

        this.element.classList.add("hidden");
    }

    this.delayed_showing_timeout = null;
    this.element = element;
}

spinners.spinner_button_index = 0;
spinners.button_spinner_groups = {};
/*
When a group member is closing, it will call the closer on all other members
in the group. Of course, this would recurse forever without some kind of
flagging, so this dict will hold group_id:true if a close is in progress,
and be empty otherwise.
*/
spinners.spinner_group_closing = {};

spinners.add_to_spinner_group =
function add_to_spinner_group(group_id, button)
{
    if (!(group_id in spinners.button_spinner_groups))
    {
        spinners.button_spinner_groups[group_id] = [];
    }
    spinners.button_spinner_groups[group_id].push(button);
}

spinners.close_button_spinner =
function close_button_spinner(button)
{
    window[button.dataset.spinnerCloser]();
}

spinners.close_grouped_spinners =
function close_grouped_spinners(group_id)
{
    if (group_id && !(spinners.spinner_group_closing[group_id]))
    {
        spinners.spinner_group_closing[group_id] = true;
        for (const button of spinners.button_spinner_groups[group_id])
        {
            window[button.dataset.spinnerCloser]();
        }
        delete spinners.spinner_group_closing[group_id];
    }
}

spinners.open_grouped_spinners =
function open_grouped_spinners(group_id)
{
    for (const button of spinners.button_spinner_groups[group_id])
    {
        window[button.dataset.spinnerOpener]();
    }
}

spinners.init_button_with_spinner =
function init_button_with_spinner()
{
    /*
    To create a button that has a spinner, and cannot be clicked again while
    the action is running, assign it the class "button_with_spinner".
    When you're ready for the spinner to disappear, call
    spinners.close_button_spinner(button).

    Optional:
        data-spinner-id: If you want to use your own element as the spinner,
            give its ID here. Otherwise a new one will be created.

        data-spinner-delay: The number of milliseconds to wait before the
            spinner appears. For tasks that you expect to run very quickly,
            this helps prevent a pointlessly short spinner. Note that the button
            always becomes disabled immediately, and this delay only affects
            the separate spinner element.

        data-holder-class: CSS class for the new span that holds the menu.

        data-spinner-group: An opaque string. All button_with_spinner that have
            the same group will go into spinner mode when any of them is
            clicked. Useful if you want to have two copies of a button on the
            page, or two buttons which do opposite things and you only want one
            to run at a time.
    */
    const buttons = Array.from(document.getElementsByClassName("button_with_spinner"));
    for (const button of buttons)
    {
        button.classList.remove("button_with_spinner");
        button.innerHTML = button.innerHTML.trim();

        const holder = document.createElement("span");
        holder.classList.add("spinner_holder");
        holder.classList.add(button.dataset.holderClass || "spinner_holder");
        button.parentElement.insertBefore(holder, button);
        holder.appendChild(button);

        if (button.dataset.spinnerGroup)
        {
            spinners.add_to_spinner_group(button.dataset.spinnerGroup, button);
        }

        let spinner_element;
        if (button.dataset.spinnerId)
        {
            spinner_element = document.getElementById(button.dataset.spinnerId);
            spinner_element.classList.add("hidden");
        }
        else
        {
            spinner_element = document.createElement("span");
            spinner_element.innerText = button.dataset.spinnerText || "Working...";
            spinner_element.classList.add("hidden");
            holder.appendChild(spinner_element);
        }

        const spin = new spinners.Spinner(spinner_element);
        const spin_delay = parseFloat(button.dataset.spinnerDelay) || 0;

        button.dataset.spinnerOpener = "spinner_opener_" + spinners.spinner_button_index;
        window[button.dataset.spinnerOpener] = function spinner_opener()
        {
            spin.show(spin_delay);
            button.disabled = true;
        }
        // It is expected that the function referenced by onclick will call
        // spinners.close_button_spinner(button) when appropriate, since from
        // our perspective we cannot be sure when to close the spinner.
        button.dataset.spinnerCloser = "spinner_closer_" + spinners.spinner_button_index;
        window[button.dataset.spinnerCloser] = function spinner_closer()
        {
            spinners.close_grouped_spinners(button.dataset.spinnerGroup);
            spin.hide();
            button.disabled = false;
        }

        const wrapped_onclick = button.onclick;
        button.removeAttribute('onclick');
        button.onclick = function(event)
        {
            if (button.dataset.spinnerGroup)
            {
                spinners.open_grouped_spinners(button.dataset.spinnerGroup);
            }
            else
            {
                window[button.dataset.spinnerOpener]();
            }
            const ret = wrapped_onclick(event);
            if (ret === spinners.BAIL)
            {
                window[button.dataset.spinnerCloser]();
            }
            return ret;
        }

        spinners.spinner_button_index += 1;
    }
}

spinners.on_pageload =
function on_pageload()
{
    spinners.init_button_with_spinner();
}
document.addEventListener("DOMContentLoaded", spinners.on_pageload);
