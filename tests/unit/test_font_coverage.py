"""Run the established cmap vectors against the product parser as well."""
import struct
from unittest.mock import patch
from tests.unit.test_renpy_font_cmap_audit import FontCmapAuditTests as _Base, font
from vntext.font_coverage import cmap_glyphs


class ProductionFontCoverageTests(_Base):
    def setUp(self):
        replacement = patch("tests.unit.test_renpy_font_cmap_audit.cmap_glyphs", cmap_glyphs)
        replacement.start(); self.addCleanup(replacement.stop)

    def test_unsorted_groups_are_rejected_instead_of_binary_searching_invalid_input(self):
        sub = struct.pack('>HHLLL', 12, 0, 40, 0, 2) + struct.pack('>LLLLLL', 70, 70, 3, 65, 65, 4)
        with self.assertRaisesRegex(ValueError, 'group order'):
            cmap_glyphs(font(sub, encoding=10), [65])


del _Base
