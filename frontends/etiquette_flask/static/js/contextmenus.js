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
function show_menu(event, element)
{
    contextmenus.hide_open_menus();
    console.log(event);
    element.classList.add("open_contextmenu");
    const html = document.documentElement;
    const over_right = Math.max(0, event.clientX + element.offsetWidth - html.clientWidth);
    const over_bottom = Math.max(0, event.clientY + element.offsetHeight - html.clientHeight);
    const left = event.target.offsetLeft + event.offsetX - over_right;
    const top = event.target.offsetTop + event.offsetY - over_bottom;
    element.style.left = left + "px";
    element.style.top = top + "px";
}

function on_pageload()
{
    document.body.addEventListener("click", contextmenus.hide_open_menus);
}
document.addEventListener("DOMContentLoaded", on_pageload);
