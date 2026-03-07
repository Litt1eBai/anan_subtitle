import unittest

from config import (
    apply_model_profile_to_args as legacy_apply_model_profile_to_args,
    apply_model_profile_to_settings as legacy_apply_model_profile_to_settings,
    normalize_config as legacy_normalize_config,
    parse_chunk_size as legacy_parse_chunk_size,
    parse_model_profile as legacy_parse_model_profile,
)
from core.settings import (
    apply_model_profile_to_args,
    apply_model_profile_to_settings,
    normalize_config,
    parse_chunk_size,
    parse_model_profile,
)


class ConfigImportCompatibilityTests(unittest.TestCase):
    def test_config_module_reexports_core_settings_helpers(self) -> None:
        self.assertIs(legacy_parse_chunk_size, parse_chunk_size)
        self.assertIs(legacy_parse_model_profile, parse_model_profile)
        self.assertIs(legacy_normalize_config, normalize_config)
        self.assertIs(legacy_apply_model_profile_to_settings, apply_model_profile_to_settings)
        self.assertIs(legacy_apply_model_profile_to_args, apply_model_profile_to_args)
