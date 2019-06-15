var spinner = {};

spinner.Spinner =
function Spinner(element)
{
    this.show = function(delay)
    {
        clearTimeout(this.delayed_showing_timeout);
        this.delayed_showing_timeout = null;

        if (delay)
        {
            this.delayed_showing_timeout = setTimeout(function(thisthis){thisthis.show()}, delay, this);
        }
        else
        {
            this.element.classList.remove("hidden");
        }
    }

    this.hide = function()
    {
        clearTimeout(this.delayed_showing_timeout);
        this.delayed_showing_timeout = null;

        this.element.classList.add("hidden");
    }

    this.delayed_showing_timeout = null;
    this.element = element;
}
