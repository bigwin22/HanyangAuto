from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from playwright.sync_api import Dialog, Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from utils.logger import HanyangLogger
from utils.database import update_user_status
from utils.security import mask_sensitive_text, mask_sensitive_url

LMS_ORIGIN = "https://learning.hanyang.ac.kr"
OAUTH_HOST = "https://api.hanyang.ac.kr/oauth/login"
DASHBOARD_API = "/api/v1/dashboard/dashboard_cards"
MODULES_API = "/api/v1/courses/{course_id}/modules?include[]=items&per_page=100"

DISCOVERY_TIMEOUT_MS = 20_000
LECTURE_LOAD_TIMEOUT_MS = 30_000
FRAME_URL_WAIT_TIMEOUT_MS = 20_000
STATUS_POLL_INTERVAL_SEC = 5
STATUS_REFRESH_INTERVAL_SEC = 45
POST_REFRESH_WAIT_SEC = 3
INITIAL_STATUS_SYNC_ATTEMPTS = 4
INITIAL_STATUS_SYNC_WAIT_SEC = 1
PLAYBACK_VERIFY_WAIT_MS = 3_000
PLAYBACK_VERIFY_POLL_SEC = 0.5
DEFAULT_DURATION_SEC = 60 * 60
MAX_LECTURE_RUNTIME_SEC = 3 * 60 * 60
NO_PLAYER_SKIP_THRESHOLD_SEC = 90


@dataclass(frozen=True)
class LectureItem:
    course_id: str
    module_name: str
    item_id: str
    title: str
    html_url: str
    external_url: str
    content_id: Optional[str]

    @property
    def key(self) -> str:
        return self.html_url

    @property
    def aliases(self) -> Set[str]:
        aliases = {self.html_url, self.external_url, self.item_id}
        aliases.update(_strip_query(value) for value in list(aliases) if value)
        return {value for value in aliases if value}


def _lecture_log_fields(lecture: Optional[LectureItem]) -> Dict[str, Any]:
    if not lecture:
        return {}
    return {
        "course_id": lecture.course_id,
        "module_name": lecture.module_name,
        "item_id": lecture.item_id,
        "lecture_title": lecture.title,
        "content_id": lecture.content_id or "-",
    }


def _status_summary(snapshot: Dict[str, Any]) -> str:
    parts = [str(part or "").strip() for part in snapshot.get("statusParts") or [] if str(part or "").strip()]
    return " / ".join(parts) if parts else "-"


def _is_static_pending_without_player(snapshot: Dict[str, Any]) -> bool:
    parts = [str(part or "").strip() for part in snapshot.get("statusParts") or [] if str(part or "").strip()]
    if snapshot.get("hasInnerFrame"):
        return False
    if snapshot.get("hycmsSrc"):
        return False
    if snapshot.get("hasDirectMedia"):
        return False
    if snapshot.get("completed"):
        return False
    if "미완료" not in parts:
        return False
    return True


