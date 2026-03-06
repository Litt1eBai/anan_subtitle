import unittest

from core.subtitle_pipeline import merge_incremental_text
from core.text_postprocess import extract_text, replace_sentence_initial_wo
from text_utils import (
    extract_text as legacy_extract_text,
    merge_incremental_text as legacy_merge_incremental_text,
    replace_sentence_initial_wo as legacy_replace_sentence_initial_wo,
)


class TextUtilsImportCompatibilityTests(unittest.TestCase):
    def test_legacy_text_utils_exports_current_core_functions(self) -> None:
        self.assertIs(legacy_extract_text, extract_text)
        self.assertIs(legacy_merge_incremental_text, merge_incremental_text)
        self.assertIs(legacy_replace_sentence_initial_wo, replace_sentence_initial_wo)
