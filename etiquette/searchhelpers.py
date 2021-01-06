'''
This file provides helper functions used to normalize the arguments that
go into search queries. Mainly converting the strings given by the user
into proper data types.
'''
from . import constants
from . import exceptions
from . import helpers
from . import objects

from voussoirkit import expressionmatch
from voussoirkit import pathclass
from voussoirkit import sqlhelpers
from voussoirkit import stringtools

def expand_mmf(tag_musts, tag_mays, tag_forbids):
    '''
    In order to generate SQL queries for `tagid IN (options)`, we need to
    expand the descendents of the given must/may/forbid tags to generate the
    complete list of options able to satisfy each query.
    - musts becomes a list of sets and the photo must have at least one tag
      from each set.
    - mays becomes a set and the photo must have at least one.
    - forbids becomes a set and the photo must not have any.
    '''
    def _set(x):
        if x is None:
            return set()
        return set(x)

    tag_musts = _set(tag_musts)
    tag_mays = _set(tag_mays)
    tag_forbids = _set(tag_forbids)

    forbids_expanded = set()

    def _remove_redundant_musts(tagset):
        '''
        Suppose B is a child of A, and the user searches for tag_musts=[A, B]
        for some reason. In this case, A is redundant since having B already
        satisfies A, so it makes sense to only expand and generate SQL for B.
        This function will remove any tags which are ancestors of other tags
        in the set so that we generate the minimum amount of SQL queries.
        '''
        ancestors = set()
        for tag in tagset:
            if tag in ancestors:
                continue
            ancestors.update(tag.walk_parents())
        pruned = tagset.difference(ancestors)
        return pruned

    def _expand_flat(tagset):
        # I am not using tag.walk_children because if the user happens to give
        # us two tags in the same lineage, we have the opportunity to bail
        # early, which walk_children won't know about. So instead I'm doing the
        # queue popping and pushing myself.
        expanded = set()
        while len(tagset) > 0:
            tag = tagset.pop()
            if tag in forbids_expanded:
                continue
            if tag in expanded:
                continue
            expanded.add(tag)
            tagset.update(tag.get_children())
        return expanded

    # forbids must come first so that musts and mays don't waste their time
    # expanding the forbidden subtrees.
    forbids_expanded = _expand_flat(tag_forbids)
    musts_expanded = [_expand_flat({tag}) for tag in _remove_redundant_musts(tag_musts)]
    mays_expanded = _expand_flat(tag_mays)

    return (musts_expanded, mays_expanded, forbids_expanded)

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

    except ValueError as exc:
        if warning_bag:
            warning_bag.add(constants.WARNING_MINMAX_INVALID.format(field=key, value=value))
            return
        else:
            raise

    except exceptions.OutOfOrder as exc:
        if warning_bag:
            warning_bag.add(exc)
            return
        else:
            raise

    if low is not None:
        minimums[key] = low

    if high is not None:
        maximums[key] = high

def normalize_author(authors, photodb, warning_bag=None):
    '''
    Either:
    - A string, where the usernames are separated by commas
    - An iterable containing
        - Usernames as strings
        - User objects

    Returns: A set of user IDs.
    '''
    if authors is None:
        authors = []

    if isinstance(authors, str):
        authors = stringtools.comma_space_split(authors)

    users = set()
    for requested_author in authors:
        if isinstance(requested_author, objects.User):
            if requested_author.photodb == photodb:
                users.add(requested_author)
            else:
                requested_author = requested_author.username

        try:
            user = photodb.get_user(username=requested_author)
        except exceptions.NoSuchUser as exc:
            if warning_bag:
                warning_bag.add(exc)
            else:
                raise
        else:
            users.add(user)

    return users

def normalize_extension(extensions):
    '''
    Either:
    - A string, where extensions are separated by commas or spaces.
    - An iterable containing extensions as strings.

    Returns: A set of strings with no leading dots.
    '''
    if extensions is None:
        extensions = set()

    elif isinstance(extensions, str):
        extensions = stringtools.comma_space_split(extensions)

    extensions = [e.lower().strip('.').strip() for e in extensions]
    extensions = set(e for e in extensions if e)

    return extensions

def normalize_filename(filename_terms):
    '''
    Either:
    - A string.
    - An iterable containing search terms as strings.

    Returns: A string where terms are separated by spaces.
    '''
    if filename_terms is None:
        filename_terms = ''

    if not isinstance(filename_terms, str):
        filename_terms = ' '.join(filename_terms)

    filename_terms = filename_terms.strip()

    return filename_terms

