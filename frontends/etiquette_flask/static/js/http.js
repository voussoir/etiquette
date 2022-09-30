const http = {};

http.HEADERS = {};

http.requests_in_flight = 0;

http.request_queue = {};
http.request_queue.array = [];

http.request_queue.push =
function request_queue_push(func)
{
    http.request_queue.array.push(func)
    if (http.requests_in_flight == 0)
    {
        http.request_queue_next();
    }
}

http.request_queue.unshift =
function request_queue_unshift(func)
{
    http.request_queue.array.unshift(func)
    if (http.requests_in_flight == 0)
    {
        http.request_queue_next();
    }
}
http.request_queue.pushleft = http.request_queue.unshift;

http.request_queue_next =
function request_queue_next()
{
    if (http.requests_in_flight > 0)
    {
        return;
    }
    if (http.request_queue.array.length === 0)
    {
        return;
    }
    const func = http.request_queue.array.shift();
    func();
}

http.formdata =
function formdata(data)
{
    const fd = new FormData();
    for (let [key, value] of Object.entries(data))
    {
        if (value === undefined)
        {
            continue;
        }
        if (value === null)
        {
            value = '';
        }
        fd.append(key, value);
    }
    return fd;
}

http._request =
function _request(kwargs)
{
    /*
    Perform an HTTP request and call the `callback` with the response.

    The response will have the following structure:
    {
        "meta": {
            "request": the XMLHttpRequest object,
            "completed": true / false,
            "status": If the connection failed or request otherwise could not
                complete, `status` will be 0. If the request completed,
                `status` will be the HTTP response code.
            "json_ok": If the server responded with parseable json, `json_ok`
                will be true, and that data will be in `response.data`. If the
                server response was not parseable json, `json_ok` will be false
                and `response.data` will be undefined.
            "kwargs": The kwargs exactly as given to this call.
        }
        "data": {JSON parsed from server response if json_ok},
        "retry": function you can call to retry the request.
    }

    So, from most lenient to most strict, error catching might look like:
    if response.meta.completed
    if response.meta.json_ok
    if response.meta.status === 200
    if response.meta.status === 200 and response.meta.json_ok
    */
    const request = new XMLHttpRequest();
    const response = {
        "meta": {
            "request": request,
            "completed": false,
            "status": 0,
            "json_ok": false,
            "kwargs": kwargs,
        },
        "retry": function(){http._request(kwargs)},
    };

    request.onreadystatechange = function()
    {
        /*
        readystate values:
        0 UNSENT / ABORTED
        1 OPENED
        2 HEADERS_RECEIVED
        3 LOADING
        4 DONE
        */
        if (request.readyState != 4)
        {
            return;
        }

        http.requests_in_flight -= 1;
        setTimeout(http.request_queue_next, 0);

        if (kwargs["callback"] == null)
        {
            return;
        }

        response.meta.status = request.status;

        if (request.status != 0)
        {
            response.meta.completed = true;
            try
            {
                response.data = JSON.parse(request.responseText);
                response.meta.json_ok = true;
            }
            catch (exc)
            {
                response.meta.json_ok = false;
            }
        }
        kwargs["callback"](response);
    };

    // Headers

    const asynchronous = "asynchronous" in kwargs ? kwargs["asynchronous"] : true;
    request.open(kwargs["method"], kwargs["url"], asynchronous);

    for (const [header, value] of Object.entries(http.HEADERS))
    {
        request.setRequestHeader(header, value);
    }

    const more_headers = kwargs["headers"] || {};
    for (const [header, value] of Object.entries(more_headers))
    {
        request.setRequestHeader(header, value);
    }

    if (kwargs["with_credentials"])
    {
        request.withCredentials = true;
    }

    // Send

    let data = kwargs["data"];
    if (data === undefined || data === null)
    {
        request.send();
    }
    else if (data instanceof FormData)
    {
        request.send(data);
    }
    else if (typeof(data) === "string" || data instanceof String)
    {
        request.send(data);
    }
    else
    {
        request.send(http.formdata(data));
    }
    http.requests_in_flight += 1;

    return request;
}

http.get =
function get(kwargs)
{
    kwargs["method"] = "GET";
    return http._request(kwargs);
}

http.post =
function post(kwargs)
{
    /*
    `data`:
        a FormData object which you have already filled with values, or a
        dictionary from which a FormData will be made, using http.formdata.
    */
    kwargs["method"] = "POST";
    return http._request(kwargs);
}