def _snapshot_from_direct_media(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    direct_media = snapshot.get("directMediaStates") or []
    return {
        "mediaStates": direct_media,
        "timing": {},
        "timeText": "-",
        "playerClass": "",
        "playPauseClass": "",
    }


def _log_lecture_event(
    logger: HanyangLogger,
    event: str,
    lecture: Optional[LectureItem] = None,
    message: Optional[str] = None,
    **fields: Any,
) -> None:
    payload = _lecture_log_fields(lecture)
    payload.update(fields)
    logger.event("lecture", event, message or event, **payload)


def _log_playback_event(
    logger: HanyangLogger,
    event: str,
    lecture: Optional[LectureItem] = None,
    message: Optional[str] = None,
    **fields: Any,
) -> None:
    payload = _lecture_log_fields(lecture)
    payload.update(fields)
    logger.event("playback", event, message or event, **payload)


def _strip_query(url: str) -> str:
    return url.split("?", 1)[0]


def _absolute_lms_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{LMS_ORIGIN}{url}"
    return f"{LMS_ORIGIN}/{url}"


def _is_completed_lecture_item(item: Dict[str, Any]) -> bool:
    completion_requirement = item.get("completion_requirement") or {}
    alt_completion_requirement = item.get("completionRequirement") or {}
    module_completion_requirement = item.get("module_item_completion_requirement") or {}

    candidates = [
        completion_requirement.get("completed"),
        completion_requirement.get("fulfilled"),
        alt_completion_requirement.get("completed"),
        alt_completion_requirement.get("fulfilled"),
        module_completion_requirement.get("completed"),
        module_completion_requirement.get("fulfilled"),
    ]
    if any(value is True for value in candidates):
        return True

    text_candidates = [
        item.get("completion_status"),
        item.get("completionState"),
        completion_requirement.get("status"),
        module_completion_requirement.get("status"),
    ]
    normalized = {str(value or "").strip().lower() for value in text_candidates if str(value or "").strip()}
    return bool(normalized & {"completed", "complete", "done", "passed"})


def _parse_canvas_json(text: str) -> Any:
    cleaned = re.sub(r"^while\(1\);", "", text)
    try:
        import json

        return json.loads(cleaned)
    except Exception:
        return cleaned


def _fetch_json(page: Page, url: str) -> Any:
    result = page.evaluate(
        """async (targetUrl) => {
          const response = await fetch(targetUrl, { credentials: "include" });
          return { status: response.status, text: await response.text() };
        }""",
        url,
    )
    if int(result["status"]) >= 400:
        raise RuntimeError(f"HTTP {result['status']} for {url}")
    return _parse_canvas_json(result["text"])


def _handle_dialog(logger: HanyangLogger, dialog: Dialog) -> None:
    logger.info("login", f"dialog: {mask_sensitive_text(dialog.message)}")
    dialog.accept()


def _find_button_by_text(frame: Frame, text: str):
    return frame.locator("button").filter(has_text=text).first


def _submit_login_form(page: Page, user_id: str, password: str, logger: HanyangLogger) -> Dict[str, Any]:
    page.goto(OAUTH_HOST, wait_until="domcontentloaded")
    page.wait_for_selector("#uid", timeout=DISCOVERY_TIMEOUT_MS)
    page.fill("#uid", user_id)
    page.fill("#upw", password)
    page.wait_for_function("typeof fnRSAEnc === 'function' && !!_public_key && !!_public_key_nm", timeout=DISCOVERY_TIMEOUT_MS)

    result = page.evaluate(
        """async ({ userId, password }) => {
          const body = new URLSearchParams({
            _userId: fnRSAEnc(userId),
            _password: fnRSAEnc(password),
            identck: _public_key_nm,
            sinbun: "",
          });
          const response = await fetch("/oauth/login_submit.json", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" },
            body: body.toString(),
          });
          return { status: response.status, payload: await response.json() };
        }""",
        {"userId": user_id, "password": password},
    )

    payload = result["payload"]
    code = str(payload.get("code") or "")
    msg = str(payload.get("msg") or "")
    url = str(payload.get("url") or "")
    logger.event(
        "login",
        "login_submit_result",
        "login_submit result",
        code=code,
        response_url=mask_sensitive_url(url) or "-",
        response_message=mask_sensitive_text(msg) or "-",
    )
    return {
        "status": int(result["status"]),
        "code": code,
        "msg": msg,
        "url": url,
        "payload": payload,
    }


def _parse_duration_seconds(texts: Iterable[str]) -> int:
    joined = " ".join(texts)
    match = re.search(r"(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*/\s*(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})", joined)
    if match:
        return _parse_clock_seconds(match.group(2)) or DEFAULT_DURATION_SEC
    match = re.search(r"(\d{1,2}:\d{2}:\d{2})", joined)
    if match:
        return _parse_clock_seconds(match.group(1)) or DEFAULT_DURATION_SEC
    match = re.search(r"(\d+)분\s*(\d+)초", joined)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.search(r"(\d+):(\d{2})", joined)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return DEFAULT_DURATION_SEC


def _parse_clock_seconds(value: str) -> Optional[int]:
    parts = [segment for segment in str(value or "").strip().split(":") if segment]
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return None


def _resolve_expected_duration_seconds(texts: Iterable[str], player_snapshot: Optional[Dict[str, Any]] = None) -> int:
    player_total = int(_snapshot_total_duration(player_snapshot or {}))
    if player_total > 0:
        return max(player_total, 180)
    return max(_parse_duration_seconds(texts), 180)


def _maybe_extend_deadline(
    deadline: float,
    logger: HanyangLogger,
    lecture: LectureItem,
    snapshot: Dict[str, Any],
    current_media_second: Optional[float],
) -> float:
    total_duration = _snapshot_total_duration(snapshot)
    if total_duration <= 0 or current_media_second is None:
        return deadline
    remaining_sec = max(total_duration - current_media_second, 0)
    candidate_deadline = time.time() + min(int(remaining_sec * 1.2) + 180, MAX_LECTURE_RUNTIME_SEC)
    if candidate_deadline > deadline + 30:
        extended_by = int(candidate_deadline - deadline)
        _log_lecture_event(
            logger,
            "lecture_deadline_extended",
            lecture,
            "deadline extended from active playback",
            remaining_sec=int(remaining_sec),
            total_duration_sec=int(total_duration),
            current_second=int(current_media_second),
            extended_by_sec=extended_by,
        )
        return candidate_deadline
    return deadline


def _normalize_snapshot_texts(snapshot: Dict[str, Any]) -> Dict[str, str]:
    status_parts = [str(part or "").strip() for part in snapshot.get("statusParts") or [] if str(part or "").strip()]
    body_text = str(snapshot.get("bodyText") or "").strip()
    return {
        "status": " ".join(status_parts),
        "body": body_text,
        "status_parts": status_parts,
    }


def _get_lecture_availability_state(snapshot: Dict[str, Any]) -> Optional[str]:
    return _get_lecture_availability_reason(snapshot)[0]


def _get_lecture_availability_reason(snapshot: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    normalized = _normalize_snapshot_texts(snapshot)
    status_text = normalized["status"]
    body_text = normalized["body"]
    scheduled_markers = [
        "학습이 가능합니다",
        "부터 학습이 가능합니다",
        "학습 예정",
        "오픈 예정",
        "수강 예정",
        "아직 학습할 수 없습니다",
    ]
    for marker in scheduled_markers:
        if marker in status_text:
            return ("scheduled", "statusParts", marker)

    expired_markers = ["학습 기간이 종료되었습니다."]
    for marker in expired_markers:
        if marker in status_text:
            return ("expired", "statusParts", marker)

    if not normalized["status_parts"]:
        for marker in scheduled_markers:
            if marker in body_text:
                return ("scheduled", "bodyText", marker)
        for marker in expired_markers:
            if marker in body_text:
                return ("expired", "bodyText", marker)

    return (None, None, None)


def _is_non_required_recording(snapshot: Dict[str, Any], lecture: Optional[LectureItem] = None) -> bool:
    return _get_non_required_recording_reason(snapshot, lecture)[0]


def _get_non_required_recording_reason(snapshot: Dict[str, Any], lecture: Optional[LectureItem] = None) -> tuple[bool, Optional[str]]:
    normalized = _normalize_snapshot_texts(snapshot)
    status_text = normalized["status"]
    body_text = normalized["body"]
    lecture_title = str(lecture.title if lecture else "").strip()
    combined = " ".join([status_text, body_text, lecture_title]).strip()
    if "출결 대상 아님" not in combined:
        return (False, None)
    markers = [
        "강의녹화",
        "녹화",
        "대면",
        "대면 강의",
    ]
    for marker in markers:
        if marker in combined:
            return (True, marker)
    return (False, None)


def _snapshot_max_media_second(snapshot: Dict[str, Any]) -> Optional[float]:
    media_times = [float(media.get("currentTime") or 0) for media in snapshot.get("mediaStates") or []]
    return max(media_times) if media_times else None


def _snapshot_total_duration(snapshot: Dict[str, Any]) -> float:
    timing = snapshot.get("timing") or {}
    total = float(timing.get("totalSeconds") or 0)
    if total > 0:
        return total
    durations = [float(media.get("duration") or 0) for media in snapshot.get("mediaStates") or []]
    return max(durations) if durations else 0.0


def _snapshot_has_running_media(snapshot: Dict[str, Any]) -> bool:
    for media in snapshot.get("mediaStates") or []:
        if media.get("ended"):
            continue
        if not media.get("paused", True):
            return True
    return False


def _snapshot_has_ended_media(snapshot: Dict[str, Any]) -> bool:
    return any(bool(media.get("ended")) for media in snapshot.get("mediaStates") or [])


def _snapshot_looks_playing(snapshot: Dict[str, Any]) -> bool:
    if _snapshot_has_running_media(snapshot):
        return True
    player_class = str(snapshot.get("playerClass") or "")
    play_pause_class = str(snapshot.get("playPauseClass") or "")
    looks_playing = any(token in player_class for token in ("vjs-playing",))
    looks_playing = looks_playing or any(token in play_pause_class for token in ("vc-pctrl-on-play", "vc-pctrl-on-playing"))
    looks_paused = any(token in player_class for token in ("vjs-paused",))
    looks_paused = looks_paused or "vc-pctrl-on-pause" in play_pause_class
    return looks_playing and not looks_paused


def _playback_was_near_completion(snapshot: Dict[str, Any], media_second: Optional[float] = None) -> bool:
    current = media_second if media_second is not None else _snapshot_max_media_second(snapshot)
    total = _snapshot_total_duration(snapshot)
    return total > 0 and current is not None and current >= max(total - 15, total * 0.95)


def _classify_playback_transition(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    before_second = _snapshot_max_media_second(before)
    after_second = _snapshot_max_media_second(after)
    if _snapshot_looks_playing(after):
        if before_second is not None and after_second is not None and after_second > before_second + 0.5:
            return "progressing"
        return "running"
    if before_second is not None and after_second is not None:
        if after_second > before_second + 0.5:
            return "progressing"
        if after_second + 30 < before_second and _playback_was_near_completion(before, before_second):
            return "restarted_after_end"
    if _snapshot_has_ended_media(after) and _playback_was_near_completion(before, before_second):
        return "ended_near_completion"
    return "stalled"


def _read_attendance_snapshot(frame: Frame) -> Dict[str, Any]:
    return frame.evaluate(
        """() => {
          const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
          const queryVisible = (selectors) => {
            for (const selector of selectors) {
              const element = document.querySelector(selector);
              if (!element) continue;
              const rect = element.getBoundingClientRect();
              if (rect.width > 0 && rect.height > 0) return { selector, text: normalize(element.textContent) };
            }
            return null;
          };
          const refreshButton = Array.from(document.querySelectorAll("button"))
            .find((button) => normalize(button.textContent) === "학습 상태 확인");
          const parent = refreshButton?.parentElement || null;
          const statusParts = parent
            ? Array.from(parent.children)
                .map((node) => normalize(node.textContent))
                .filter(Boolean)
                .filter((text) => text !== "학습 상태 확인")
            : [];
          const bodyText = normalize(document.body?.innerText || "");
          const completed = statusParts.includes("완료") || bodyText.includes("학습 진행 상태: 완료");
          const nonVideoHints = ["교안", "pdf", "파일"].some((token) => bodyText.toLowerCase().includes(token));
          const hycmsFrame = document.querySelector('iframe[src*="hycms.hanyang.ac.kr"]');
          const directMediaStates = Array.from(document.querySelectorAll("video, audio")).map((media, index) => ({
            index,
            paused: !!media.paused,
            ended: !!media.ended,
            muted: !!media.muted,
            currentTime: Number(media.currentTime || 0),
            duration: Number(media.duration || 0),
            readyState: Number(media.readyState || 0),
            tag: media.tagName,
          }));
          return {
            statusParts,
            bodyText,
            completed,
            hasRefreshButton: Boolean(refreshButton),
            hasInnerFrame: Boolean(document.querySelector("iframe")),
            hycmsSrc: hycmsFrame?.getAttribute("src") || "",
            nonVideoHints,
            hasDirectMedia: directMediaStates.length > 0,
            directMediaStates,
            directPlayControl: queryVisible([
              "button[aria-label*='재생']",
              "button[title*='재생']",
              ".vjs-big-play-button",
              ".vjs-play-control",
              "video",
              "audio",
            ]),
          };
        }"""
    )


def _find_attendance_frame(page: Page) -> Optional[Frame]:
    return page.frame(name="tool_content")


def _find_hycms_frame(page: Page) -> Optional[Frame]:
    for frame in page.frames:
        if "hycms.hanyang.ac.kr" in frame.url:
            return frame
    return None


def _decode_html_url(url: str) -> str:
    return (
        url.replace("&amp;", "&")
        .replace("&#38;", "&")
        .replace("&quot;", '"')
        .replace("&#34;", '"')
    )


def _wait_for_hycms_frame(page: Page, attendance_frame: Optional[Frame], timeout_ms: int) -> Optional[Frame]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        frame = _find_hycms_frame(page)
        if frame:
            return frame
        if attendance_frame:
            try:
                snapshot = _read_attendance_snapshot(attendance_frame)
                hycms_src = _decode_html_url(snapshot.get("hycmsSrc") or "")
                if hycms_src:
                    page.wait_for_timeout(500)
            except Exception:
                pass
        time.sleep(0.5)
    return _find_hycms_frame(page)


def _wait_for_frame_url(page: Page, finder: Callable[[Page], Optional[Frame]], predicate: Callable[[str], bool], timeout_ms: int) -> Optional[Frame]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        frame = finder(page)
        if frame and predicate(frame.url or ""):
            return frame
        time.sleep(0.5)
    return finder(page)


def _read_hycms_snapshot(page: Page, attendance_frame: Optional[Frame] = None) -> Dict[str, Any]:
    hycms = _wait_for_hycms_frame(page, attendance_frame, 5_000)
    if not hycms:
        return {"available": False}
    try:
        return hycms.evaluate(
            """() => {
              const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
              const parseTime = (text) => {
                const parseClock = (value) => {
                  const parts = normalize(value).split(":").map((part) => Number(part));
                  if (parts.some((part) => Number.isNaN(part))) return null;
                  if (parts.length === 2) return parts[0] * 60 + parts[1];
                  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
                  return null;
                };
                const match = normalize(text).match(/((?:\\d{1,2}:)?\\d{1,2}:\\d{2})\\s*\\/\\s*((?:\\d{1,2}:)?\\d{1,2}:\\d{2})/);
                if (!match) return null;
                const currentSeconds = parseClock(match[1]);
                const totalSeconds = parseClock(match[2]);
                if (currentSeconds === null || totalSeconds === null) return null;
                return {
                  currentSeconds,
                  totalSeconds,
                };
              };
              const queryVisible = (selectors) => {
                for (const selector of selectors) {
                  const element = document.querySelector(selector);
                  if (!element) continue;
                  const rect = element.getBoundingClientRect();
                  if (rect.width > 0 && rect.height > 0) return { selector, text: normalize(element.textContent), rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } };
                }
                return null;
              };

              const timeText = normalize(document.querySelector(".vc-pctrl-play-time-text-area")?.textContent);
              return {
                available: true,
                url: location.href,
                title: document.title,
                timeText,
                timing: parseTime(timeText),
                frontScreen: queryVisible([
                  "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div",
                  "#front-screen .vc-front-screen-btn-wrapper.video1-btn > div",
                  "#front-screen .vc-front-screen-btn-wrapper > div",
                  "#front-screen",
                ]),
                playPause: queryVisible([
                  "#play-controller .vc-pctrl-play-pause-btn",
                  ".vc-pctrl-play-pause-btn",
                  ".player-center-control-wrapper",
                  ".player-restart-btn",
                  ".vjs-big-play-button",
                ]),
                playPauseClass: document.querySelector(".vc-pctrl-play-pause-btn")?.className || "",
                playerClass: document.querySelector("#svp-video, #vp1-video1, #vp4-video1, .video-js")?.className || "",
                mediaStates: Array.from(document.querySelectorAll("video, audio")).map((media, index) => ({
                  index,
                  paused: !!media.paused,
                  ended: !!media.ended,
                  muted: !!media.muted,
                  currentTime: Number(media.currentTime || 0),
                  duration: Number(media.duration || 0),
                  readyState: Number(media.readyState || 0),
                })),
              };
            }"""
        )
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def _click_selector(frame: Frame, selector: str) -> bool:
    locator = frame.locator(selector).first
    if locator.count() == 0:
        return False
    try:
        locator.click(timeout=2_000, force=True)
        return True
    except PlaywrightTimeoutError:
        return False
    except Exception:
        return False


def _click_if_visible(frame: Frame, text: str) -> bool:
    locator = _find_button_by_text(frame, text)
    if locator.count() == 0:
        return False
    try:
        locator.click(timeout=2_000)
        return True
    except PlaywrightTimeoutError:
        return False


def _click_resume_prompt(frame: Frame) -> bool:
    try:
        return bool(
            frame.evaluate(
                r'''() => {
                  const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                  const preferred = document.querySelector('.confirm-ok-btn.confirm-btn');
                  if (preferred) {
                    const rect = preferred.getBoundingClientRect();
                    const style = window.getComputedStyle(preferred);
                    if (rect.width === 0 || rect.height === 0) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    ['mousedown', 'mouseup', 'click'].forEach((type) => {
                      preferred.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true }));
                    });
                    if (typeof preferred.click === 'function') preferred.click();
                    return true;
                  }
                  const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div, span'));
                  const target = candidates.find((element) => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    if (rect.width === 0 || rect.height === 0) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    const text = normalize(element.textContent);
                    const title = normalize(element.getAttribute('title'));
                    return text === '예' || title === '예' || text.includes('이어') || title.includes('이어');
                  });
                  if (!target) return false;
                  ['mousedown', 'mouseup', 'click'].forEach((type) => {
                    target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true }));
                  });
                  if (typeof target.click === 'function') target.click();
                  return true;
                }'''
            )
        )
    except Exception:
        return False


def _accept_resume_prompt(page: Page, attendance_frame: Optional[Frame], logger: HanyangLogger, wait_ms: int = 6_000) -> bool:
    deadline = time.time() + (wait_ms / 1000)
    while time.time() < deadline:
        hycms = _wait_for_hycms_frame(page, attendance_frame, 1_000)
        if hycms and (_click_if_visible(hycms, "예") or _click_resume_prompt(hycms)):
            logger.event("playback", "resume_prompt_accepted", "resume prompt accepted")
            time.sleep(1)
            after = _read_hycms_snapshot(page, attendance_frame)
            logger.event(
                "playback",
                "playback_snapshot_after_resume",
                "snapshot after resume",
                player_time=after.get("timeText") or "-",
                media=after.get("mediaStates"),
            )
            return True
        time.sleep(0.5)
    return False


def _resume_prompt_visible(page: Page, attendance_frame: Optional[Frame]) -> bool:
    hycms = _wait_for_hycms_frame(page, attendance_frame, 1_000)
    if not hycms:
        return False
    try:
        return bool(
            hycms.evaluate(
                """() => {
                  const dialog = document.querySelector('#confirm-dialog, .confirm-dialog-wrapper, .confirm-msg-box');
                  if (!dialog) return false;
                  const rect = dialog.getBoundingClientRect();
                  const style = window.getComputedStyle(dialog);
                  return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                }"""
            )
        )
    except Exception:
        return False


def _invoke_media_play(frame: Frame) -> bool:
    try:
        return bool(
            frame.evaluate(
                """() => {
                  const mediaList = Array.from(document.querySelectorAll("video, audio"));
                  let invoked = false;
                  for (const media of mediaList) {
                    if (!media) continue;
                    try {
                      const result = media.play?.();
                      if (result && typeof result.catch === "function") result.catch(() => {});
                      invoked = true;
                    } catch (error) {
                      // ignore and keep trying other media elements
                    }
                  }
                  return invoked;
                }"""
            )
        )
    except Exception:
        return False


def _invoke_attendance_media_play(frame: Frame) -> bool:
    try:
        return bool(
            frame.evaluate(
                """() => {
                  const mediaList = Array.from(document.querySelectorAll("video, audio"));
                  let invoked = false;
                  for (const media of mediaList) {
                    try {
                      const result = media.play?.();
                      if (result && typeof result.catch === "function") result.catch(() => {});
                      invoked = true;
                    } catch (error) {
                      // continue
                    }
                  }
                  if (invoked) return true;
                  const clickable = Array.from(document.querySelectorAll("button, [role='button'], .vjs-big-play-button, .vjs-play-control"));
                  for (const element of clickable) {
                    const text = (element.textContent || "").replace(/\\s+/g, " ").trim();
                    const title = (element.getAttribute("title") || "").replace(/\\s+/g, " ").trim();
                    const aria = (element.getAttribute("aria-label") || "").replace(/\\s+/g, " ").trim();
                    if (![text, title, aria].some((value) => value.includes("재생") || value.toLowerCase().includes("play"))) continue;
                    if (typeof element.click === "function") {
                      element.click();
                      return true;
                    }
                  }
                  return false;
                }"""
            )
        )
    except Exception:
        return False


def _wait_for_playback_confirmation(
    page: Page,
    attendance_frame: Optional[Frame],
    logger: HanyangLogger,
    stage: str,
    baseline: Dict[str, Any],
    wait_ms: int = PLAYBACK_VERIFY_WAIT_MS,
) -> tuple[bool, Dict[str, Any], str]:
    deadline = time.time() + (wait_ms / 1000)
    last_snapshot = baseline
    while time.time() < deadline:
        time.sleep(PLAYBACK_VERIFY_POLL_SEC)
        last_snapshot = _read_hycms_snapshot(page, attendance_frame)
        transition = _classify_playback_transition(baseline, last_snapshot)
        if transition in {"progressing", "running", "restarted_after_end", "ended_near_completion"}:
            logger.event(
                "playback",
                "playback_confirmed",
                f"playback confirmed after {stage}",
                stage=stage,
                transition=transition,
                player_time=last_snapshot.get("timeText") or "-",
                media=last_snapshot.get("mediaStates"),
            )
            return (True, last_snapshot, transition)
    failure_reason = f"{stage}_still_{_classify_playback_transition(baseline, last_snapshot)}"
    logger.event(
        "playback",
        "playback_not_confirmed",
        "playback attempt did not progress",
        stage=stage,
        reason=failure_reason,
        player_time=last_snapshot.get("timeText") or "-",
        media=last_snapshot.get("mediaStates"),
    )
    return (False, last_snapshot, failure_reason)


def _ensure_playing(page: Page, logger: HanyangLogger) -> bool:
    attendance_frame = _find_attendance_frame(page)
    hycms = _wait_for_hycms_frame(page, attendance_frame, 10_000)
    if not hycms:
        fallback_snapshot = _read_attendance_snapshot(attendance_frame) if attendance_frame else {}
        logger.event("playback", "hycms_frame_missing", "hycms frame not found", hycms_src=fallback_snapshot.get("hycmsSrc") or "-")
        return False

    before = _read_hycms_snapshot(page, attendance_frame)
    logger.event(
        "playback",
        "playback_snapshot_before",
        "snapshot before play",
        player_time=before.get("timeText") or "-",
        media=before.get("mediaStates"),
        front_selector=before.get("frontScreen", {}).get("selector") if isinstance(before.get("frontScreen"), dict) else "-",
        play_selector=before.get("playPause", {}).get("selector") if isinstance(before.get("playPause"), dict) else "-",
    )

    if _classify_playback_transition(before, before) in {"progressing", "running"}:
        logger.event("playback", "playback_already_running", "player already progressing", player_time=before.get("timeText") or "-", media=before.get("mediaStates"))
        return True

    last_snapshot = before
    last_reason = "no_attempt_made"

    if _resume_prompt_visible(page, attendance_frame) and _accept_resume_prompt(page, attendance_frame, logger, wait_ms=1_000):
        ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, "resume_accepted", before)
        if ok:
            return True
        hycms = _wait_for_hycms_frame(page, attendance_frame, 3_000) or hycms

    for selector in [
        "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div",
        "#front-screen .vc-front-screen-btn-wrapper.video1-btn > div",
        "#front-screen .vc-front-screen-btn-wrapper > div",
        "#front-screen",
    ]:
        if _click_selector(hycms, selector):
            logger.event("playback", "playback_action", "front-screen selector clicked", action="front_click", selector=selector)
            ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, f"front_clicked:{selector}", last_snapshot)
            if ok:
                return True
            if _accept_resume_prompt(page, attendance_frame, logger, wait_ms=1_500):
                ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, "resume_after_front_click", last_snapshot)
                if ok:
                    return True
            hycms = _wait_for_hycms_frame(page, attendance_frame, 3_000) or hycms

    if _click_if_visible(hycms, "재생"):
        logger.event("playback", "playback_action", "play button clicked", action="text_play_click")
        ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, "text_play_clicked", last_snapshot)
        if ok:
            return True
        hycms = _wait_for_hycms_frame(page, attendance_frame, 3_000) or hycms

    for selector in [
        "#play-controller .vc-pctrl-play-pause-btn",
        ".vc-pctrl-play-pause-btn",
        ".player-center-control-wrapper",
        ".player-restart-btn",
        ".vjs-big-play-button",
    ]:
        if _click_selector(hycms, selector):
            logger.event("playback", "playback_action", "play control selector clicked", action="play_control_click", selector=selector)
            ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, f"play_control_clicked:{selector}", last_snapshot)
            if ok:
                return True
            if _accept_resume_prompt(page, attendance_frame, logger, wait_ms=1_500):
                ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, "resume_after_control_click", last_snapshot)
                if ok:
                    return True
            hycms = _wait_for_hycms_frame(page, attendance_frame, 3_000) or hycms

    if _invoke_media_play(hycms):
        logger.event("playback", "playback_action", "media play invoked via js", action="js_play")
        ok, last_snapshot, last_reason = _wait_for_playback_confirmation(page, attendance_frame, logger, "js_play_invoked", last_snapshot)
        if ok:
            return True

    if _find_button_by_text(hycms, "일시정지").count() > 0:
        after = _read_hycms_snapshot(page, attendance_frame)
        logger.event("playback", "playback_running_after_check", "player already running", player_time=after.get("timeText") or "-", media=after.get("mediaStates"))
        return True

    logger.event(
        "playback",
        "playback_start_failed",
        "playback start failed",
        reason=last_reason,
        player_time=last_snapshot.get("timeText") or "-",
        media=last_snapshot.get("mediaStates"),
    )
    return False


