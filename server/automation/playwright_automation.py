from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from playwright.sync_api import Dialog, Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from utils.logger import HanyangLogger
from utils.database import update_user_status

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
DEFAULT_DURATION_SEC = 60 * 60
MAX_LECTURE_RUNTIME_SEC = 3 * 60 * 60


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
    logger.info("login", f"dialog: {dialog.message}")
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
    logger.info("login", f"login_submit result: code={code}, url={url or '-'}, msg={msg or '-'}")
    return {
        "status": int(result["status"]),
        "code": code,
        "msg": msg,
        "url": url,
        "payload": payload,
    }


def _parse_duration_seconds(texts: Iterable[str]) -> int:
    joined = " ".join(texts)
    match = re.search(r"(\d+)분\s*(\d+)초", joined)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.search(r"(\d+):(\d{2})", joined)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return DEFAULT_DURATION_SEC


def _get_lecture_availability_state(snapshot: Dict[str, Any]) -> Optional[str]:
    body_text = str(snapshot.get("bodyText") or "")
    status_parts = [str(part or "") for part in snapshot.get("statusParts") or []]
    combined = " ".join(status_parts + [body_text])
    scheduled_markers = [
        "학습이 가능합니다",
        "부터 학습이 가능합니다",
        "학습 예정",
        "오픈 예정",
        "수강 예정",
        "아직 학습할 수 없습니다",
    ]
    if any(marker in combined for marker in scheduled_markers):
        return "scheduled"

    expired_markers = ["학습 기간이 종료되었습니다."]
    if any(marker in combined for marker in expired_markers):
        return "expired"

    return None


def _is_non_required_recording(snapshot: Dict[str, Any], lecture: Optional[LectureItem] = None) -> bool:
    body_text = str(snapshot.get("bodyText") or "")
    status_parts = [str(part or "") for part in snapshot.get("statusParts") or []]
    lecture_title = str(lecture.title if lecture else "")
    combined = " ".join(status_parts + [body_text, lecture_title])
    markers = [
        "강의녹화",
        "녹화",
        "대면",
        "대면 강의",
    ]
    return any(marker in combined for marker in markers)