def normalize_has_tags(has_tags):
    '''
    See etiquette.helpers.truthystring.
    '''
    return helpers.truthystring(has_tags)

def normalize_has_thumbnail(has_thumbnail):
    '''
    See etiquette.helpers.truthystring.
    '''
    return helpers.truthystring(has_thumbnail)

def normalize_is_searchhidden(is_searchhidden):
    '''
    See etiquette.helpers.truthystring.
    '''
    return helpers.truthystring(is_searchhidden)

def _limit_offset(number, warning_bag):
    if number is None:
        return None

    try:
        number = normalize_positive_integer(number)
    except ValueError as exc:
        if warning_bag:
            warning_bag.add(exc)
        number = 0
    return number

def normalize_limit(limit, warning_bag=None):
    '''
    Either:
    - None to indicate unlimited.
    - A non-negative number as an int, float, or string.

    Returns: None or a positive integer.
    '''
    return _limit_offset(limit, warning_bag)

def normalize_mimetype(mimetype, warning_bag=None):
    '''
    Either:
    - A string, where mimetypes are separated by commas or spaces.
    - An iterable containing mimetypes as strings.

    Returns: A set of strings.
    '''
    return normalize_extension(mimetype, warning_bag)

def normalize_mmf_vs_expression_conflict(
        tag_musts,
        tag_mays,
        tag_forbids,
        tag_expression,
        warning_bag=None,
    ):
    '''
    The user cannot provide both mmf sets and tag expression at the same time.
    If both are provided, nullify everything.
    '''
    if (tag_musts or tag_mays or tag_forbids) and tag_expression:
        exc = exceptions.NotExclusive(['tag_musts+mays+forbids', 'tag_expression'])
        if warning_bag:
            warning_bag.add(exc)
        else:
            raise exc
        conflict = True
    conflict = False

    if conflict:
        tag_musts = None
        tag_mays = None
        tag_forbids = None
        tag_expression = None
    return (tag_musts, tag_mays, tag_forbids, tag_expression)

def normalize_offset(offset, warning_bag=None):
    '''
    Either:
    - None.
    - A non-negative number as an int, float, or string.

    Returns: None or a positive integer.
    '''
    if offset is None:
        return 0
    return _limit_offset(offset, warning_bag)

def normalize_orderby(orderby, warning_bag=None):
    '''
    Either:
    - A string of orderbys separated by commas, where a single orderby consists
    of 'column' or 'column-direction' or 'column direction'.
    - A list of such orderby strings.
    - A list of tuples of (column, direction)

    With no direction, direction is implied desc.

    Returns: A list of tuples of (column_friendly, column_expanded, direction)
    where friendly is the name as the user would see it and expanded is the
    expression to be used in the SQL query. This is important for columns like
    "area" which is expanded into width*height.
    '''
    if orderby is None:
        orderby = []

    if isinstance(orderby, str):
        orderby = orderby.replace('-', ' ')
        orderby = orderby.split(',')

    final_orderby = []
    for requested_order in orderby:
        if isinstance(requested_order, str):
            requested_order = requested_order.strip().lower()
            if not requested_order:
                continue
            split_order = requested_order.split()
        else:
            split_order = tuple(x.strip().lower() for x in requested_order)

        if len(split_order) == 2:
            (column, direction) = split_order

        elif len(split_order) == 1:
            column = split_order[0]
            direction = 'desc'

        else:
            exc = ValueError(constants.WARNING_ORDERBY_INVALID.format(request=requested_order))
            if warning_bag:
                warning_bag.add(exc)
                continue
            else:
                raise exc

        if direction not in ('asc', 'desc'):
            message = constants.WARNING_ORDERBY_BADDIRECTION.format(
                column=column,
                direction=direction,
            )
            exc = ValueError(message)
            if warning_bag:
                warning_bag.add(exc)
                direction = 'desc'
            else:
                raise exc

        if column not in constants.ALLOWED_ORDERBY_COLUMNS:
            exc = ValueError(constants.WARNING_ORDERBY_BADCOL.format(column=column))
            if warning_bag:
                warning_bag.add(exc)
                continue
            else:
                raise exc

        column_friendly = column
        column_expanded = {
            'random': 'RANDOM()',
            'area': '(width * height)',
            'basename': 'COALESCE(override_filename, basename)',
            'bitrate': '((bytes / 128) / duration)',
            'ratio': '(width / height)',
        }.get(column, column)

        final_orderby.append( (column_friendly, column_expanded, direction) )

    return final_orderby

