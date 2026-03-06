import unittest

from presentation.controller import SubtitlePresentationController
from presentation.model import SubtitleViewState


class FakeSubtitleView:
    def __init__(self) -> None:
        self.states: list[SubtitleViewState] = []

    def apply_view_state(self, view_state: SubtitleViewState) -> None:
        self.states.append(view_state)


class SubtitlePresentationControllerTests(unittest.TestCase):
    def test_bind_view_pushes_initial_state(self) -> None:
        view = FakeSubtitleView()
        controller = SubtitlePresentationController()

        controller.bind_view(view)

        self.assertEqual(view.states[-1].status_text, "模型加载中...")
        self.assertEqual(view.states[-1].subtitle_text, "")

    def test_handle_subtitle_updates_view_state(self) -> None:
        view = FakeSubtitleView()
        controller = SubtitlePresentationController(view)

        controller.handle_subtitle(" 你好 ")

        self.assertEqual(view.states[-1].subtitle_text, "你好")
        self.assertEqual(controller.export_view_state().subtitle_text, "你好")

    def test_handle_error_clears_subtitle_and_sets_status(self) -> None:
        view = FakeSubtitleView()
        controller = SubtitlePresentationController(view)
        controller.handle_subtitle("你好")

        controller.handle_error("boom")

        self.assertEqual(view.states[-1].subtitle_text, "")
        self.assertEqual(view.states[-1].status_text, "[ERROR] boom")

    def test_clear_subtitle_preserves_status(self) -> None:
        view = FakeSubtitleView()
        controller = SubtitlePresentationController(view)
        controller.handle_status("就绪")
        controller.handle_subtitle("你好")

        controller.clear_subtitle()

        self.assertEqual(view.states[-1].subtitle_text, "")
        self.assertEqual(view.states[-1].status_text, "就绪")


if __name__ == "__main__":
    unittest.main()
