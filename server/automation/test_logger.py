import os
import sys
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(__file__))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from utils.logger import HanyangLogger


class LoggerFormattingTests(unittest.TestCase):
    def test_format_fields_orders_event_first(self):
        logger = HanyangLogger("system", user_id="logger-test", default_fields={"run_id": "run-123"})
        rendered = logger._format_fields({"event": "lecture_completed", "lecture_title": "테스트 강의", "elapsed_sec": 42})
        self.assertTrue(rendered.startswith(' | event=lecture_completed'))
        self.assertIn('run_id=run-123', rendered)
        self.assertIn('lecture_title="테스트 강의"', rendered)
        self.assertIn('elapsed_sec=42', rendered)
        logger.close()

    def test_with_context_merges_default_fields(self):
        logger = HanyangLogger("system", user_id="logger-test", default_fields={"run_id": "run-123"})
        scoped = logger.with_context(lecture_title="강의 A")
        rendered = scoped._format_fields({"event": "playback_stalled"})
        self.assertIn('run_id=run-123', rendered)
        self.assertIn('lecture_title="강의 A"', rendered)
        self.assertIn('event=playback_stalled', rendered)
        scoped.close()
        logger.close()


if __name__ == "__main__":
    unittest.main()