def normalize_positive_integer(number):
    if number is None:
        number = 0

    elif isinstance(number, str):
        # Convert to float, then int, just in case they type '-4.5'
        # because int('-4.5') does not work.
        number = float(number)

    number = int(number)

    if number < 0:
        raise ValueError(f'{number} must be >= 0.')

    return number

def normalize_tag_expression(expression):
    if not expression:
        return None

    if not isinstance(expression, str):
        expression = ' '.join(expression)

    expression = expression.strip()

    if not expression:
        return None

    return expression

def normalize_within_directory(paths, warning_bag=None):
    if paths is None:
        return set()

    if isinstance(paths, set):
        pass
    elif isinstance(paths, (str, pathclass.Path)):
        paths = {paths}
    elif isinstance(paths, (list, tuple)):
        paths = set(paths)
    else:
        exc = TypeError(paths)
        if warning_bag:
            warning_bag.add(exc)
            return set()
        else:
            raise exc

    paths = {pathclass.Path(p) for p in paths}
    directories = {p for p in paths if p.is_dir}
    not_directories = paths.difference(directories)
    if not_directories:
        exc = pathclass.NotDirectory(not_directories)
        if warning_bag:
            warning_bag.add(exc)
        else:
            raise exc

    return directories

def normalize_yield_albums(yield_albums):
    '''
    See etiquette.helpers.truthystring.
    '''
    return helpers.truthystring(yield_albums)

def normalize_yield_photos(yield_photos):
    '''
    See etiquette.helpers.truthystring.
    '''
    return helpers.truthystring(yield_photos)

EXIST_FORMAT = '''
{operator} (
    SELECT 1 FROM photo_tag_rel WHERE photos.id == photo_tag_rel.photoid
    AND tagid IN {tagset}
)
'''.strip()
def photo_tag_rel_exist_clauses(tag_musts, tag_mays, tag_forbids):
    (tag_musts, tag_mays, tag_forbids) = expand_mmf(
        tag_musts,
        tag_mays,
        tag_forbids,
    )

    clauses = []
    # Notice musts is a loop and the others are ifs.
    for tag_must_group in tag_musts:
        clauses.append( ('EXISTS', tag_must_group) )
    if tag_mays:
        clauses.append( ('EXISTS', tag_mays) )
    if tag_forbids:
        clauses.append( ('NOT EXISTS', tag_forbids) )

    clauses = [
        (operator, sqlhelpers.listify(tag.id for tag in tagset))
        for (operator, tagset) in clauses
    ]
    clauses = [
        EXIST_FORMAT.format(operator=operator, tagset=tagset)
        for (operator, tagset) in clauses
    ]
    return clauses

def normalize_tagset(photodb, tags, warning_bag=None):
    if not tags:
        return None

    if isinstance(tags, str):
        tags = stringtools.comma_space_split(tags)

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
        except exceptions.NoSuchTag as exc:
            if warning_bag:
                warning_bag.add(exc)
                continue
            else:
                raise exc
        tagset.add(tag)
    return tagset

def tag_expression_tree_builder(
        tag_expression,
        photodb,
        warning_bag=None
    ):
    if not tag_expression:
        return None
    try:
        expression_tree = expressionmatch.ExpressionTree.parse(tag_expression)
    except expressionmatch.NoTokens:
        return None
    except Exception as exc:
        warning_bag.add(f'Bad expression "{tag_expression}"')
        return None

    for node in expression_tree.walk_leaves():
        try:
            node.token = photodb.get_tag(name=node.token).name
        except (exceptions.NoSuchTag) as exc:
            if warning_bag:
                warning_bag.add(exc)
                node.token = None
            else:
                raise

        if node.token is None:
            continue

    expression_tree.prune()
    if expression_tree.token is None:
        return None
    return expression_tree

def tag_expression_matcher_builder(frozen_children):
    frozen_children = {
        (tag.name if not isinstance(tag, str) else tag): children
        for (tag, children) in frozen_children.items()
    }

    def match_function(photo_tags, tagname):
        '''
        Used as the `match_function` for the ExpressionTree evaluation.

        photo_tags:
            The set of tag names owned by the photo in question.
        tagname:
            The tag which the ExpressionTree wants it to have.
        '''
        if not photo_tags:
            return False

        options = frozen_children[tagname]
        return any(option in photo_tags for option in options)

    return match_function
