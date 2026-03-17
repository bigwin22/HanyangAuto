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
          return {
            statusParts,
            bodyText,
            completed,
            hasRefreshButton: Boolean(refreshButton),
            hasInnerFrame: Boolean(document.querySelector("iframe")),
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


def _click_if_visible(frame: Frame, text: str) -> bool:
    locator = _find_button_by_text(frame, text)
    if locator.count() == 0:
        return False
    try:
        locator.click(timeout=2_000)
        return True
    except PlaywrightTimeoutError:
        return False


def _ensure_playing(page: Page, logger: HanyangLogger) -> bool:
    hycms = _find_hycms_frame(page)
    if not hycms:
        return False

    if _click_if_visible(hycms, "예"):
        logger.info("playback", "resume prompt accepted")
        return True

    if _click_if_visible(hycms, "재생"):
        logger.info("playback", "play button clicked")
        return True

    if _find_button_by_text(hycms, "일시정지").count() > 0:
        logger.info("playback", "player already running")
        return True

    return False


def _refresh_status(frame: Frame, logger: HanyangLogger) -> None:
    button = _find_button_by_text(frame, "학습 상태 확인")
    if button.count() == 0:
        return
    button.click(timeout=5_000)
    logger.info("progress", "status refresh clicked")
    time.sleep(POST_REFRESH_WAIT_SEC)


def _wait_for_attendance_frame(page: Page) -> Frame:
    page.wait_for_selector('iframe[name="tool_content"]', timeout=LECTURE_LOAD_TIMEOUT_MS)
    frame = _find_attendance_frame(page)
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

    logger.info("lecture", f"playback started: {lecture.title}")

    while time.time() < deadline:
        attendance_frame = _wait_for_attendance_frame(page)
        snapshot = _read_attendance_snapshot(attendance_frame)
        if snapshot["completed"]:
            logger.info("lecture", f"completed: {lecture.title}")
            return {"learn": True, "msg": "completed"}

        if snapshot["hasInnerFrame"]:
            _ensure_playing(page, logger)
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
