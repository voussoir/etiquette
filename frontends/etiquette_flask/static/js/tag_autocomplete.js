const tag_autocomplete = {};

tag_autocomplete.tagset = {"tags": [], "synonyms": {}};

tag_autocomplete.DATALIST_ID = "tag_autocomplete_datalist";

tag_autocomplete.init_datalist =
function init_datalist()
{
    let datalist;
    datalist = document.getElementById(tag_autocomplete.DATALIST_ID);
    if (!datalist)
    {
        datalist = document.createElement("datalist");
        datalist.id = tag_autocomplete.DATALIST_ID;
        document.body.appendChild(datalist);
    }

    common.delete_all_children(datalist);
    for (const tag_name of tag_autocomplete.tagset["tags"])
    {
        const option = document.createElement("option");
        option.value = tag_name;
        datalist.appendChild(option);
    }
    for (const synonym in tag_autocomplete.tagset["synonyms"])
    {
        const option = document.createElement("option");
        option.value = tag_autocomplete.tagset["synonyms"][synonym] + "+" + synonym;
        datalist.appendChild(option);
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
    if (tag_autocomplete.tagset["tags"].indexOf(tagname) != -1)
    {
        return tagname;
    }
    if (tagname in tag_autocomplete.tagset["synonyms"])
    {
        return tag_autocomplete.tagset["synonyms"][tagname];
    }
    return null;
}

tag_autocomplete.update_tagset_callback =
function update_tagset_callback(response)
{
    if (response["meta"]["status"] == 304)
    {
        return;
    }
    if (response["meta"]["status"] == 200)
    {
        tag_autocomplete.tagset = response["data"];
        if (document.getElementById(tag_autocomplete.DATALIST_ID))
        {
            tag_autocomplete.init_datalist();
        }
        console.log(`Updated tagset contains ${tag_autocomplete.tagset.tags.length}.`);
        return tag_autocomplete.tagset;
    }
    console.error(response);
}

tag_autocomplete.update_tagset =
function update_tagset()
{
    console.log("Updating known tagset.");
    const url = "/all_tags.json";
    common.get(url, tag_autocomplete.update_tagset_callback);
}

tag_autocomplete.on_pageload =
function on_pageload()
{
    tag_autocomplete.update_tagset();
    tag_autocomplete.init_entry_with_tagname_replacements();
}
document.addEventListener("DOMContentLoaded", tag_autocomplete.on_pageload);
