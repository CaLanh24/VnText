"""The Release DEV worker smoke hands the patch off to the single-file patch installer, so the publisher must build that installer first."""
import unittest
from pathlib import Path

PUBLISH = (Path(__file__).resolve().parents[2] / "release" / "publish.ps1").read_text(encoding="utf-8-sig")


class PublishInstallerOrderTests(unittest.TestCase):
    def test_installer_is_built_before_the_dev_smoke_and_handed_to_it(self):
        build = PUBLISH.index("dotnet publish $installerProj")
        smoke = PUBLISH.index('"--smoke-worker"')
        self.assertLess(build, smoke)
        self.assertEqual(1, PUBLISH.count("dotnet publish $installerProj"))                      # built once, not moved-and-duplicated
        env = PUBLISH.index("VNTEXT_PATCH_INSTALLER = $installerBuiltExe")
        self.assertLess(build, env)
        self.assertLess(env, smoke)
        self.assertLess(PUBLISH.index("$installerBuiltExe = Join-Path $installerPublish"), env)  # defined before it is used


if __name__ == "__main__":
    unittest.main()
