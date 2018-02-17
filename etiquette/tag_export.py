'''
This file provides a variety of functions for exporting a PDB's tags into other
formats. Strings, dicts, etc.
'''

def easybake(tags):
    '''
    A string where every line is the qualified name of a tag or its synonyms.

    people
    people.family
    people.family.mother
    people.family.mother+mom
    '''
    lines = []
    tags = list(tags)
    for tag in tags:
        qualname = tag.qualified_name()
        lines.append(qualname)
        lines.extend(qualname + '+' + syn for syn in tag.synonyms())
    return '\n'.join(lines)

def flat_dict(tags):
    '''
    A dictionary where every tag is its own key, and the value is a list
    containing itself all of its nested children.
    Synonyms not included.

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
    for tag in tags:
        for child in tag.walk_children():
            children = list(child.walk_children())
            result[child] = children
            for synonym in child.synonyms():
                result[synonym] = children
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

def qualified_names(tags):
    '''
    A dictionary where keys are string names, values are qualified names.
    Synonyms included.

    {
        'people': 'people',
        'family': 'people.family',
        'mother': 'people.family.mother',
        'mom': 'people.family.mother',
    }
    '''
    results = {}
    for tag in tags:
        qualname = tag.qualified_name()
        results[tag.name] = qualname
        for synonym in tag.synonyms():
            results[synonym] = qualname
    return results

def stdout(tags, depth=0):
    for tag in tags:
        children = tag.get_children()
        synonyms = tag.synonyms()

        pad = '    ' * depth
        print(pad + tag.name)

        synpad = '    ' * (depth + 1)
        for synonym in synonyms:
            print(synpad + '+' + synonym)

        stdout(children, depth=depth+1)

        if tag.get_parent() is None:
            print()
