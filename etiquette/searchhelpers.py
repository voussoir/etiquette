import shlex

from . import constants
from . import exceptions
from . import helpers
from . import objects

def build_query(orderby, notnulls):
    query = 'SELECT * FROM photos'

    if orderby:
        orderby = [o.split('-') for o in orderby]
        orderby_columns = [column for (column, sorter) in orderby if column != 'RANDOM()']
    else:
        orderby_columns = []

    if notnulls:
        notnulls.extend(orderby_columns)
    elif orderby_columns:
        notnulls = orderby_columns

    if notnulls:
        notnulls = [x + ' IS NOT NULL' for x in notnulls]
        notnulls = ' AND '.join(notnulls)
        query += ' WHERE ' + notnulls
    if not orderby:
        query += ' ORDER BY created DESC'
        return query

    # Combine each column+sorter
    orderby = [' '.join(o) for o in orderby]

    # Combine everything
    orderby = ', '.join(orderby)
    query += ' ORDER BY %s' % orderby
    return query

def get_user(photodb, username_or_id):
    try:
        user = photodb.get_user(username=username_or_id)
    except exceptions.NoSuchUser:
        try:
            user = photodb.get_user(id=username_or_id)
        except exceptions.NoSuchUser:
            raise

    return user

def minmax(key, value, minimums, maximums, warning_bag=None):
    '''
    Dissects a hyphenated range string and inserts the correct k:v pair into
    both minimums and maximums.
    ('area', '100-200', {}, {})
    -->
    {'area': 100}, {'area': 200} (MODIFIED IN PLACE)
    '''
    if value is None:
        return

    if isinstance(value, str):
        value = value.strip()

    if value == '':
        return

    if isinstance(value, (int, float)):
        minimums[key] = value
        return

    try:
        (low, high) = helpers.hyphen_range(value)

    except ValueError as e:
        if warning_bag:
            warning_bag.add(constants.WARNING_MINMAX_INVALID.format(field=key, value=value))
            return
        else:
            raise

    except exceptions.OutOfOrder as e:
        if warning_bag:
            warning_bag.add(e.error_message)
            return
        else:
            raise

    if low is not None:
        minimums[key] = low

    if high is not None:
        maximums[key] = high

def normalize_authors(authors, photodb, warning_bag=None):
    '''
    Either:
    - A string, where the usernames are separated by commas
    - An iterable containing usernames
    - An iterable containing User objects.

    Returns: A set of user IDs.
    '''
    if not authors:
        return None

    if isinstance(authors, str):
        authors = helpers.comma_split(authors)

    user_ids = set()
    for requested_author in authors:
        if isinstance(requested_author, objects.User):
            if requested_author.photodb == photodb:
                user_ids.add(requested_author.id)
            else:
                requested_author = requested_author.username

        try:
            user = get_user(photodb, requested_author)
        except exceptions.NoSuchUser as e:
            if warning_bag:
                warning_bag.add(e.error_message)
            else:
                raise
        else:
            user_ids.add(user.id)

    if len(user_ids) == 0:
        return None

    return user_ids

def normalize_extensions(extensions):
    if not extensions:
        return None

    if isinstance(extensions, str):
        extensions = helpers.comma_split(extensions)

    if len(extensions) == 0:
        return None

    extensions = [e.lower().strip('.').strip() for e in extensions]
    extensions = set(extensions)
    extensions = {e for e in extensions if e}

    if len(extensions) == 0:
        return None

    return extensions

def normalize_filename(filename_terms):
    if not filename_terms:
        return None

    if not isinstance(filename_terms, str):
        filename_terms = ' '.join(filename_terms)

    filename_terms = filename_terms.strip()

    if not filename_terms:
        return None

    return filename_terms

def normalize_has_tags(has_tags):
    if not has_tags:
        return None

    if isinstance(has_tags, str):
        return helpers.truthystring(has_tags)

    if isinstance(has_tags, int):
        return bool(has_tags)

    return None

