import unittest

import etiquette


class EtiquetteTest(unittest.TestCase):
    def setUp(self):
        self.P = etiquette.photodb.PhotoDB(ephemeral=True)

    def tearDown(self):
        self.P.close()
        del self.P
