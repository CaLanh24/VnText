import unittest
from pathlib import Path
from unittest.mock import patch
from release.dependency_profiles import select,installed
ROOT=Path(__file__).resolve().parents[2]
class Profiles(unittest.TestCase):
 def test_worker_never_pulls_in_qt_or_builder(self):
  self.assertEqual([p.name for p in select(ROOT,(3,12))],['windows-cp312-runtime.txt'])
  self.assertEqual(len(select(ROOT,(3,14),build=True,legacy_qt=True)),3)
 def test_unsupported_runtime_refuses_instead_of_using_ranges(self):
  with self.assertRaises(ValueError):select(ROOT,(3,11))
 def test_preinstalled_mismatch_is_a_blocker_not_an_implicit_upgrade(self):
  with patch('release.dependency_profiles.version',return_value='0'):
   with self.assertRaisesRegex(ValueError,'differ from lock'):installed(select(ROOT,(3,14)))