def normalize_limit(limit, warning_bag=None):
    if not limit and limit != 0:
        return None

    if isinstance(limit, str):
        limit = limit.strip()
        if limit.isdigit():
            limit = int(limit)

    if isinstance(limit, float):
        limit = int(limit)

    if not isinstance(limit, int):
        message = 'Invalid limit "%s%"' % limit
        if warning_bag:
            warning_bag.add(message)
            limit = None
        else:
            raise ValueError(message)

    return limit

def normalize_offset(offset, warning_bag=None):
    if not offset:
        return None

    if isinstance(offset, str):
        offset = offset.strip()
        if offset.isdigit():
            offset = int(offset)

    if isinstance(offset, float):
        offset = int(offset)

    if not isinstance(offset, int):
        message = 'Invalid offset "%s%"' % offset
        if warning_bag:
            warning_bag.add(message)
            offset = None
        else:
            raise ValueError(message)

    return offset

def normalize_orderby(orderby, warning_bag=None):
    if not orderby:
        return None

    if isinstance(orderby, str):
        orderby = orderby.replace('-', ' ')
        orderby = orderby.split(',')

    if not orderby:
        return None

    final_orderby = []
    for requested_order in orderby:
        requested_order = requested_order.lower().strip()
        if not requested_order:
            continue

        split_order = requested_order.split(' ')
        if len(split_order) == 2:
            (column, direction) = split_order

        elif len(split_order) == 1:
            column = split_order[0]
            direction = 'desc'

        else:
            message = constants.WARNING_ORDERBY_INVALID.format(requested=requested_order)
            if warning_bag:
                warning_bag.add(message)
            else:
                raise ValueError(message)
            continue

        if column not in constants.ALLOWED_ORDERBY_COLUMNS:
            message = constants.WARNING_ORDERBY_BADCOL.format(column=column)
            if warning_bag:
                warning_bag.add(message)
            else:
                raise ValueError(message)
            continue

        if column == 'random':
            column = 'RANDOM()'

        if direction not in ('asc', 'desc'):
            message = constants.WARNING_ORDERBY_BADDIRECTION.format(
                column=column,
                direction=direction,
            )
            if warning_bag:
                warning_bag.add(message)
            else:
                raise ValueError(message)            
            direction = 'desc'

        requested_order = '%s-%s' % (column, direction)
        final_orderby.append(requested_order)

    return final_orderby

def normalize_tag_expression(expression):
    if not expression:
        return None

    if not isinstance(expression, str):
        expression = ' '.join(expression)

    expression = expression.strip()

    if not expression:
        return None

    return expression

def normalize_tag_mmf(tags, photodb, warning_bag=None):
    if not tags:
        return None

    if isinstance(tags, str):
        tags = helpers.comma_split(tags)

    tagset = set()
    for tag in tags:
        if isinstance(tag, objects.Tag):
            if tag.photodb == photodb:
                tagset.add(tag)
                continue
            else:
                tag = tag.name

        tag = tag.strip()
        if tag == '':
            continue
        tag = tag.split('.')[-1]

        try:
            tag = photodb.get_tag(name=tag)
            exc = None
        except exceptions.NoSuchTag as e:
            exc = e
        except (exceptions.TagTooShort, exceptions.TagTooLong) as e:
            exc = exceptions.NoSuchTag(tag)
        if exc:
            if warning_bag:
                warning_bag.add(exc.error_message)
                continue
            else:
                raise exc
        tagset.add(tag)

    if len(tagset) == 0:
        return None

    return tagset

def tag_expression_matcher_builder(frozen_children, warning_bag=None):
    def matcher(photo_tags, tagname):
        '''
        Used as the `match_function` for the ExpressionTree evaluation.

        photo:
            The set of tag names owned by the photo in question.
        tagname:
            The tag which the ExpressionTree wants it to have.
        '''
        if not photo_tags:
            return False

        options = frozen_children[tagname]
        return any(option in photo_tags for option in options)

    return matcher
