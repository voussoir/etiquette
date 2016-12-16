import os
import phototagger
import unittest
import random

class PhotoDBTest(unittest.TestCase):
    def setUp(self):
        self.P = phototagger.PhotoDB(':memory:')


class AlbumTest(PhotoDBTest):
    '''
    Test the creation and properties of albums
    '''
    def test_create_album(self):
        album = self.P.new_album()
        test = self.P.get_album(album.id)
        self.assertEqual(album, test)

        album = self.P.new_album(title='test1', description='test2')
        self.assertEqual(album.title, 'test1')
        self.assertEqual(album.description, 'test2')

    def test_delete_album_nonrecursive(self):
        album = self.P.new_album()
        album.delete()
        self.assertRaises(phototagger.NoSuchAlbum, self.P.get_album, album.id)

    def test_edit_album(self):
        album = self.P.new_album(title='t1', description='d1')
        album.edit(title='t2')
        self.assertEqual(album.title, 't2')
        self.assertEqual(album.description, 'd1')

        album.edit(title='t3', description='d2')
        self.assertEqual(album.title, 't3')
        self.assertEqual(album.description, 'd2')

        album.edit(description='d3')
        album = self.P.get_album(album.id)
        self.assertEqual(album.title, 't3')
        self.assertEqual(album.description, 'd3')


class PhotoTest(PhotoDBTest):
    '''
    Test the creation and properties of photos
    '''
    def test_create_photo(self):
        photo = self.P.new_photo('samples\\bolts.jpg')
        self.assertGreater(photo.area, 1)

    def test_delete_photo(self):
        pass

    def test_reload_metadata(self):
        pass


class TagTest(PhotoDBTest):
    '''
    Test the creation and properties of tags
    '''
    def test_normalize_tagname(self):
        tag = self.P.new_tag('test normalize')
        self.assertEqual(tag.name, 'test_normalize')

        tag = self.P.new_tag('TEST!!NORMALIZE')
        self.assertEqual(tag.name, 'testnormalize')

        self.assertRaises(phototagger.TagTooShort, self.P.new_tag, '')
        self.assertRaises(phototagger.TagTooShort, self.P.new_tag, '!??*&')
        self.assertRaises(phototagger.TagTooLong, self.P.new_tag, 'a'*(phototagger.MAX_TAG_NAME_LENGTH+1))

    def test_create_tag(self):
        tag = self.P.new_tag('test create tag')
        self.assertEqual(tag.name, 'test_create_tag')
        self.assertRaises(phototagger.TagExists, self.P.new_tag, 'test create tag')

    def test_delete_tag_nonrecursive(self):
        tag = self.P.new_tag('test delete tag non')
        tag.delete()
        self.assertRaises(phototagger.NoSuchTag, self.P.get_tag, tag.name)

    def test_rename_tag(self):
        tag = self.P.new_tag('test rename pre')
        self.assertEqual(tag.name, 'test_rename_pre')
        tag.rename('test rename post')
        self.assertEqual(self.P.get_tag('test rename post'), tag)
        self.assertRaises(phototagger.NoSuchTag, self.P.get_tag, 'test rename pre')
        self.assertRaises(phototagger.TagTooShort, tag.rename, '??')
        tag.rename(tag.name)  # does nothing


class SearchTest(PhotoDBTest):
    def search_extension(self):
        pass
    def search_minmaxers(self):
        pass
    def search_notags(self):
        pass
    def search_tags(self):
        pass


class SynonymTest(PhotoDBTest):
    '''
    Test the creation and management of synonyms
    '''
    def test_create_synonym(self):
        tag = self.P.new_tag('test create syn')
        tag2 = self.P.new_tag('getting in the way')
        tag.add_synonym('test make syn')

        test = self.P.get_tag('test make syn')
        self.assertEqual(test, tag)
        self.assertTrue('test_make_syn' in tag.synonyms())

        self.assertRaises(phototagger.TagExists, tag.add_synonym, 'test make syn')

    def test_delete_synonym(self):
        tag = self.P.new_tag('test del syn')
        tag.add_synonym('test rem syn')
        tag.remove_synonym('test rem syn')
        self.assertRaises(phototagger.NoSuchSynonym, tag.remove_synonym, 'test rem syn')

    def test_convert_tag_to_synonym(self):
        tag1 = self.P.new_tag('convert 1')
        tag2 = self.P.new_tag('convert 2')
        tag2.convert_to_synonym(tag1)

        test = self.P.get_tag(tag2)
        self.assertEqual(test, tag1)
        self.assertTrue('convert_2' in tag1.synonyms())

    def test_get_synonyms(self):
        tag = self.P.new_tag('test get syns')
        tag.add_synonym('test get syns1')
        tag.add_synonym('test get syns2')
        tag.add_synonym('test get syns3')
        self.assertEqual(len(tag.synonyms()), 3)


class AlbumGroupTest(PhotoDBTest):
    '''
    Test the relationships between albums as they form and leave groups
    '''
    def test_delete_album_recursive(self):
        pass

    def test_join_album(self):
        pass

    def test_leave_album(self):
        pass

    def test_album_children(self):
        pass

    def test_album_parents(self):
        pass


class TagGroupTest(PhotoDBTest):
    '''
    Test the relationships between tags as they form and leave groups
    '''
    def test_delete_tag_recursive(self):
        pass

    def test_join_tag(self):
        pass

    def test_leave_tag(self):
        pass

    def test_tag_children(self):
        pass

    def test_tag_parents(self):
        pass

    def test_tag_qualified_name(self):
        pass


class AlbumPhotoTest(PhotoDBTest):
    '''
    Test the relationships between albums and photos
    '''
    def test_add_photo(self):
        pass

    def test_remove_photo(self):
        pass


class PhotoTagTest(PhotoDBTest):
    '''
    Test the relationships between photos and tags
    '''
    def test_photo_has_tag(self):
        pass

    def test_add_tag(self):
        pass

    def test_remove_tag(self):
        pass




if __name__ == '__main__':
    unittest.main()
