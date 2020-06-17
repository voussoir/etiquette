var tag_autocomplete = {};

tag_autocomplete.tagset = {"tags": [], "synonyms": {}};

tag_autocomplete.DATALIST_ID = "tag_autocomplete_datalist";

tag_autocomplete.init_datalist =
function init_datalist()
{
    var datalist;
    datalist = document.getElementById(tag_autocomplete.DATALIST_ID);
    if (!datalist)
    {
        var datalist = document.createElement("datalist");
        datalist.id = tag_autocomplete.DATALIST_ID;
        document.body.appendChild(datalist);
    }

    common.delete_all_children(datalist);
    for (var index = 0; index < tag_autocomplete.tagset["tags"].length; index += 1)
    {
        var option = document.createElement("option");
        option.value = tag_autocomplete.tagset["tags"][index];
        datalist.appendChild(option);
    }
    for (var synonym in tag_autocomplete.tagset["synonyms"])
    {
        var option = document.createElement("option");
        option.value = tag_autocomplete.tagset["synonyms"][synonym] + "+" + synonym;
        datalist.appendChild(option);
    }
}

tag_automplete.normalize_tagname =
function normalize_tagname(tagname)
{
    tagname = tagname.trim();
    tagname = tagname.toLocaleLowerCase();
    tagname = tagname.split(".");
    tagname = tagname[tagname.length-1];
    tagname = tagname.split("+")[0];
    tagname = tag_automplete.tagname_replacements(tagname);
    return tagname;
}

tag_automplete.tagname_replacements =
function tagname_replacements(tagname)
{
    tagname = tagname.replace(new RegExp(" ", 'g'), "_");
    tagname = tagname.replace(new RegExp("-", 'g'), "_");
    return tagname;
}

tag_automplete.entry_with_tagname_replacements_hook =
function entry_with_tagname_replacements_hook(event)
{
    var cursor_position = event.target.selectionStart;
    var new_value = tag_automplete.tagname_replacements(event.target.value);
    if (new_value != event.target.value)
    {
        event.target.value = new_value;
        event.target.selectionStart = cursor_position;
        event.target.selectionEnd = cursor_position;
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
    var url = "/all_tags.json";
    common.get(url, tag_autocomplete.update_tagset_callback);
}

function on_pageload()
{
    tag_autocomplete.update_tagset();
}
document.addEventListener("DOMContentLoaded", on_pageload);