def _refresh_status(frame: Frame, logger: HanyangLogger) -> None:
    before = _read_attendance_snapshot(frame)
    button = _find_button_by_text(frame, "학습 상태 확인")
    if button.count() == 0:
        return
    button.click(timeout=5_000)
    time.sleep(POST_REFRESH_WAIT_SEC)
    after = _read_attendance_snapshot(frame)
    logger.event(
        "progress",
        "status_refresh",
        "status refresh clicked",
        before=before["statusParts"] or ["(empty)"],
        after=after["statusParts"] or ["(empty)"],
        before_summary=_status_summary(before),
        after_summary=_status_summary(after),
        completed=after["completed"],
    )


def _wait_for_attendance_frame(page: Page) -> Frame:
    page.wait_for_selector('iframe[name="tool_content"]', timeout=LECTURE_LOAD_TIMEOUT_MS)
    frame = _wait_for_frame_url(
        page,
        _find_attendance_frame,
        lambda url: bool(url) and url != "about:blank" and "learningx" in url,
        FRAME_URL_WAIT_TIMEOUT_MS,
    )
    if not frame:
        raise RuntimeError("tool_content frame not found")
    frame.wait_for_load_state("domcontentloaded", timeout=LECTURE_LOAD_TIMEOUT_MS)
    return frame


