const hotkeys = {};

hotkeys.HOTKEYS = {};

hotkeys.hotkey_identifier =
function hotkey_identifier(key, ctrlKey, shiftKey, altKey)
{
    // Return the string that will represent this hotkey in the dictionary.
    return key.toLowerCase() + "." + (ctrlKey & 1) + "." + (shiftKey & 1) + "." + (altKey & 1);
}

hotkeys.hotkey_human =
function hotkey_human(key, ctrlKey, shiftKey, altKey)
{
    // Return the string that will be displayed to the user to represent this hotkey.
    let mods = [];
    if (ctrlKey) { mods.push("Ctrl"); }
    if (shiftKey) { mods.push("Shift"); }
    if (altKey) { mods.push("Alt"); }
    mods = mods.join("+");
    if (mods) { mods = mods + "+"; }
    return mods + key.toUpperCase();
}

hotkeys.register_hotkey =
function register_hotkey(hotkey, action, description)
{
    if (! Array.isArray(hotkey))
    {
        hotkey = hotkey.split(/\s+/g);
    }

    const key = hotkey.pop();
    modifiers = hotkey.map(word => word.toLocaleLowerCase());
    const ctrlKey = modifiers.includes("control") || modifiers.includes("ctrl");
    const shiftKey = modifiers.includes("shift");
    const altKey = modifiers.includes("alt");

    const identifier = hotkeys.hotkey_identifier(key, ctrlKey, shiftKey, altKey);
    const human = hotkeys.hotkey_human(key, ctrlKey, shiftKey, altKey);
    hotkeys.HOTKEYS[identifier] = {"action": action, "human": human, "description": description}
}

hotkeys.should_prevent_hotkey =
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

hotkeys.show_all_hotkeys =
function show_all_hotkeys()
{
    // Display an Alert with a list of all the hotkeys.
    let lines = [];
    for (const identifier in hotkeys.HOTKEYS)
    {
        const line = hotkeys.HOTKEYS[identifier]["human"] + " :  " + hotkeys.HOTKEYS[identifier]["description"];
        lines.push(line);
    }
    lines = lines.join("\n");
    alert(lines);
}

hotkeys.hotkeys_listener =
function hotkeys_listener(event)
{
    if (hotkeys.should_prevent_hotkey(event)) { return; }
    identifier = hotkeys.hotkey_identifier(event.key, event.ctrlKey, event.shiftKey, event.altKey);
    //console.log(identifier);
    if (identifier in hotkeys.HOTKEYS)
    {
        hotkeys.HOTKEYS[identifier]["action"]();
        event.preventDefault();
    }
}

window.addEventListener("keydown", hotkeys.hotkeys_listener);

hotkeys.register_hotkey("/", hotkeys.show_all_hotkeys, "Show hotkeys.");
