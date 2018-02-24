var PARAGRAPH_TYPES = new Set(["P", "PRE"]);

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
                func(self, self.edit_element_map, self.display_element_map);
            }
            else
            {
                func(self, self.edit_elements, self.display_elements);
            }
        }
        return bound;
    }

    this.bound_open = binder(on_open, this.open);
    this.bound_save = binder(on_save, this.save);
    this.bound_cancel = binder(on_cancel, this.cancel);

    var last_element = this.edit_elements[this.edit_elements.length - 1];
    var toolbox = document.createElement("div");
    toolbox.classList.add("editor_toolbox");
    last_element.parentElement.insertBefore(toolbox, last_element.nextSibling);

    this.open_button = document.createElement("button");
    this.open_button.innerText = "Edit";
    this.open_button.classList.add("editor_button");
    this.open_button.classList.add("editor_open_button");
    this.open_button.classList.add("green_button");
    this.open_button.onclick = this.bound_open.bind(this);
    toolbox.appendChild(this.open_button);

    this.save_button = document.createElement("button");
    this.save_button.innerText = "Save";
    this.save_button.classList.add("editor_button");
    this.save_button.classList.add("editor_save_button");
    this.save_button.classList.add("green_button");
    this.save_button.classList.add("hidden");
    this.save_button.onclick = this.bound_save.bind(this);
    toolbox.appendChild(this.save_button);

    this.cancel_button = document.createElement("button");
    this.cancel_button.innerText = "Cancel";
    this.cancel_button.classList.add("editor_button");
    this.cancel_button.classList.add("editor_cancel_button");
    this.cancel_button.classList.add("red_button");
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
