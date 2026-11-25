import unittest
from pathlib import Path
from unittest.mock import patch
from release.dependency_profiles import select,installed
ROOT=Path(__file__).resolve().parents[2]
class Profiles(unittest.TestCase):
 def test_only_the_runtime_profile_is_selected(self):
  self.assertEqual([p.name for p in select(ROOT,(3,12))],['windows-cp312-runtime.txt'])
  self.assertEqual([p.name for p in select(ROOT,(3,14))],['windows-cp314-runtime.txt'])
 def test_unsupported_runtime_refuses_instead_of_using_ranges(self):
  with self.assertRaises(ValueError):select(ROOT,(3,11))
 def test_preinstalled_mismatch_is_a_blocker_not_an_implicit_upgrade(self):
  with patch('release.dependency_profiles.version',return_value='0'):
   with self.assertRaisesRegex(ValueError,'differ from lock'):installed(select(ROOT,(3,14)))
