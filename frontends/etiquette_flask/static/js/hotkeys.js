HOTKEYS = {};

function hotkey_identifier(key, ctrlKey, shiftKey, altKey)
{
    // Return the string that will represent this hotkey in the dictionary.
    return key.toLowerCase() + "." + (ctrlKey & 1) + "." + (shiftKey & 1) + "." + (altKey & 1);
}

function hotkey_human(key, ctrlKey, shiftKey, altKey)
{
    // Return the string that will be displayed to the user to represent this hotkey.
    mods = [];
    if (ctrlKey) { mods.push("Ctrl"); }
    if (shiftKey) { mods.push("Shift"); }
    if (altKey) { mods.push("Alt"); }
    mods = mods.join("+");
    if (mods) { mods = mods + "+"; }
    return mods + key.toUpperCase();
}

function register_hotkey(key, ctrlKey, shiftKey, altKey, action, description)
{
    identifier = hotkey_identifier(key, ctrlKey, shiftKey, altKey);
    human = hotkey_human(key, ctrlKey, shiftKey, altKey);
    HOTKEYS[identifier] = {"action": action, "human": human, "description": description}
}

function should_prevent_hotkey(event)
{
    if (event.target.tagName == "INPUT" && event.target.type == "checkbox")
    {
        return false;
    }
    else
    {
        return common.INPUT_TYPES.has(event.target.tagName);
    }
}

function show_all_keybinds()
{
    // Display an Alert with a list of all the keybinds.
    var lines = [];
    for (var identifier in HOTKEYS)
    {
        var line = HOTKEYS[identifier]["human"] + " :  " + HOTKEYS[identifier]["description"];
        lines.push(line);
    }
    lines = lines.join("\n");
    alert(lines);
}


window.addEventListener(
    "keydown",
    function(event)
    {
        if (should_prevent_hotkey(event)) { return; }
        identifier = hotkey_identifier(event.key, event.ctrlKey, event.shiftKey, event.altKey);
        console.log(identifier);
        if (identifier in HOTKEYS)
        {
            HOTKEYS[identifier]["action"]();
            event.preventDefault();
        }
    }
);

register_hotkey("/", 0, 0, 0, show_all_keybinds, "Show keybinds.");