def _read_attendance_snapshot(frame: Frame) -> Dict[str, Any]:
    return frame.evaluate(
        """() => {
          const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
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
          return {
            statusParts,
            bodyText,
            completed,
            hasRefreshButton: Boolean(refreshButton),
            hasInnerFrame: Boolean(document.querySelector("iframe")),
            hycmsSrc: hycmsFrame?.getAttribute("src") || "",
            nonVideoHints,
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
                const match = normalize(text).match(/(\\d{1,2}):(\\d{2})\\s*\\/\\s*(\\d{1,2}):(\\d{2})/);
                if (!match) return null;
                return {
                  currentSeconds: Number(match[1]) * 60 + Number(match[2]),
                  totalSeconds: Number(match[3]) * 60 + Number(match[4]),
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
            logger.info("playback", "resume prompt accepted")
            time.sleep(1)
            after = _read_hycms_snapshot(page, attendance_frame)
            logger.info("playback", f"snapshot after resume | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
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


def _ensure_playing(page: Page, logger: HanyangLogger) -> bool:
    attendance_frame = _find_attendance_frame(page)
    hycms = _wait_for_hycms_frame(page, attendance_frame, 10_000)
    if not hycms:
        fallback_snapshot = _read_attendance_snapshot(attendance_frame) if attendance_frame else {}
        logger.info("playback", f"hycms frame not found | hycmsSrc={fallback_snapshot.get('hycmsSrc') or '-'}")
        return False

    before = _read_hycms_snapshot(page, attendance_frame)
    logger.info(
        "playback",
        f"snapshot before play | time={before.get('timeText') or '-'} | media={before.get('mediaStates')} | "
        f"front={before.get('frontScreen', {}).get('selector') if isinstance(before.get('frontScreen'), dict) else '-'} | "
        f"play={before.get('playPause', {}).get('selector') if isinstance(before.get('playPause'), dict) else '-'}",
    )

    if _resume_prompt_visible(page, attendance_frame) and _accept_resume_prompt(page, attendance_frame, logger, wait_ms=1_000):
        return True

    for selector in [
        "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div",
        "#front-screen .vc-front-screen-btn-wrapper.video1-btn > div",
        "#front-screen .vc-front-screen-btn-wrapper > div",
        "#front-screen",
    ]:
        if _click_selector(hycms, selector):
            logger.info("playback", f"front-screen selector clicked: {selector}")
            time.sleep(1)
            if _accept_resume_prompt(page, attendance_frame, logger):
                return True
            after = _read_hycms_snapshot(page, attendance_frame)
            logger.info("playback", f"snapshot after front-screen click | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
            return True

    if _click_if_visible(hycms, "재생"):
        logger.info("playback", "play button clicked")
        time.sleep(1)
        after = _read_hycms_snapshot(page, attendance_frame)
        logger.info("playback", f"snapshot after text play click | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
        return True

    for selector in [
        "#play-controller .vc-pctrl-play-pause-btn",
        ".vc-pctrl-play-pause-btn",
        ".player-center-control-wrapper",
        ".player-restart-btn",
        ".vjs-big-play-button",
    ]:
        if _click_selector(hycms, selector):
            logger.info("playback", f"play control selector clicked: {selector}")
            time.sleep(1)
            if _accept_resume_prompt(page, attendance_frame, logger):
                return True
            after = _read_hycms_snapshot(page, attendance_frame)
            logger.info("playback", f"snapshot after control click | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
            return True

    after = _read_hycms_snapshot(page, attendance_frame)
    if any((media.get("currentTime") or 0) > 0 and not media.get("paused", True) for media in after.get("mediaStates") or []):
        logger.info("playback", f"player already progressing | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
        return True

    if _find_button_by_text(hycms, "일시정지").count() > 0:
        logger.info("playback", f"player already running | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
        return True

    logger.info("playback", f"playback start failed | time={after.get('timeText') or '-'} | media={after.get('mediaStates')}")
    return False


def _refresh_status(frame: Frame, logger: HanyangLogger) -> None:
    before = _read_attendance_snapshot(frame)
    button = _find_button_by_text(frame, "학습 상태 확인")
    if button.count() == 0:
        return
    button.click(timeout=5_000)
    time.sleep(POST_REFRESH_WAIT_SEC)
    after = _read_attendance_snapshot(frame)
    logger.info(
        "progress",
        "status refresh clicked | "
        f"before={before['statusParts'] or ['(empty)']} | "
        f"after={after['statusParts'] or ['(empty)']} | "
        f"completed={after['completed']}",
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
        return {"login": False, "msg": submit_result["msg"] or f"로그인 실패 코드: {submit_result['code']}"}

    try:
        page.goto(LMS_ORIGIN, wait_until="domcontentloaded")
    except Exception as exc:
        logger.info("login", f"LMS navigation after login_submit raised: {exc}")

    end_time = time.time() + 20
    while time.time() < end_time:
        current_url = page.url
        if current_url.startswith(LMS_ORIGIN):
            if "oauth/login" not in current_url:
                logger.info("login", f"logged in at {current_url}")
                return {"login": True, "msg": "로그인 성공"}
        time.sleep(1)

    return {"login": False, "msg": f"로그인 후 LMS 이동 실패: {page.url}"}


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
    logger.info("discovery", f"dashboard courses discovered: {len(courses)}")
    return courses


def _discover_lecture_items(page: Page, course_ids: List[Dict[str, str]], logger: HanyangLogger) -> List[LectureItem]:
    lectures: List[LectureItem] = []
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
    logger.info("discovery", f"lecture attendance items discovered: {len(lectures)}")
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
    page.goto(lecture.html_url, wait_until="domcontentloaded")
    attendance_frame = _wait_for_attendance_frame(page)

    initial = _read_attendance_snapshot(attendance_frame)
    availability_state = _get_lecture_availability_state(initial)
    if availability_state == "scheduled":
        logger.info("lecture", f"scheduled lecture skipped: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
        return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
    if availability_state == "expired":
        logger.info("lecture", f"expired lecture skipped: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
        return {"learn": True, "msg": "expired lecture"}
    if _is_non_required_recording(initial, lecture):
        logger.info("lecture", f"non-required recording skipped: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
        return {"learn": True, "msg": "non-required recording"}
    if initial["completed"]:
        logger.info("lecture", f"already completed: {lecture.title}")
        return {"learn": True, "msg": "already completed"}

    # Many already-finished lectures briefly look incomplete until the
    # attendance page synchronizes server state. Try several quick syncs before
    # we even consider starting playback.
    if initial["hasRefreshButton"]:
        for attempt in range(INITIAL_STATUS_SYNC_ATTEMPTS):
            _refresh_status(attendance_frame, logger)
            attendance_frame = _wait_for_attendance_frame(page)
            initial = _read_attendance_snapshot(attendance_frame)
            availability_state = _get_lecture_availability_state(initial)
            if availability_state == "scheduled":
                logger.info("lecture", f"scheduled lecture skipped after sync: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
                return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
            if availability_state == "expired":
                logger.info("lecture", f"expired lecture skipped after sync: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
                return {"learn": True, "msg": "expired lecture"}
            if _is_non_required_recording(initial, lecture):
                logger.info("lecture", f"non-required recording skipped after sync: {lecture.title} | status={initial['statusParts'] or ['(empty)']}")
                return {"learn": True, "msg": "non-required recording"}
            if initial["completed"]:
                logger.info("lecture", f"already completed after sync: {lecture.title}")
                return {"learn": True, "msg": "already completed after sync"}
            if attempt + 1 < INITIAL_STATUS_SYNC_ATTEMPTS:
                time.sleep(INITIAL_STATUS_SYNC_WAIT_SEC)

    duration_sec = min(
        max(_parse_duration_seconds(initial["statusParts"] + [initial["bodyText"]]), 180),
        MAX_LECTURE_RUNTIME_SEC,
    )
    deadline = time.time() + min(int(duration_sec * 1.2) + 180, MAX_LECTURE_RUNTIME_SEC)
    last_refresh = 0.0
    last_media_second: Optional[float] = None

    logger.info("lecture", f"playback started: {lecture.title}")

    while time.time() < deadline:
        attendance_frame = _wait_for_attendance_frame(page)
        snapshot = _read_attendance_snapshot(attendance_frame)
        availability_state = _get_lecture_availability_state(snapshot)
        if availability_state == "scheduled":
            logger.info("lecture", f"scheduled lecture skipped during playback loop: {lecture.title} | status={snapshot['statusParts'] or ['(empty)']}")
            return {"learn": True, "mark_processed": False, "msg": "scheduled lecture"}
        if availability_state == "expired":
            logger.info("lecture", f"expired lecture skipped during playback loop: {lecture.title} | status={snapshot['statusParts'] or ['(empty)']}")
            return {"learn": True, "msg": "expired lecture"}
        if _is_non_required_recording(snapshot, lecture):
            logger.info("lecture", f"non-required recording skipped during playback loop: {lecture.title} | status={snapshot['statusParts'] or ['(empty)']}")
            return {"learn": True, "msg": "non-required recording"}
        if snapshot["completed"]:
            logger.info("lecture", f"completed: {lecture.title}")
            return {"learn": True, "msg": "completed"}

        if snapshot["hasInnerFrame"]:
            _ensure_playing(page, logger)
            media_snapshot = _read_hycms_snapshot(page, attendance_frame)
            media_times = [float(media.get("currentTime") or 0) for media in media_snapshot.get("mediaStates") or []]
            current_media_second = max(media_times) if media_times else None
            if current_media_second is not None:
                if last_media_second is not None and current_media_second > last_media_second + 0.5:
                    logger.info(
                        "playback",
                        f"playback progressing | lecture={lecture.title} | second={current_media_second:.1f} | time={media_snapshot.get('timeText') or '-'}",
                    )
                elif last_media_second is not None and current_media_second <= last_media_second + 0.1:
                    logger.info(
                        "playback",
                        f"playback stalled | lecture={lecture.title} | second={current_media_second:.1f} | time={media_snapshot.get('timeText') or '-'} | media={media_snapshot.get('mediaStates')}",
                    )
                else:
                    logger.info(
                        "playback",
                        f"playback initial media state | lecture={lecture.title} | second={current_media_second:.1f} | time={media_snapshot.get('timeText') or '-'} | media={media_snapshot.get('mediaStates')}",
                    )
                last_media_second = current_media_second
        elif snapshot["nonVideoHints"]:
            logger.info("lecture", f"non-video item treated as processed: {lecture.title}")
            return {"learn": True, "msg": "non-video attendance item"}

        if time.time() - last_refresh >= STATUS_REFRESH_INTERVAL_SEC and snapshot["hasRefreshButton"]:
            _refresh_status(attendance_frame, logger)
            last_refresh = time.time()

        time.sleep(STATUS_POLL_INTERVAL_SEC)

    attendance_frame = _wait_for_attendance_frame(page)
    if _read_attendance_snapshot(attendance_frame)["completed"]:
        return {"learn": True, "msg": "completed after final refresh"}
    return {"learn": False, "msg": f"timeout waiting for completion: {lecture.title}"}


def run_user_automation(user_id: str, pwd: str, learned_lectures: List[str], db_add_learned) -> Dict[str, Any]:
    user_logger = HanyangLogger("user", user_id=str(user_id))
    learned_set = {value for item in learned_lectures for value in ([item] if item else [])}
    learned: List[str] = []

    try:
        update_user_status(user_id, "active")
    except Exception as exc:
        user_logger.error("automation", f"status update failed: {exc}")

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
        page.on("dialog", lambda dialog: _handle_dialog(user_logger, dialog))

        login_result = _login(page, user_id, pwd, user_logger)
        if not login_result.get("login"):
            update_user_status(user_id, "error")
            return {"success": False, "msg": login_result.get("msg", "로그인 실패"), "learned": []}

        courses = _discover_courses(page, user_logger)
        if not courses:
            update_user_status(user_id, "completed")
            return {"success": True, "msg": "과목 없음", "learned": []}

        lectures = _discover_lecture_items(page, courses, user_logger)
        pending = [lecture for lecture in lectures if not _is_learned(lecture, learned_set)]
        user_logger.info("automation", f"pending lectures: {len(pending)}")

        for lecture in pending:
            result = _play_until_complete(page, lecture, user_logger)
            if not result.get("learn"):
                update_user_status(user_id, "error")
                return {
                    "success": False,
                    "msg": f"강의 처리 실패: {lecture.title} ({result.get('msg', '')})",
                    "learned": learned,
                }
            if result.get("mark_processed", True):
                _mark_processed(lecture, learned, learned_set, db_add_learned, user_id)

        update_user_status(user_id, "completed")
        return {"success": True, "msg": f"{len(learned)}개 강의 처리 완료", "learned": learned}
    except Exception as exc:
        user_logger.error("automation", f"playwright automation error: {exc}")
        try:
            update_user_status(user_id, "error")
        except Exception as status_exc:
            user_logger.error("automation", f"status update failed: {status_exc}")
        return {"success": False, "msg": f"자동화 오류: {exc}", "learned": learned}
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
        logger.error("verification", f"login verification failed: {exc}")
        return {"success": False, "message": f"계정 확인 중 오류가 발생했습니다: {exc}"}
    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
