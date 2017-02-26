import json
import os
import unittest
import random
import requests
import string

URL = 'http://localhost:5000'

def randstring(length):
    return ''.join(random.choice(string.ascii_letters) for x in range(length))

class EtiquetteSiteTest(unittest.TestCase):
    pass


class TagTest(EtiquetteSiteTest):
    '''
    Test the tag editor.
    '''
    def _helper(self, action, tagname):
        url = URL + '/tags/' + action
        data = {'tagname': tagname}
        print(action, data)
        response = requests.post(url, data=data)
        print(response.status_code)
        #print(response.text)
        j = response.json()
        print(json.dumps(j, indent=4, sort_keys=True))
        print()
        return

        
    def _create_helper(self, tagname):
        return self._helper('create_tag', tagname)

    def _delete_helper(self, tagname):
        return self._helper('delete_tag', tagname)

    def _delete_synonym_helper(self, tagname):
        return self._helper('delete_synonym', tagname)

    def test_create_tag(self):
        self._create_helper('1')

        # new tag
        tagname = randstring(10)
        self._create_helper(tagname)

        # new tags with grouping
        tagname = '.'.join(randstring(3) for x in range(2))
        self._create_helper(tagname)

        # new tag with new synonym
        tagname = '+'.join(randstring(3) for x in range(2))
        self._create_helper(tagname)

        # existing tag with new synonym
        tagname = randstring(10)
        self._create_helper('1.' + tagname)

        # renaming
        self._create_helper('testing')
        self._create_helper('testing=tester')
        self._create_helper('tester=testing')

        # trying to rename nonexisting
        tagname = randstring(10)
        self._create_helper(tagname + '=nonexist')
        self._create_helper(tagname + '+nonexist')

        # length errors
        tagname = randstring(100)
        self._create_helper(tagname)
        self._create_helper('')
        self._create_helper('*?%$')

        # regrouping.
        self._create_helper('test1.test2')
        self._create_helper('test3.test2')
        self._create_helper('test1.test2')
        self._create_helper('test3.test1.test2')

    def test_delete_tag(self):
        self._create_helper('1')
        self._delete_helper('1')

        self._create_helper('1.2')
        self._delete_helper('2')

        self._create_helper('1.2')
        self._delete_helper('1')

    def test_delete_synonym(self):
        tagname = randstring(5)
        self._create_helper('testing+' + tagname)
        self._create_helper('testing+' + tagname)
        self._delete_synonym_helper(tagname)

        self._create_helper('testing+' + tagname)
        self._delete_synonym_helper('testing+' + tagname)

        self._create_helper('tester.testing+' + tagname)
        self._delete_synonym_helper('tester.testing+' + tagname)




if __name__ == '__main__':
    unittest.main()
