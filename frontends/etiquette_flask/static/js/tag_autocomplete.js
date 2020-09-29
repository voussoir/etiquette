const tag_autocomplete = {};

tag_autocomplete.tags = new Set();
tag_autocomplete.synonyms = {};

tag_autocomplete.DATALIST_ID = "tag_autocomplete_datalist";

// {
//     const db_name = "tag_autocomplete";
//     const db_version = 1;
//     const open_request = window.indexedDB.open(db_name, db_version);
//     open_request.onsuccess = function(event)
//     {
//         const db = event.target.result;
//         tag_autocomplete.db = db;
//         console.log("Initialized db.");
//     }
//     open_request.onupgradeneeded = function(event)
//     {
//         const db = event.target.result;
//         const tag_store = db.createObjectStore("tags", {"keyPath": "name"});
//         const synonym_store = db.createObjectStore("synonyms", {"keyPath": "name"});
//         const meta_store = db.createObjectStore("meta", {"keyPath": "key"});
//         tag_store.createIndex("name", "name", {unique: true});
//         synonym_store.createIndex("name", "name", {unique: true});
//         console.log("Installed db schema.");
//     }
// }

////////////////////////////////////////////////////////////////////////////////////////////////////

tag_autocomplete.init_datalist =
function init_datalist()
{
    console.log("Init datalist.");
    let datalist;
    datalist = document.getElementById(tag_autocomplete.DATALIST_ID);
    if (datalist)
    {
        return;
    }

    datalist = document.createElement("datalist");
    datalist.id = tag_autocomplete.DATALIST_ID;
    document.body.appendChild(datalist);

    const fragment = document.createDocumentFragment();
    common.delete_all_children(datalist);
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

// function update_stored_tags(data)
// {
//     console.log("Updating db tags.");
//     const updated = data.updated;
//     const version_transaction = tag_autocomplete.db.transaction(["meta"], "readwrite");
//     const meta_store = version_transaction.objectStore("meta");
//     meta_store.add({"key": "updated", "val": updated});
//     const tags_transaction = tag_autocomplete.db.transaction(["tags"], "readwrite");
//     const tags_store = tags_transaction.objectStore("tags");
//     for (const name of data.tags)
//     {
//         tags_store.add({"name": name});
//         tag_autocomplete.tags.add(name);
//     }
//     const synonyms_transaction = tag_autocomplete.db.transaction(["synonyms"], "readwrite");
//     const synonyms_store = synonyms_transaction.objectStore("synonyms");
//     for (const [name, mastertag] of Object.entries(data.synonyms))
//     {
//         synonyms_store.add({"name": name, "mastertag": mastertag});
//     }
//     tag_autocomplete.synonyms = data.synonyms;
//     count = data.tags.length + Object.keys(data.synonyms).length;
//     console.log(`Updated db tags with ${count} items.`);
//     if (document.getElementById(tag_autocomplete.DATALIST_ID))
//     {
//         setTimeout(() => tag_autocomplete.init_datalist(), 0);
//     }
// }

// function load_stored_tags()
// {
//     console.log("Loading stored db tags.");
//     const load_transaction = tag_autocomplete.db.transaction(["tags", "synonyms"]);
//     const tags_store = load_transaction.objectStore("tags");
//     const tags_request = tags_store.getAll();
//     tags_request.onsuccess = function(event)
//     {
//         for (row of event.target.result)
//         {
//             tag_autocomplete.tags.add(row["name"]);
//         }
//     }
//     // const synonyms_transaction = tag_autocomplete.db.transaction(["synonyms"]);
//     const synonyms_store = load_transaction.objectStore("synonyms");
//     const synonyms_request = synonyms_store.getAll();
//     synonyms_request.onsuccess = function(event)
//     {
//         for (row of event.target.result)
//         {
//             tag_autocomplete.synonyms[row["name"]] = row["mastertag"];
//         }
//         if (document.getElementById(tag_autocomplete.DATALIST_ID))
//         {
//             setTimeout(() => tag_autocomplete.init_datalist(), 0);
//         }
//     }
// }

tag_autocomplete.get_all_tags_callback =
function get_all_tags_callback(response)
{
    if (response["meta"]["status"] == 304)
    {
        return;
    }
    if (response["meta"]["status"] != 200)
    {
        console.error(response);
        return;
    }

    // const server_updated = response.data.updated;
    // const transaction = tag_autocomplete.db.transaction(["meta"]);
    // const meta_store = transaction.objectStore("meta");
    // const request = meta_store.get("updated");
    // request.onsuccess = function(event)
    // {
    //     if (event.target.result === undefined || event.target.result < server_updated)
    //     {
    //         update_stored_tags(response.data);
    //     }
    //     else
    //     {
    //         load_stored_tags();
    //     }
    // }
    tag_autocomplete.tags = new Set(response.data.tags);
    tag_autocomplete.synonyms = response.data.synonyms;
    setTimeout(() => tag_autocomplete.init_datalist(), 0);
    return tag_autocomplete.tagset;
}

tag_autocomplete.on_pageload =
function on_pageload()
{
    setTimeout(() => api.tags.get_all_tags(tag_autocomplete.get_all_tags_callback), 0);
    tag_autocomplete.init_entry_with_tagname_replacements();
}
document.addEventListener("DOMContentLoaded", tag_autocomplete.on_pageload);
