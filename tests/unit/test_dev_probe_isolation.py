"""DEV_PROBES-only code (picker overrides) must be unreachable from a release build."""
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "wpf_app" / "VNText.Studio.App"


class DevProbeIsolationTests(unittest.TestCase):
    def test_probe_sources_are_removed_from_non_probe_builds(self):
        csproj = (APP / "VNText.Studio.App.csproj").read_text(encoding="utf-8")
        self.assertIn('<Compile Remove="Services\*Probe.cs" />', csproj)
        self.assertIn("DEV_PROBES", csproj)
        # Release never turns the probes on by default.
        self.assertRegex(csproj, r"Condition=\"'\$\(EnableDevProbes\)' == '' and '\$\(Configuration\)' == 'Debug'\"")
        probe = (APP / "Services" / "PickerOverrideProbe.cs").read_text(encoding="utf-8")
        self.assertTrue(probe.lstrip().startswith("#if DEV_PROBES"))
        self.assertTrue(probe.rstrip().endswith("#endif"))

    def test_every_reference_outside_the_probe_file_sits_inside_a_dev_probes_block(self):
        for path in APP.rglob("*.cs"):
            if path.name == "PickerOverrideProbe.cs" or "obj" in path.parts or "bin" in path.parts:
                continue
            depth, inside = 0, []
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if re.match(r"#if\b", stripped):
                    depth += 1
                    inside.append(stripped == "#if DEV_PROBES" or (inside and inside[-1]))
                elif stripped == "#endif":
                    depth -= 1
                    inside.pop()
                elif "PickerOverrideProbe" in line:
                    self.assertTrue(inside and inside[-1], f"{path.name}:{number} uses the probe outside #if DEV_PROBES")
            self.assertEqual(0, depth, path.name)


if __name__ == "__main__":
    unittest.main()
