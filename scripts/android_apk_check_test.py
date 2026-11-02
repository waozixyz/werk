#!/usr/bin/env python3
"""Exercise the APK bytecode allowlist without building an APK."""
import unittest

from android_apk_check import allowed_class


class AllowedClassTest(unittest.TestCase):
    def test_approved_classes_and_compiler_helpers(self):
        for name in ("AccountHandoff", "AccountHandoffConsentActivity",
                     "AccountHandoffNameProvider", "AccountHandoffRequestActivity"):
            base = "Lorg/kryonlabs/platform/" + name
            for suffix in (";", "$$ExternalSyntheticLambda0;",
                           "$$ExternalSyntheticApiModelOutline0;",
                           "$$ExternalSyntheticApiModelOutline12;"):
                with self.subTest(descriptor=base + suffix):
                    self.assertTrue(allowed_class(base + suffix))
        for descriptor in ("Lxyz/waozi/pass/R;", "Lxyz/waozi/pass/R$string;"):
            self.assertTrue(allowed_class(descriptor))

    def test_rejects_other_and_lookalike_classes(self):
        for descriptor in (
            "Lxyz/waozi/pass/MainActivity;",
            "Lxyz/waozi/pass/AccountHandoff$$ExternalSyntheticApiModelOutline0;",
            "Lorg/kryonlabs/platform/Other$$ExternalSyntheticApiModelOutline0;",
            "Lorg/kryonlabs/platform/AccountHandoffExtra$$ExternalSyntheticApiModelOutline0;",
            "Lorg/kryonlabs/platform/AccountHandoff$$ExternalSyntheticApiModelOutline;",
            "Lorg/kryonlabs/platform/AccountHandoff$$ExternalSyntheticApiModelOutline0Extra;",
            "Lorg/kryonlabs/platform/AccountHandoff$$ExternalSyntheticLambda0Extra;",
            "Lxyz/waozi/pass/Rogue;",
        ):
            with self.subTest(descriptor=descriptor):
                self.assertFalse(allowed_class(descriptor))


if __name__ == "__main__":
    unittest.main()