def _login(page: Page, user_id: str, password: str, logger: HanyangLogger) -> Dict[str, Any]:
    submit_result = _submit_login_form(page, user_id, password, logger)
    if submit_result["code"] not in {"200", "504"}:
        logger.event("login", "login_failed", "login failed", code=submit_result["code"], reason=submit_result["msg"] or "-")
        return {"login": False, "msg": submit_result["msg"] or f"로그인 실패 코드: {submit_result['code']}"}

    try:
        page.goto(LMS_ORIGIN, wait_until="domcontentloaded")
    except Exception as exc:
        logger.info("login", f"LMS navigation after login_submit raised: {mask_sensitive_text(exc)}")

    end_time = time.time() + 20
    while time.time() < end_time:
        current_url = page.url
        if current_url.startswith(LMS_ORIGIN):
            if "oauth/login" not in current_url:
                logger.event("login", "login_succeeded", "logged in", current_url=mask_sensitive_url(current_url))
                return {"login": True, "msg": "로그인 성공"}
        time.sleep(1)

    logger.event("login", "login_navigation_failed", "로그인 후 LMS 이동 실패", current_url=mask_sensitive_url(page.url))
    return {"login": False, "msg": f"로그인 후 LMS 이동 실패: {mask_sensitive_url(page.url)}"}


