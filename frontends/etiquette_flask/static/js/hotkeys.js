const hotkeys = {};

hotkeys.HOTKEYS = {};
hotkeys.HELPS = [];

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
    if (ctrlKey) { mods.push("CTRL"); }
    if (shiftKey) { mods.push("SHIFT"); }
    if (altKey) { mods.push("ALT"); }
    mods = mods.join("+");
    if (mods) { mods = mods + "+"; }
    return mods + key.toUpperCase();
}

hotkeys.register_help =
function register_help(help)
{
    hotkeys.HELPS.push(help);
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
    /*
    If the user is currently in an input element, then the registered hotkey
    will be ignored and the browser will use its default behavior.
    */
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
    if (hotkeys.HELPS)
    {
        lines.push("");
    }
    for (const help of hotkeys.HELPS)
    {
        lines.push(help);
    }
    lines = lines.join("\n");
    alert(lines);
}

hotkeys.hotkeys_listener =
function hotkeys_listener(event)
{
    // console.log(event.key);
    if (hotkeys.should_prevent_hotkey(event))
    {
        return;
    }

    identifier = hotkeys.hotkey_identifier(event.key, event.ctrlKey, event.shiftKey, event.altKey);
    //console.log(identifier);
    if (identifier in hotkeys.HOTKEYS)
    {
        hotkeys.HOTKEYS[identifier]["action"](event);
        event.preventDefault();
    }
}

window.addEventListener("keydown", hotkeys.hotkeys_listener);

hotkeys.register_hotkey("/", hotkeys.show_all_hotkeys, "Show hotkeys.");
