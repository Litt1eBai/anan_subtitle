import unittest

from app import main
from app.application import main as application_main


class AppImportCompatibilityTests(unittest.TestCase):
    def test_app_package_reexports_application_main(self) -> None:
        self.assertIs(main, application_main)


if __name__ == "__main__":
    unittest.main()
