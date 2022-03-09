const contextmenus = {};

contextmenus.hide_open_menus =
function hide_open_menus()
{
    const elements = document.getElementsByClassName("open_contextmenu");
    while (elements.length > 0)
    {
        elements[0].classList.remove("open_contextmenu");
    }
}

contextmenus.show_menu =
function show_menu(event, menu)
{
    contextmenus.hide_open_menus();
    menu.classList.add("open_contextmenu");
    const html = document.documentElement;
    const over_right = Math.max(0, event.clientX + menu.offsetWidth - html.clientWidth);
    const over_bottom = Math.max(0, event.clientY + menu.offsetHeight - html.clientHeight);
    const left = event.pageX - over_right;
    const top = event.pageY - over_bottom;
    menu.style.left = left + "px";
    menu.style.top = top + "px";
}

function on_pageload()
{
    document.body.addEventListener("click", contextmenus.hide_open_menus);
}
document.addEventListener("DOMContentLoaded", on_pageload);
