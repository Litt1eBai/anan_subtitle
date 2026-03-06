import unittest

from text_utils import (
    extract_text,
    merge_incremental_text,
    replace_sentence_initial_wo,
)


class ExtractTextTests(unittest.TestCase):
    def test_extract_text_from_dict_text_field(self) -> None:
        self.assertEqual(extract_text({"text": " 你好 "}), "你好")

    def test_extract_text_from_sentence_info(self) -> None:
        result = {
            "sentence_info": [
                {"text": "你"},
                {"text": "好"},
            ]
        }
        self.assertEqual(extract_text(result), "你好")

    def test_extract_text_from_list_result(self) -> None:
        self.assertEqual(extract_text([{"text": "测试"}]), "测试")

    def test_extract_text_falls_back_to_string(self) -> None:
        self.assertEqual(extract_text(123), "123")


class MergeIncrementalTextTests(unittest.TestCase):
    def test_merge_when_new_text_extends_current(self) -> None:
        self.assertEqual(merge_incremental_text("你好", "你好啊"), "你好啊")

    def test_merge_when_current_already_contains_new_suffix(self) -> None:
        self.assertEqual(merge_incremental_text("你好啊", "啊"), "你好啊")

    def test_merge_when_overlap_exists(self) -> None:
        self.assertEqual(merge_incremental_text("今天", "天下雨"), "今天下雨")

    def test_merge_when_no_overlap_exists(self) -> None:
        self.assertEqual(merge_incremental_text("你好", "世界"), "你好世界")


class ReplaceSentenceInitialWoTests(unittest.TestCase):
    def test_replace_all_wo_characters(self) -> None:
        self.assertEqual(replace_sentence_initial_wo("我和我"), "吾辈和吾辈")


if __name__ == "__main__":
    unittest.main()
