'''
This file provides a variety of functions for exporting a PDB's tags into other
formats. Strings, dicts, etc.
'''

def easybake(tags, include_synonyms=True, with_objects=False):
    '''
    A string where every line is the qualified name of a tag or its synonyms.

    people
    people.family
    people.family.mother
    people.family.mother+mom
    '''
    tags = sorted(tags)
    for tag in tags:
        if with_objects:
            my_line = (tag.name, tag)
        else:
            my_line = tag.name

        yield my_line

        if include_synonyms:
            syn_lines = [f'{tag.name}+{syn}' for syn in sorted(tag.get_synonyms())]
            if with_objects:
                syn_lines = [(line, tag) for line in syn_lines]
            yield from syn_lines

        child_lines = easybake(
            tag.get_children(),
            include_synonyms=include_synonyms,
            with_objects=with_objects,
        )
        if with_objects:
            child_lines = ((f'{tag.name}.{line[0]}', line[1]) for line in child_lines)
        else:
            child_lines = (f'{tag.name}.{line}' for line in child_lines)
        yield from child_lines

def flat_dict(tags, include_synonyms=True):
    '''
    A dictionary where every tag is its own key, and the value is a list
    containing itself and all of its descendants.

    If synonyms are included, their key is a string, and the value is the same
    list as the children of the master tag.

    {
        people: [people, family, mother],
        family: [family, mother],
        mother: [mother],
    }

    The list contains itself so that you can quickly ask whether a user's
    requested tag exists in that tree without having to write separate checks
    for equaling the main tag versus existing in the rest of the subtree.
    '''
    result = {}

    def recurse(tag):
        try:
            return result[tag]
        except KeyError:
            pass

        my_result = set()
        my_result.add(tag)

        for child in tag.get_children():
            my_result.update(recurse(child))

        result[tag] = my_result

        if include_synonyms:
            for synonym in tag.get_synonyms():
                result[synonym] = my_result
        return my_result

    for tag in tags:
        recurse(tag)

    return result

def nested_dict(tags):
    '''
    A dictionary where keys are tags, values are recursive dictionaries
    of children.
    Synonyms not included.

    {
        people: {
            family: {
                mother: {}
            }
        }
    }
    '''
    result = {}
    for tag in tags:
        result[tag] = nested_dict(tag)

    return result

def stdout(tags, depth=0):
    for tag in tags:
        children = tag.get_children()
        synonyms = tag.get_synonyms()

        pad = '    ' * depth
        print(pad + tag.name)

        synpad = '    ' * (depth + 1)
        for synonym in synonyms:
            print(synpad + '+' + synonym)

        stdout(children, depth=depth+1)

        if not tag.has_any_parent():
            print()
