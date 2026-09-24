import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chinesecap.core import Cue, clean_text, export, load_project, make_cues, speaker_at, stamp, subtitle_lines, validate_correction
from chinesecap.corrector import LocalCorrector
from chinesecap.pipeline import youtube_url


class CoreTests(unittest.TestCase):
    def test_taiwan_and_fillers(self):
        self.assertEqual(clean_text('嗯，软件里面有视频。'), '軟體裡面有影片。')
        self.assertEqual(clean_text('那個人就是老師。'), '那個人就是老師。')
        self.assertEqual(clean_text('嗯,那個,就是,我們開始討論。'), '我們開始討論。')
        self.assertEqual(clean_text('這個就是我們的目標。'), '這個就是我們的目標。')

    def test_timestamp_rounding(self):
        self.assertEqual(stamp(59.9996, True), '00:01:00,000')
        self.assertEqual(stamp(3661.234, True), '01:01:01,234')

    def test_subtitle_wraps_only_at_punctuation(self):
        term = '期中考成績分析與補救教學規劃'
        term_wrapped = subtitle_lines('說話者 1：' + term, preferred=12)
        self.assertIn(term, term_wrapped.splitlines())
        wrapped = subtitle_lines('說話者 1：今天介紹產品，接著說明完整操作流程。', preferred=15)
        self.assertEqual(wrapped, '說話者 1：今天介紹產品，\n接著說明完整操作流程。')
        self.assertIn(term, subtitle_lines('產品說明，' + term + '，適合專業工作。', preferred=14))

    def test_speaker_boundary_and_overlap(self):
        turns = [(0, 1, 0), (1, 2, 1)]
        self.assertEqual(speaker_at(.8, 1.2, turns)[0], '說話者 1')
        self.assertEqual(speaker_at(.5, 1.5, [(0, 2, 0), (1, 3, 1)])[0], '重疊發言')
        self.assertEqual(speaker_at(3, 4, turns)[0], '未辨識')
        cues = make_cues([(0, .5, '你好'), (1, 1.5, '謝謝')], turns)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[1].speaker, '說話者 2')

    def test_exports_keep_timing_and_skip_empty(self):
        cues = [Cue(0, 1, '說話者 1', '嗯', ''), Cue(2, 3.25, '說話者 2', '软件', '軟體')]
        with tempfile.TemporaryDirectory() as tmp:
            result = export(cues, Path(tmp), '../name', {})
            srt = (result / '字幕.srt').read_text(encoding='utf-8')
            self.assertTrue(srt.startswith('1\n00:00:02,000 --> 00:00:03,250'))
            self.assertIn('說話者 2：軟體', srt)
            loaded, _ = load_project(result / '專案.json')
            self.assertEqual(loaded, cues)
            self.assertNotEqual(result, export(cues, Path(tmp), '../name', {}))

    def test_bad_timing_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for cues in [[Cue(float('nan'), 3, '', '')], [Cue(0, 2, '', ''), Cue(1, 3, '', '')]]:
                with self.assertRaises(ValueError):
                    export(cues, Path(tmp), 'bad', {})

    def test_correction_guard(self):
        self.assertFalse(validate_correction('今天預算是 100 元', '今天預算是 1000 元'))
        self.assertFalse(validate_correction('這是一段不能被模型隨意摘要刪除的內容', '摘要'))
        self.assertTrue(validate_correction('這個軟替很好用', '這個軟體很好用'))
        self.assertFalse(validate_correction('非常累的時候就會站在陽台上吹吹風', '和你們一起走過很多很多的路堅持到底'))

    def test_bad_llm_ids_keep_original(self):
        cue = Cue(0, 1, '說話者 1', '你好', '你好')
        fake = {'choices': [{'message': {'content': json.dumps({'items': [{'id': 7, 'text': '錯誤'}]})}}]}
        corrector = LocalCorrector(Path('.'), 1, lambda _: None, None)
        with patch.object(corrector, 'request', return_value=fake):
            corrector.correct([cue], '')
        self.assertEqual(cue.text, '你好')
        self.assertIn('失敗', cue.notes[-1])

    def test_url_restriction(self):
        self.assertTrue(youtube_url('https://youtu.be/abc'))
        self.assertFalse(youtube_url('https://youtube.com.evil.test/foo'))
        self.assertFalse(youtube_url('file:///etc/passwd'))


if __name__ == '__main__':
    unittest.main()