def _discover_courses(page: Page, logger: HanyangLogger) -> List[Dict[str, str]]:
    cards = _fetch_json(page, DASHBOARD_API)
    courses: List[Dict[str, str]] = []
    for card in cards if isinstance(cards, list) else []:
        course_id = str(card.get("id") or "")
        if not course_id:
            continue
        courses.append(
            {
                "id": course_id,
                "name": card.get("shortName")
                or card.get("courseCode")
                or card.get("originalName")
                or card.get("longName")
                or "",
            }
        )
    logger.event("discovery", "courses_discovered", "dashboard courses discovered", count=len(courses))
    return courses


def _discover_lecture_items(page: Page, course_ids: List[Dict[str, str]], logger: HanyangLogger) -> List[LectureItem]:
    lectures: List[LectureItem] = []
    skipped_completed = 0
    for course in course_ids:
        payload = _fetch_json(page, MODULES_API.format(course_id=course["id"]))
        if not isinstance(payload, list):
            continue
        for module in payload:
            module_name = str(module.get("name") or "")
            for item in module.get("items") or []:
                content_id = str(item.get("content_id") or "")
                external_url = str(item.get("external_url") or "")
                if item.get("type") != "ExternalTool":
                    continue
                if content_id != "138" and "/learningx/lti/lecture_attendance/items/view/" not in external_url:
                    continue
                html_url = _absolute_lms_url(str(item.get("html_url") or ""))
                if not html_url:
                    continue
                if _is_completed_lecture_item(item):
                    skipped_completed += 1
                    continue
                lectures.append(
                    LectureItem(
                        course_id=course["id"],
                        module_name=module_name,
                        item_id=str(item.get("id") or ""),
                        title=str(item.get("title") or ""),
                        html_url=html_url,
                        external_url=_absolute_lms_url(external_url),
                        content_id=content_id or None,
                    )
                )
    logger.event(
        "discovery",
        "lecture_items_discovered",
        "lecture attendance items discovered",
        count=len(lectures),
        skipped_completed=skipped_completed,
    )
    return lectures


