const editor = {};

editor.PARAGRAPH_TYPES = new Set(["P", "PRE"]);

editor.Editor =
function Editor(element_argss, on_open, on_save, on_cancel)
{
    /*
    This class wraps around display elements like spans, headers, and
    paragraphs, and creates edit elements like inputs and textareas to edit
    them with.

    element_argss should be a list of dicts. Each dict is required to have "id"
    which is unique amongst its peers, and "element" which is the display
    element. Additionally, you may add the following properties to change the
    element's behavior:

    "autofocus": true
        When the user opens the editor, this element will get .focus().
        Only one element should have this.

    "empty_text": string
        If the display element contains this text, then the edit element will
        be set to "" when opened.
        If the edit element contains "", then the display element will
        contain this text when saved.

    "hide_when_empty": true
        If the element does not have any text, it will get the "hidden" css
        class after saving / closing.

    "placeholder": string
        The placeholder attribute of the edit element.

    The editor object will contain a dict called elements that maps IDs to the
    display element, edit elements, and your other options.

    Your on_open, on_save and on_cancel hooks will be called with the editor
    object as the only argument.

    When your callbacks are used, the default `open`, `save`, `cancel`
    methods are not called automatically. You should call them from within
    your function. That's because you may wish to do some of your own
    normalization before the default handler, and some of your own cleanup
    after it. So it is up to you when to call the default.
    */
    this.cancel = function()
    {
        this.close();
    };

    this.close = function()
    {
        for (const element of Object.values(this.elements))
        {
            element.edit.classList.add("hidden");
            if (! (element.display.innerText === "" && element.hide_when_empty))
            {
                element.display.classList.remove("hidden");
            }
        }
        this.hide_spinner();
        this.hide_error();
        this.open_button.classList.remove("hidden");
        this.save_button.classList.add("hidden");
        this.cancel_button.classList.add("hidden");
    };

    this.hide_error = function()
    {
        this.error_message.classList.add("hidden");
    };

    this.hide_spinner = function()
    {
        this.spinner.hide();
    };

    this.open = function()
    {
        for (const element of Object.values(this.elements))
        {
            element.display.classList.add("hidden");
            element.edit.classList.remove("hidden");

            if (element.autofocus)
            {
                element.edit.focus();
            }

            if (element.empty_text !== undefined && element.display.innerText == element.empty_text)
            {
                element.edit.value = "";
            }
            else
            {
                element.edit.value = element.display.innerText;
            }
        }
        this.open_button.classList.add("hidden");
        this.save_button.classList.remove("hidden");
        this.cancel_button.classList.remove("hidden");
    };

    this.save = function()
    {
        for (const element of Object.values(this.elements))
        {
            if (element.empty_text !== undefined && element.edit.value == "")
            {
                element.display.innerText = element.empty_text;
            }
            else
            {
                element.display.innerText = element.edit.value;
            }
        }

        this.close();
    };

    this.show_error = function(message)
    {
        this.hide_spinner();
        this.error_message.innerText = message;
        this.error_message.classList.remove("hidden");
    };

    this.show_spinner = function(delay)
    {
        this.hide_error();
        this.spinner.show(delay);
    };

    this.elements = {};

    // End-user can put anything they want in here.
    this.misc_data = {};

    // Keep track of last edit element so we can put the toolbox after it.
    let last_element;

    for (const element_args of element_argss)
    {
        const element = {};
        element.id = element_args.id;
        this.elements[element.id] = element;

        element.display = element_args.element;
        element.empty_text = element_args.empty_text;
        element.hide_when_empty = element_args.hide_when_empty;
        element.autofocus = element_args.autofocus;

        if (editor.PARAGRAPH_TYPES.has(element.display.tagName))
        {
            element.edit = document.createElement("textarea");
            element.edit.rows = 6;
        }
        else
        {
            element.edit = document.createElement("input");
            element.edit.type = "text";
        }

        element.edit.classList.add("editor_input");
        element.edit.classList.add("hidden");

        if (element_args.placeholder !== undefined)
        {
            element.edit.placeholder = element_args.placeholder;
        }

        element.display.parentElement.insertBefore(element.edit, element.display.nextSibling);
        last_element = element.edit;
    }

    this.binder = function(func, fallback)
    {
        /*
        Given a function that takes an Editor as its first argument,
        return a new function which requires no arguments and calls the
        function with this editor.

        This is done so that the new function can be used in an event handler.
        */
        if (func == undefined)
        {
            return fallback.bind(this);
        }

        const bindable = () => func(this);
        return bindable.bind(this);
    }

    // In order to prevent page jumping on load, you can add an element with
    // class editor_toolbox_placeholder to the page and size it so it matches
    // the buttons that are going to get placed there.
    const placeholders = document.getElementsByClassName("editor_toolbox_placeholder");
    for (const placeholder of placeholders)
    {
        placeholder.parentElement.removeChild(placeholder);
    }

    const toolbox = document.createElement("div");
    toolbox.classList.add("editor_toolbox");
    last_element.parentElement.insertBefore(toolbox, last_element.nextSibling);

    this.open_button = document.createElement("button");
    this.open_button.innerText = "Edit";
    this.open_button.classList.add("editor_button");
    this.open_button.classList.add("editor_open_button");
    this.open_button.classList.add("green_button");
    this.open_button.onclick = this.binder(on_open, this.open);
    toolbox.appendChild(this.open_button);

    this.save_button = document.createElement("button");
    this.save_button.innerText = "Save";
    this.save_button.classList.add("editor_button");
    this.save_button.classList.add("editor_save_button");
    this.save_button.classList.add("green_button");
    this.save_button.classList.add("hidden");
    this.save_button.onclick = this.binder(on_save, this.save);
    toolbox.appendChild(this.save_button);
    toolbox.appendChild(document.createTextNode(" "));

    this.cancel_button = document.createElement("button");
    this.cancel_button.innerText = "Cancel";
    this.cancel_button.classList.add("editor_button");
    this.cancel_button.classList.add("editor_cancel_button");
    this.cancel_button.classList.add("gray_button");
    this.cancel_button.classList.add("hidden");
    this.cancel_button.onclick = this.binder(on_cancel, this.cancel);
    toolbox.appendChild(this.cancel_button);

    this.error_message = document.createElement("span");
    this.error_message.classList.add("editor_error");
    this.error_message.classList.add("hidden");
    toolbox.appendChild(this.error_message);

    spinner_element = document.createElement("span");
    spinner_element.innerText = "Submitting...";
    spinner_element.classList.add("editor_spinner");
    spinner_element.classList.add("hidden");
    this.spinner = new spinners.Spinner(spinner_element);
    toolbox.appendChild(spinner_element);

    for (const element of Object.values(this.elements))
    {
        const ctrl_enter = element.edit.tagName == "TEXTAREA";
        common.bind_box_to_button(element.edit, this.save_button, ctrl_enter);
    }
}
