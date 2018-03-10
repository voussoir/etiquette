var PARAGRAPH_TYPES = new Set(["P", "PRE"]);

function Editor(elements, on_open, on_save, on_cancel)
{
    /*
    This class wraps around display elements like headers and paragraphs, and
    creates edit elements like inputs and textareas to edit them with.

    You may add the following data- attributes to your display elements to
    affect their corresponding edit elements:
    data-editor-empty-text: If the display element contains this text, then
        the edit element will be set to "" when opened.
        If the edit element contains "", then the display element will
        contain this text when saved.
    data-editor-id: The string used as the key into display_element_map and
        edit_element_map.
    data-editor-placeholder: The placeholder attribute of the edit element.

    Your on_open, on_save and on_cancel hooks will be called with:
        1. This editor object.
        2. The edit elements as either:
            If ALL of the display elements have a data-editor-id,
            then a dictionary of {data-editor-id: edit_element, ...}.
            Otherwise, an array of [edit_element, ...] in the order they were
            given to the constructor.
        3. The display elements as either the map or the array, similarly.

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
    this.display_element_map = {};
    this.edit_element_map = {};

    this.misc_data = {};

    for (var index = 0; index < elements.length; index += 1)
    {
        var display_element = elements[index];
        var edit_element;
        if (PARAGRAPH_TYPES.has(display_element.tagName))
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
                this.display_element_map[display_element.dataset.editorId] = display_element;
                this.edit_element_map[display_element.dataset.editorId] = edit_element;
            }
            else
            {
                this.can_use_element_map = false;
                this.edit_element_map = null;
                this.display_element_map = null;
            }
        }

        display_element.parentElement.insertBefore(edit_element, display_element.nextSibling);

        this.display_elements.push(display_element);
        this.edit_elements.push(edit_element);
    }

    this.binder = function(func, fallback)
    {
        /*
        Given a function that takes an Editor as its first argument, and the
        element arrays/maps as the second and third, return a new function
        which requires no arguments and calls the given function with the
        correct data.

        This is done so that the new function can be used in an event handler.
        */
        if (func == undefined)
        {
            return fallback;
        }

        var bindable = function()
        {
            if (this.can_use_element_map)
            {
                func(this, this.edit_element_map, this.display_element_map);
            }
            else
            {
                func(this, this.edit_elements, this.display_elements);
            }
        }
        return bindable.bind(this);
    }

    var last_element = this.edit_elements[this.edit_elements.length - 1];
    var toolbox = document.createElement("div");
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

    this.cancel_button = document.createElement("button");
    this.cancel_button.innerText = "Cancel";
    this.cancel_button.classList.add("editor_button");
    this.cancel_button.classList.add("editor_cancel_button");
    this.cancel_button.classList.add("red_button");
    this.cancel_button.classList.add("hidden");
    this.cancel_button.onclick = this.binder(on_cancel, this.cancel);
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
