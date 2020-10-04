const tag_autocomplete = {};

tag_autocomplete.tags = new Set();
tag_autocomplete.synonyms = {};

tag_autocomplete.DATALIST_ID = "tag_autocomplete_datalist";
tag_autocomplete.datalist = null;
tag_autocomplete.on_load_hooks = [];

////////////////////////////////////////////////////////////////////////////////////////////////////

tag_autocomplete.init_datalist =
function init_datalist()
{
    if (tag_autocomplete.datalist)
    {
        return;
    }
    console.log("Init tag_autocomplete datalist.");
    const datalist = document.createElement("datalist");
    datalist.id = tag_autocomplete.DATALIST_ID;
    document.body.appendChild(datalist);

    const fragment = document.createDocumentFragment();
    for (const tag_name of tag_autocomplete.tags)
    {
        const option = document.createElement("option");
        option.value = tag_name;
        fragment.appendChild(option);
    }
    for (const synonym in tag_autocomplete.synonyms)
    {
        const option = document.createElement("option");
        option.value = tag_autocomplete.synonyms[synonym] + "+" + synonym;
        fragment.appendChild(option);
    }
    datalist.appendChild(fragment);
    tag_autocomplete.datalist = datalist;

    for (const hook of tag_autocomplete.on_load_hooks)
    {
        hook(datalist);
    }
}

tag_autocomplete.normalize_tagname =
function normalize_tagname(tagname)
{
    tagname = tagname.trim();
    tagname = tagname.toLocaleLowerCase();
    tagname = tagname.split(".");
    tagname = tagname[tagname.length-1];
    tagname = tagname.split("+")[0];
    tagname = tag_autocomplete.tagname_replacements(tagname);
    return tagname;
}

tag_autocomplete.tagname_replacements =
function tagname_replacements(tagname)
{
    tagname = tagname.replace(new RegExp(" ", 'g'), "_");
    tagname = tagname.replace(new RegExp("-", 'g'), "_");
    return tagname;
}

tag_autocomplete.entry_with_tagname_replacements_hook =
function entry_with_tagname_replacements_hook(event)
{
    const cursor_position = event.target.selectionStart;
    const new_value = tag_autocomplete.tagname_replacements(event.target.value);
    if (new_value != event.target.value)
    {
        event.target.value = new_value;
        event.target.selectionStart = cursor_position;
        event.target.selectionEnd = cursor_position;
    }
}

tag_autocomplete.init_entry_with_tagname_replacements =
function init_entry_with_tagname_replacements()
{
    const inputs = Array.from(document.getElementsByClassName("entry_with_tagname_replacements"));
    for (const input of inputs)
    {
        input.addEventListener("keyup", tag_autocomplete.entry_with_tagname_replacements_hook);
        input.classList.remove("entry_with_tagname_replacements");
    }
}

tag_autocomplete.resolve =
function resolve(tagname)
{
    tagname = tag_autocomplete.normalize_tagname(tagname);
    if (tag_autocomplete.tags.has(tagname))
    {
        return tagname;
    }
    if (tagname in tag_autocomplete.synonyms)
    {
        return tag_autocomplete.synonyms[tagname];
    }
    return null;
}

tag_autocomplete.get_all_tags_callback =
function get_all_tags_callback(response)
{
    if (response.meta.status !== 200)
    {
        console.error(response);
        return;
    }

    tag_autocomplete.tags = new Set(response.data.tags);
    tag_autocomplete.synonyms = response.data.synonyms;
    setTimeout(tag_autocomplete.init_datalist, 0);
}

tag_autocomplete.on_pageload =
function on_pageload()
{
    setTimeout(() => api.tags.get_all_tags(tag_autocomplete.get_all_tags_callback), 0);
    tag_autocomplete.init_entry_with_tagname_replacements();
}
document.addEventListener("DOMContentLoaded", tag_autocomplete.on_pageload);
