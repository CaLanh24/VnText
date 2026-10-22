import struct
import unittest

from tests.tools.renpy_owner_font_audit import cmap_glyphs


def font(subtable,encoding=1,glyphs=10):
    cmap=struct.pack('>HHHHL',0,1,3,encoding,12)+subtable
    maxp=struct.pack('>LH',0x10000,glyphs)
    return (struct.pack('>LHHHH',0x10000,2,0,0,0)+
        struct.pack('>4sLLL',b'cmap',0,44,len(cmap))+
        struct.pack('>4sLLL',b'maxp',0,44+len(cmap),len(maxp))+cmap+maxp)


class FontCmapAuditTests(unittest.TestCase):
    def test_unicode_bmp_delta_and_missing_vietnamese(self):
        sub=struct.pack('>7H',4,32,0,4,4,1,0)+struct.pack('>9H',65,65535,0,65,65535,65474,1,0,0)
        result=cmap_glyphs(font(sub),[65,0x1EA3])
        self.assertEqual(result['glyph_ids'],{'U+0041':3,'U+1EA3':0})
        self.assertEqual(result['missing'],['U+1EA3 ả'])

    def test_unicode_bmp_glyph_array_offset(self):
        sub=struct.pack('>7H',4,34,0,4,4,1,0)+struct.pack('>10H',65,65535,0,65,65535,0,1,4,0,3)
        self.assertEqual(cmap_glyphs(font(sub),[65])['glyph_ids']['U+0041'],3)

    def test_unicode_full_and_constant_groups(self):
        for fmt,expected in [(12,5),(13,3)]:
            sub=struct.pack('>HHLLL',fmt,0,28,0,1)+struct.pack('>LLL',0x1EA3,0x1EA5,3)
            result=cmap_glyphs(font(sub,encoding=10),[0x1EA3,0x1EA5,0x1ED9])
            self.assertEqual(result['glyph_ids']['U+1EA5'],expected)
            self.assertEqual(result['missing'],['U+1ED9 ộ'])

    def test_outside_table_and_glyph_bounds_are_not_coverage(self):
        sub=struct.pack('>HHLLL',12,0,28,0,1)+struct.pack('>LLL',65,65,300)
        with self.assertRaisesRegex(ValueError,'maxp'):
            cmap_glyphs(font(sub,encoding=10),[65])
        with self.assertRaisesRegex(ValueError,'outside file'):
            cmap_glyphs(font(sub,encoding=10)[:-4],[65])
