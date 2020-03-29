def dict_to_params(d):
    '''
    Given a dictionary of URL parameters, return a URL parameter string.

    {'a':1, 'b':2} -> '?a=1&b=2'
    '''
    if not d:
        return ''

    params = [f'{key}={value}' for (key, value) in d.items()]
    params = '&'.join(params)
    params = '?' + params

    return params
