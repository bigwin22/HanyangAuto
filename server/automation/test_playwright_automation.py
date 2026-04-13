import importlib.util
import os
import sys
import types
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(__file__))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

utils_pkg = types.ModuleType("utils")
logger_module = types.ModuleType("utils.logger")
database_module = types.ModuleType("utils.database")
security_module = types.ModuleType("utils.security")


class DummyLogger:
    def __init__(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def warn(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None

    def event(self, *args, **kwargs):
        return None

    @staticmethod
    def new_run_id(prefix="run"):
        return f"{prefix}-test"


logger_module.HanyangLogger = DummyLogger
database_module.update_user_status = lambda *args, **kwargs: None
security_module.mask_sensitive_text = lambda value: value
security_module.mask_sensitive_url = lambda value: value

sys.modules.setdefault("utils", utils_pkg)
sys.modules["utils.logger"] = logger_module
sys.modules["utils.database"] = database_module
sys.modules["utils.security"] = security_module

MODULE_PATH = os.path.join(os.path.dirname(__file__), "playwright_automation.py")
SPEC = importlib.util.spec_from_file_location("testable_playwright_automation", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

LectureItem = MODULE.LectureItem
_classify_playback_transition = MODULE._classify_playback_transition
_get_lecture_availability_reason = MODULE._get_lecture_availability_reason
_get_non_required_recording_reason = MODULE._get_non_required_recording_reason
_is_static_pending_without_player = MODULE._is_static_pending_without_player
_snapshot_from_direct_media = MODULE._snapshot_from_direct_media


def make_snapshot(
    *,
    status_parts=None,
    body_text="",
    media_states=None,
    player_class="",
    play_pause_class="",
    timing=None,
    has_inner_frame=False,
    hycms_src="",
    completed=False,
):
    return {
        "statusParts": status_parts or [],
        "bodyText": body_text,
        "mediaStates": media_states or [],
        "playerClass": player_class,
        "playPauseClass": play_pause_class,
        "timing": timing or {},
        "hasInnerFrame": has_inner_frame,
        "hycmsSrc": hycms_src,
        "completed": completed,
    }


def media(*, paused=True, ended=False, current_time=0, duration=0, ready_state=4):
    return {
        "paused": paused,
        "ended": ended,
        "currentTime": current_time,
        "duration": duration,
        "readyState": ready_state,
    }


class LectureAvailabilityTests(unittest.TestCase):
    def test_zero_progress_incomplete_is_not_scheduled(self):
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "미결"])
        self.assertEqual(_get_lecture_availability_reason(snapshot), (None, None, None))

    def test_status_parts_drive_scheduled_detection(self):
        snapshot = make_snapshot(status_parts=["학습 예정", "4월 30일부터 학습이 가능합니다"])
        state, source, marker = _get_lecture_availability_reason(snapshot)
        self.assertEqual(state, "scheduled")
        self.assertEqual(source, "statusParts")
        self.assertIn(marker, {"학습 예정", "부터 학습이 가능합니다", "학습이 가능합니다"})

    def test_status_parts_drive_expired_detection(self):
        snapshot = make_snapshot(status_parts=["학습 기간이 종료되었습니다."])
        self.assertEqual(
            _get_lecture_availability_reason(snapshot),
            ("expired", "statusParts", "학습 기간이 종료되었습니다."),
        )

    def test_body_text_only_is_used_as_fallback(self):
        snapshot = make_snapshot(body_text="이 강의는 아직 학습할 수 없습니다")
        self.assertEqual(
            _get_lecture_availability_reason(snapshot),
            ("scheduled", "bodyText", "아직 학습할 수 없습니다"),
        )


class NonRequiredRecordingTests(unittest.TestCase):
    def test_title_only_recording_is_not_non_required(self):
        lecture = LectureItem(
            course_id="1",
            module_name="m",
            item_id="i",
            title="전자기학 강의녹화",
            html_url="https://example.com/html",
            external_url="https://example.com/ext",
            content_id=None,
        )
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "미결"])
        self.assertEqual(_get_non_required_recording_reason(snapshot, lecture), (False, None))

    def test_attendance_not_required_and_recording_is_non_required(self):
        lecture = LectureItem(
            course_id="1",
            module_name="m",
            item_id="i",
            title="전자기학 강의녹화",
            html_url="https://example.com/html",
            external_url="https://example.com/ext",
            content_id=None,
        )
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "출결 대상 아님"])
        self.assertEqual(_get_non_required_recording_reason(snapshot, lecture), (True, "강의녹화"))


class PlaybackTransitionTests(unittest.TestCase):
    def test_paused_resume_is_stalled(self):
        before = make_snapshot(
            media_states=[media(paused=True, current_time=2692.37, duration=3668.86)],
            timing={"currentSeconds": 2692, "totalSeconds": 3668},
        )
        after = make_snapshot(
            media_states=[media(paused=True, current_time=2692.37, duration=3668.86)],
            timing={"currentSeconds": 0, "totalSeconds": 3668},
        )
        self.assertEqual(_classify_playback_transition(before, after), "stalled")

    def test_running_media_is_progressing(self):
        before = make_snapshot(media_states=[media(paused=True, current_time=0, duration=2041.58)])
        after = make_snapshot(
            media_states=[media(paused=False, current_time=10.6, duration=2041.58)],
            timing={"currentSeconds": 10, "totalSeconds": 2041},
        )
        self.assertEqual(_classify_playback_transition(before, after), "progressing")

    def test_restart_after_end_is_not_stalled(self):
        before = make_snapshot(
            media_states=[media(paused=False, current_time=2266.2, duration=2268.73)],
            timing={"currentSeconds": 2266, "totalSeconds": 2268},
        )
        after = make_snapshot(
            media_states=[media(paused=False, ended=False, current_time=6.9, duration=2268.73)],
            timing={"currentSeconds": 6, "totalSeconds": 2268},
            play_pause_class="vc-pctrl-on-playing",
        )
        self.assertEqual(_classify_playback_transition(before, after), "running")


class NoPlayerHeuristicTests(unittest.TestCase):
    def test_static_pending_without_player_is_detected(self):
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "미결"])
        self.assertTrue(_is_static_pending_without_player(snapshot))

    def test_incomplete_without_progress_details_is_detected(self):
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "미완료"])
        self.assertTrue(_is_static_pending_without_player(snapshot))

    def test_inner_frame_prevents_no_player_skip(self):
        snapshot = make_snapshot(
            status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "미결"],
            has_inner_frame=True,
        )
        self.assertFalse(_is_static_pending_without_player(snapshot))

    def test_nonzero_progress_without_player_is_not_detected(self):
        snapshot = make_snapshot(status_parts=["학습 진행 상태:", "19분 59초(58.76%)", "미완료", "미결"])
        self.assertFalse(_is_static_pending_without_player(snapshot))

    def test_direct_media_prevents_no_player_skip(self):
        snapshot = make_snapshot(
            status_parts=["학습 진행 상태:", "0초(0%)", "미완료", "미결"],
            has_inner_frame=False,
        )
        snapshot["hasDirectMedia"] = True
        snapshot["directMediaStates"] = [media(paused=False, current_time=3, duration=120)]
        self.assertFalse(_is_static_pending_without_player(snapshot))

    def test_direct_media_snapshot_conversion(self):
        snapshot = make_snapshot()
        snapshot["directMediaStates"] = [media(paused=False, current_time=12, duration=120)]
        converted = _snapshot_from_direct_media(snapshot)
        self.assertEqual(converted["mediaStates"][0]["currentTime"], 12)


if __name__ == "__main__":
    unittest.main()