def _is_learned(lecture: LectureItem, learned_lectures: Set[str]) -> bool:
    return any(alias in learned_lectures for alias in lecture.aliases)


def _mark_processed(
    lecture: LectureItem,
    learned: List[str],
    learned_set: Set[str],
    db_add_learned: Callable[[str, str], None],
    user_id: str,
) -> None:
    if lecture.key not in learned_set:
        learned.append(lecture.key)
        learned_set.add(lecture.key)
        db_add_learned(user_id, lecture.key)


def _play_until_complete(page: Page, lecture: LectureItem, logger: HanyangLogger) -> Dict[str, Any]:
    lecture_started_at = time.time()
    page.goto(lecture.html_url, wait_until="domcontentloaded")
    attendance_frame = _wait_for_attendance_frame(page)

    initial = _read_attendance_snapshot(attendance_frame)
    _log_lecture_event(
        logger,
        "lecture_opened",
        lecture,
        "lecture opened",
        attendance_status=_status_summary(initial),
        has_refresh_button=initial.get("hasRefreshButton"),
        has_inner_frame=initial.get("hasInnerFrame"),
    )
    availability_state, availability_source, availability_marker = _get_lecture_availability_reason(initial)
    non_required, non_required_marker = _get_non_required_recording_reason(initial, lecture)
    if availability_state == "scheduled":
        _log_lecture_event(
            logger,
            "lecture_skipped",
            lecture,
            "scheduled lecture skipped",
            outcome="scheduled",
            attendance_status=initial["statusParts"] or ["(empty)"],
            source=availability_source or "-",
            marker=availability_marker or "-",
        )
        return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
    if availability_state == "expired":
        _log_lecture_event(
            logger,
            "lecture_skipped",
            lecture,
            "expired lecture skipped",
            outcome="expired",
            attendance_status=initial["statusParts"] or ["(empty)"],
            source=availability_source or "-",
            marker=availability_marker or "-",
        )
        return {"learn": True, "msg": "expired lecture"}
    if non_required:
        _log_lecture_event(
            logger,
            "lecture_skipped",
            lecture,
            "non-required recording skipped",
            outcome="non_required_recording",
            attendance_status=initial["statusParts"] or ["(empty)"],
            marker=non_required_marker or "-",
        )
        return {"learn": True, "msg": "non-required recording"}
    if initial["completed"]:
        _log_lecture_event(logger, "lecture_already_completed", lecture, "already completed", outcome="already_completed")
        return {"learn": True, "msg": "already completed"}

    # Many already-finished lectures briefly look incomplete until the
    # attendance page synchronizes server state. Try several quick syncs before
    # we even consider starting playback.
    if initial["hasRefreshButton"]:
        for attempt in range(INITIAL_STATUS_SYNC_ATTEMPTS):
            _refresh_status(attendance_frame, logger)
            attendance_frame = _wait_for_attendance_frame(page)
            initial = _read_attendance_snapshot(attendance_frame)
            availability_state, availability_source, availability_marker = _get_lecture_availability_reason(initial)
            non_required, non_required_marker = _get_non_required_recording_reason(initial, lecture)
            if availability_state == "scheduled":
                _log_lecture_event(
                    logger,
                    "lecture_skipped",
                    lecture,
                    "scheduled lecture skipped after sync",
                    outcome="scheduled",
                    phase="initial_sync",
                    attendance_status=initial["statusParts"] or ["(empty)"],
                    source=availability_source or "-",
                    marker=availability_marker or "-",
                )
                return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
            if availability_state == "expired":
                _log_lecture_event(
                    logger,
                    "lecture_skipped",
                    lecture,
                    "expired lecture skipped after sync",
                    outcome="expired",
                    phase="initial_sync",
                    attendance_status=initial["statusParts"] or ["(empty)"],
                    source=availability_source or "-",
                    marker=availability_marker or "-",
                )
                return {"learn": True, "msg": "expired lecture"}
            if non_required:
                _log_lecture_event(
                    logger,
                    "lecture_skipped",
                    lecture,
                    "non-required recording skipped after sync",
                    outcome="non_required_recording",
                    phase="initial_sync",
                    attendance_status=initial["statusParts"] or ["(empty)"],
                    marker=non_required_marker or "-",
                )
                return {"learn": True, "msg": "non-required recording"}
            if initial["completed"]:
                _log_lecture_event(logger, "lecture_already_completed", lecture, "already completed after sync", outcome="already_completed", phase="initial_sync")
                return {"learn": True, "msg": "already completed after sync"}
            if attempt + 1 < INITIAL_STATUS_SYNC_ATTEMPTS:
                time.sleep(INITIAL_STATUS_SYNC_WAIT_SEC)

    duration_snapshot: Optional[Dict[str, Any]] = None
    if initial.get("hasInnerFrame") or initial.get("hycmsSrc"):
        duration_snapshot = _read_hycms_snapshot(page, attendance_frame)
    elif initial.get("hasDirectMedia"):
        duration_snapshot = _snapshot_from_direct_media(initial)

    duration_sec = min(
        _resolve_expected_duration_seconds(initial["statusParts"] + [initial["bodyText"]], duration_snapshot),
        MAX_LECTURE_RUNTIME_SEC,
    )
    deadline = time.time() + min(int(duration_sec * 1.2) + 180, MAX_LECTURE_RUNTIME_SEC)
    last_refresh = 0.0
    last_media_second: Optional[float] = None
    last_media_snapshot: Optional[Dict[str, Any]] = None
    no_player_started_at: Optional[float] = None

    _log_lecture_event(
        logger,
        "lecture_playback_started",
        lecture,
        "playback started",
        expected_duration_sec=duration_sec,
        deadline_sec=max(int(deadline - time.time()), 0),
    )

    while time.time() < deadline:
        attendance_frame = _wait_for_attendance_frame(page)
        snapshot = _read_attendance_snapshot(attendance_frame)
        availability_state, availability_source, availability_marker = _get_lecture_availability_reason(snapshot)
        non_required, non_required_marker = _get_non_required_recording_reason(snapshot, lecture)
        if availability_state == "scheduled":
            _log_lecture_event(
                logger,
                "lecture_skipped",
                lecture,
                "scheduled lecture skipped during playback loop",
                outcome="scheduled",
                phase="playback_loop",
                attendance_status=snapshot["statusParts"] or ["(empty)"],
                source=availability_source or "-",
                marker=availability_marker or "-",
            )
            return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
        if availability_state == "expired":
            _log_lecture_event(
                logger,
                "lecture_skipped",
                lecture,
                "expired lecture skipped during playback loop",
                outcome="expired",
                phase="playback_loop",
                attendance_status=snapshot["statusParts"] or ["(empty)"],
                source=availability_source or "-",
                marker=availability_marker or "-",
            )
            return {"learn": True, "msg": "expired lecture"}
        if non_required:
            _log_lecture_event(
                logger,
                "lecture_skipped",
                lecture,
                "non-required recording skipped during playback loop",
                outcome="non_required_recording",
                phase="playback_loop",
                attendance_status=snapshot["statusParts"] or ["(empty)"],
                marker=non_required_marker or "-",
            )
            return {"learn": True, "msg": "non-required recording"}
        if snapshot["completed"]:
            _log_lecture_event(
                logger,
                "lecture_completed",
                lecture,
                "completed",
                elapsed_sec=int(time.time() - lecture_started_at),
                attendance_status=snapshot["statusParts"] or ["(empty)"],
            )
            return {"learn": True, "msg": "completed"}

        if _is_static_pending_without_player(snapshot):
            if no_player_started_at is None:
                no_player_started_at = time.time()
                _log_lecture_event(
                    logger,
                    "lecture_no_player_detected",
                    lecture,
                    "playable media not detected yet",
                    attendance_status=snapshot["statusParts"] or ["(empty)"],
                    no_player_elapsed_sec=0,
                )
            elif time.time() - no_player_started_at >= NO_PLAYER_SKIP_THRESHOLD_SEC:
                _log_lecture_event(
                    logger,
                    "lecture_skipped",
                    lecture,
                    "no playable media detected; skipped",
                    outcome="non_playable_attendance_item",
                    attendance_status=snapshot["statusParts"] or ["(empty)"],
                    no_player_elapsed_sec=int(time.time() - no_player_started_at),
                )
                return {"learn": True, "msg": "non-playable attendance item"}
        else:
            no_player_started_at = None

        if snapshot["hasInnerFrame"]:
            _ensure_playing(page, logger)
            media_snapshot = _read_hycms_snapshot(page, attendance_frame)
            current_media_second = _snapshot_max_media_second(media_snapshot)
            if current_media_second is not None:
                if last_media_second is not None and current_media_second > last_media_second + 0.5:
                    _log_playback_event(
                        logger,
                        "playback_progressing",
                        lecture,
                        "playback progressing",
                        second=round(current_media_second, 1),
                        player_time=media_snapshot.get("timeText") or "-",
                    )
                elif (
                    last_media_second is not None
                    and current_media_second + 30 < last_media_second
                    and last_media_snapshot
                    and _playback_was_near_completion(last_media_snapshot, last_media_second)
                ):
                    _log_playback_event(
                        logger,
                        "playback_restarted_after_end",
                        lecture,
                        "playback restarted after end",
                        second=round(current_media_second, 1),
                        player_time=media_snapshot.get("timeText") or "-",
                        media=media_snapshot.get("mediaStates"),
                    )
                elif last_media_second is not None and current_media_second <= last_media_second + 0.1:
                    _log_playback_event(
                        logger,
                        "playback_stalled",
                        lecture,
                        "playback stalled",
                        second=round(current_media_second, 1),
                        player_time=media_snapshot.get("timeText") or "-",
                        media=media_snapshot.get("mediaStates"),
                    )
                else:
                    _log_playback_event(
                        logger,
                        "playback_initial_state",
                        lecture,
                        "playback initial media state",
                        second=round(current_media_second, 1),
                        player_time=media_snapshot.get("timeText") or "-",
                        media=media_snapshot.get("mediaStates"),
                    )
                deadline = _maybe_extend_deadline(deadline, logger, lecture, media_snapshot, current_media_second)
                last_media_second = current_media_second
                last_media_snapshot = media_snapshot
        elif snapshot.get("hasDirectMedia"):
            if _invoke_attendance_media_play(attendance_frame):
                _log_playback_event(
                    logger,
                    "attendance_media_play_invoked",
                    lecture,
                    "attendance frame media play invoked",
                    media=snapshot.get("directMediaStates"),
                )
            media_snapshot = _snapshot_from_direct_media(_read_attendance_snapshot(attendance_frame))
            current_media_second = _snapshot_max_media_second(media_snapshot)
            if current_media_second is not None:
                if last_media_second is not None and current_media_second > last_media_second + 0.5:
                    _log_playback_event(
                        logger,
                        "playback_progressing",
                        lecture,
                        "direct media playback progressing",
                        second=round(current_media_second, 1),
                        player_time="-",
                        media=media_snapshot.get("mediaStates"),
                    )
                elif last_media_second is not None and current_media_second <= last_media_second + 0.1:
                    _log_playback_event(
                        logger,
                        "playback_stalled",
                        lecture,
                        "direct media playback stalled",
                        second=round(current_media_second, 1),
                        player_time="-",
                        media=media_snapshot.get("mediaStates"),
                    )
                else:
                    _log_playback_event(
                        logger,
                        "playback_initial_state",
                        lecture,
                        "direct media initial state",
                        second=round(current_media_second, 1),
                        player_time="-",
                        media=media_snapshot.get("mediaStates"),
                    )
                deadline = _maybe_extend_deadline(deadline, logger, lecture, media_snapshot, current_media_second)
                last_media_second = current_media_second
                last_media_snapshot = media_snapshot
        elif snapshot["nonVideoHints"]:
            _log_lecture_event(logger, "lecture_non_video_processed", lecture, "non-video item treated as processed", outcome="non_video_item")
            return {"learn": True, "msg": "non-video attendance item"}

        if time.time() - last_refresh >= STATUS_REFRESH_INTERVAL_SEC and snapshot["hasRefreshButton"]:
            _refresh_status(attendance_frame, logger)
            last_refresh = time.time()

        time.sleep(STATUS_POLL_INTERVAL_SEC)

    attendance_frame = _wait_for_attendance_frame(page)
    if _read_attendance_snapshot(attendance_frame)["completed"]:
        _log_lecture_event(
            logger,
            "lecture_completed",
            lecture,
            "completed after final refresh",
            elapsed_sec=int(time.time() - lecture_started_at),
            phase="final_refresh",
        )
        return {"learn": True, "msg": "completed after final refresh"}
    _log_lecture_event(
        logger,
        "lecture_timeout",
        lecture,
        "timeout waiting for completion",
        elapsed_sec=int(time.time() - lecture_started_at),
    )
    return {"learn": False, "msg": f"timeout waiting for completion: {lecture.title}"}


