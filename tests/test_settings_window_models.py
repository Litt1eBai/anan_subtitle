import unittest

from core.models import (
    MODEL_PROFILE_CUSTOM,
    MODEL_PROFILE_HYBRID,
    MODEL_PROFILE_OFFLINE,
)
from presentation.qt.settings_window_models import (
    build_model_config_updates,
    build_model_download_requests,
    build_model_profile_summary,
    build_model_selection_state,
    resolve_model_selection_state,
)


class ResolveModelSelectionStateTests(unittest.TestCase):
    def test_uses_preset_fields_for_offline_profile(self) -> None:
        selection = resolve_model_selection_state(
            MODEL_PROFILE_OFFLINE,
            custom_snapshot={},
        )

        self.assertEqual(selection.model, 'paraformer-zh')
        self.assertEqual(selection.detector_model, 'paraformer-zh-streaming')
        self.assertFalse(selection.disable_vad_model)

    def test_uses_custom_snapshot_for_custom_profile(self) -> None:
        selection = resolve_model_selection_state(
            MODEL_PROFILE_CUSTOM,
            custom_snapshot={
                'model': 'custom-asr',
                'detector_model': 'custom-detector',
                'vad_model': 'custom-vad',
                'punc_model': 'custom-punc',
                'disable_vad_model': True,
                'disable_punc_model': False,
            },
        )

        self.assertEqual(selection.model, 'custom-asr')
        self.assertTrue(selection.disable_vad_model)


class BuildModelProfileSummaryTests(unittest.TestCase):
    def test_marks_disabled_vad_and_punc(self) -> None:
        summary = build_model_profile_summary(
            MODEL_PROFILE_CUSTOM,
            build_model_selection_state(
                model='a',
                detector_model='b',
                vad_model='c',
                punc_model='d',
                disable_vad_model=True,
                disable_punc_model=True,
            ),
        )

        self.assertIn('VAD: 禁用', summary)
        self.assertIn('PUNC: 禁用', summary)


class BuildModelDownloadRequestsTests(unittest.TestCase):
    def test_hybrid_profile_downloads_detector_and_asr(self) -> None:
        selection = build_model_selection_state(
            model='paraformer-zh',
            detector_model='paraformer-zh-streaming',
            vad_model='fsmn-vad',
            punc_model='ct-punc',
            disable_vad_model=False,
            disable_punc_model=False,
        )

        requests = build_model_download_requests(MODEL_PROFILE_HYBRID, selection)

        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]['model'], 'paraformer-zh-streaming')
        self.assertEqual(requests[1]['vad_model'], 'fsmn-vad')

    def test_streaming_model_skips_vad_and_punc(self) -> None:
        selection = build_model_selection_state(
            model='paraformer-zh-streaming',
            detector_model='paraformer-zh-streaming',
            vad_model='fsmn-vad',
            punc_model='ct-punc',
            disable_vad_model=False,
            disable_punc_model=False,
        )

        requests = build_model_download_requests(MODEL_PROFILE_OFFLINE, selection)

        self.assertEqual(len(requests), 1)
        self.assertNotIn('vad_model', requests[0])
        self.assertNotIn('punc_model', requests[0])


class BuildModelConfigUpdatesTests(unittest.TestCase):
    def test_includes_profile_and_selection_fields(self) -> None:
        updates = build_model_config_updates(
            MODEL_PROFILE_OFFLINE,
            model_download_on_startup=True,
            selection=build_model_selection_state(
                model='paraformer-zh',
                detector_model='paraformer-zh-streaming',
                vad_model='fsmn-vad',
                punc_model='ct-punc',
                disable_vad_model=False,
                disable_punc_model=False,
            ),
        )

        self.assertEqual(updates['model_profile'], MODEL_PROFILE_OFFLINE)
        self.assertTrue(updates['model_download_on_startup'])
        self.assertEqual(updates['model'], 'paraformer-zh')
        self.assertTrue(updates['model_profile_prompted'])


if __name__ == '__main__':
    unittest.main()