def run_user_automation(user_id: str, pwd: str, learned_lectures: List[str], db_add_learned, run_id: Optional[str] = None) -> Dict[str, Any]:
    resolved_run_id = run_id or HanyangLogger.new_run_id("automation")
    user_logger = HanyangLogger("user", user_id=str(user_id), default_fields={"run_id": resolved_run_id})
    learned_set = {value for item in learned_lectures for value in ([item] if item else [])}
    learned: List[str] = []
    run_started_at = time.time()

    try:
        update_user_status(user_id, "active")
    except Exception as exc:
        user_logger.error("automation", f"status update failed: {exc}")

    browser = None
    playwright = None

    try:
        user_logger.event(
            "automation",
            "automation_run_started",
            "automation run started",
            previously_learned=len(learned_lectures),
        )
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false",
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.on("dialog", lambda dialog: _handle_dialog(user_logger, dialog))

        login_result = _login(page, user_id, pwd, user_logger)
        if not login_result.get("login"):
            update_user_status(user_id, "error")
            user_logger.event(
                "automation",
                "automation_run_failed",
                "automation run failed during login",
                outcome="login_failed",
                elapsed_sec=int(time.time() - run_started_at),
                reason=login_result.get("msg", "로그인 실패"),
                level="ERROR",
            )
            return {"success": False, "msg": login_result.get("msg", "로그인 실패"), "learned": []}

        courses = _discover_courses(page, user_logger)
        if not courses:
            update_user_status(user_id, "completed")
            user_logger.event(
                "automation",
                "automation_run_completed",
                "automation run completed with no courses",
                outcome="no_courses",
                elapsed_sec=int(time.time() - run_started_at),
            )
            return {"success": True, "msg": "과목 없음", "learned": []}

        lectures = _discover_lecture_items(page, courses, user_logger)
        pending = [lecture for lecture in lectures if not _is_learned(lecture, learned_set)]
        user_logger.event(
            "automation",
            "automation_pending_lectures",
            "pending lectures discovered",
            total_courses=len(courses),
            total_lectures=len(lectures),
            pending_lectures=len(pending),
            previously_learned_filtered=len(lectures) - len(pending),
        )

        for lecture in pending:
            result = _play_until_complete(page, lecture, user_logger)
            if not result.get("learn"):
                update_user_status(user_id, "error")
                _log_lecture_event(
                    user_logger,
                    "lecture_failed",
                    lecture,
                    "lecture processing failed",
                    outcome="failed",
                    failure_message=result.get("msg", ""),
                )
                user_logger.event(
                    "automation",
                    "automation_run_failed",
                    "automation run failed",
                    outcome="lecture_failed",
                    failed_lecture=lecture.title,
                    elapsed_sec=int(time.time() - run_started_at),
                    learned_count=len(learned),
                    level="ERROR",
                )
                return {
                    "success": False,
                    "msg": f"강의 처리 실패: {lecture.title} ({result.get('msg', '')})",
                    "learned": learned,
                }
            if result.get("mark_processed", True):
                _mark_processed(lecture, learned, learned_set, db_add_learned, user_id)

        update_user_status(user_id, "completed")
        user_logger.event(
            "automation",
            "automation_run_completed",
            "automation run completed",
            outcome="completed",
            elapsed_sec=int(time.time() - run_started_at),
            learned_count=len(learned),
            pending_lectures=len(pending),
        )
        return {"success": True, "msg": f"{len(learned)}개 강의 처리 완료", "learned": learned}
    except Exception as exc:
        user_logger.error("automation", f"playwright automation error: {mask_sensitive_text(exc)}")
        try:
            update_user_status(user_id, "error")
        except Exception as status_exc:
            user_logger.error("automation", f"status update failed: {mask_sensitive_text(status_exc)}")
        user_logger.event(
            "automation",
            "automation_run_failed",
            "automation run raised exception",
            outcome="exception",
            elapsed_sec=int(time.time() - run_started_at),
            reason=mask_sensitive_text(exc),
            level="ERROR",
        )
        return {"success": False, "msg": "자동화 오류가 발생했습니다.", "learned": learned}
    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()


def verify_user_login(user_id: str, pwd: str) -> Dict[str, Any]:
    logger = HanyangLogger("user", user_id=str(user_id))
    browser = None
    playwright = None

    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false",
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.on("dialog", lambda dialog: _handle_dialog(logger, dialog))
        submit_result = _submit_login_form(page, user_id, pwd, logger)
        if submit_result["code"] in {"200", "504"}:
            return {"success": True, "message": "한양 LMS 로그인 확인 완료"}
        return {
            "success": False,
            "message": submit_result["msg"] or "아이디 또는 비밀번호가 올바르지 않습니다.",
            "code": submit_result["code"],
        }
    except Exception as exc:
        logger.error("verification", f"login verification failed: {mask_sensitive_text(exc)}")
        return {"success": False, "message": "계정 확인 중 오류가 발생했습니다."}
    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
