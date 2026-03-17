const LMS_HOST = "learning.hanyang.ac.kr";
const TICK_MS = 2000;

const state = {
  busy: false,
  panelMounted: false,
  lastStep: "",
  lastDetail: "",
};

const now = () => Date.now();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const getStore = (keys) => chrome.storage.local.get(keys);
const send = (action, payload = {}) => chrome.runtime.sendMessage({ action, ...payload });

const log = (...args) => console.log("[HanyangAuto]", ...args);

const ensureDebugPanel = () => {
  if (state.panelMounted) return;
  const panel = document.createElement("div");
  panel.id = "hanyang-auto-debug-panel";
  panel.style.cssText = [
    "position:fixed",
    "top:12px",
    "right:12px",
    "z-index:2147483647",
    "width:360px",
    "max-height:65vh",
    "overflow:auto",
    "background:#0b1020",
    "color:#dbeafe",
    "border:1px solid #3b82f6",
    "border-radius:8px",
    "padding:10px",
    "font-size:12px",
    "font-family:ui-monospace, SFMono-Regular, Menlo, monospace",
    "line-height:1.45",
    "box-shadow:0 8px 24px rgba(0,0,0,.35)",
  ].join(";");
  panel.innerHTML = "<div>HanyangAuto Debug Initializing...</div>";
  document.documentElement.appendChild(panel);
  state.panelMounted = true;
};

const renderDebugPanel = (data) => {
  ensureDebugPanel();
  const panel = document.getElementById("hanyang-auto-debug-panel");
  if (!panel) return;

  const lectureLines = (data.detectedLectures || [])
    .map((lec, idx) => {
      const status = lec.completed ? "완료" : "미완료";
      return `${idx + 1}. [${status}] ${lec.title || "(제목없음)"}`;
    })
    .join("\n");

  panel.innerHTML = [
    "<div style='font-weight:700;color:#93c5fd;margin-bottom:6px'>HanyangAuto Debug</div>",
    `<div>Step: ${data.step || "-"}</div>`,
    `<div>Detail: ${data.detail || "-"}</div>`,
    `<div>Frame: ${window === window.top ? "top" : "iframe"}</div>`,
    `<div>URL: ${location.href}</div>`,
    `<div>CourseQueue: ${(data.courseQueue || []).join(", ") || "-"}</div>`,
    `<div>LearnedCount: ${data.learnedCount ?? 0}</div>`,
    `<div>CurrentLecture: ${data.currentLectureUrl || "-"}</div>`,
    `<div style='margin-top:8px;font-weight:700;color:#bfdbfe'>Detected Lectures</div>`,
    `<pre style='white-space:pre-wrap;margin:4px 0 0'>${lectureLines || "-"}</pre>`,
    `<div style='margin-top:8px;color:#93c5fd'>Updated: ${new Date().toLocaleTimeString()}</div>`,
  ].join("");
};

const reportDebug = async (step, detail, extra = {}) => {
  state.lastStep = step;
  state.lastDetail = detail || "";
  const store = await getStore(["courseQueue", "learnedLectures", "currentLectureUrl"]);
  const payload = {
    step,
    detail,
    url: location.href,
    frame: window === window.top ? "top" : "iframe",
    courseQueue: store.courseQueue || [],
    learnedCount: (store.learnedLectures || []).length,
    currentLectureUrl: store.currentLectureUrl || "",
    ...extra,
  };
  renderDebugPanel(payload);
  await send("REPORT_DEBUG_STATE", { debugState: payload }).catch(() => {});
};

const safeClick = (el) => {
  if (!el) return false;
  el.scrollIntoView({ block: "center", behavior: "auto" });
  el.click();
  return true;
};

const oncePer = (key, ms) => {
  const cacheKey = `hya:${key}`;
  const last = Number(sessionStorage.getItem(cacheKey) || "0");
  if (now() - last < ms) return false;
  sessionStorage.setItem(cacheKey, String(now()));
  return true;
};

const parseCourseIdsFromDashboard = () => {
  const cards = document.querySelectorAll("#DashboardCard_Container > div > div");
  const ids = [];
  cards.forEach((card) => {
    const href = card.querySelector("a")?.getAttribute("href") || "";
    const match = href.match(/\/courses\/(\d+)/);
    if (match?.[1]) ids.push(match[1]);
  });
  return [...new Set(ids)];
};

const parseCoursesFromEnv = () => {
  try {
    const list = window.ENV?.STUDENT_PLANNER_COURSES || [];
    if (!Array.isArray(list) || list.length === 0) return [];
    return list
      .map((c) => {
        const id = String(c.id || (c.href || "").match(/\/courses\/(\d+)/)?.[1] || "");
        const name = c.shortName || c.courseCode || c.originalName || c.longName || "";
        return id ? { id, name } : null;
      })
      .filter(Boolean);
  } catch (e) {
    return [];
  }
};

const fetchCoursesFromDashboardApi = async () => {
  try {
    const res = await fetch("/api/v1/dashboard/dashboard_cards", {
      credentials: "same-origin",
      headers: { Accept: "application/json+canvas-string-ids, application/json" },
    });
    if (!res.ok) return [];
    const cards = await res.json();
    if (!Array.isArray(cards)) return [];
    return cards
      .map((card) => {
        const id = String(card.id || "");
        const name = card.shortName || card.courseCode || card.originalName || "";
        return id ? { id, name } : null;
      })
      .filter(Boolean);
  } catch (e) {
    return [];
  }
};

const detectLoginPage = () => {
  const uid = document.querySelector("#uid");
  const upw = document.querySelector("#upw");
  const loginBtn = document.querySelector("#login_btn");
  const profile = document.querySelector("#global_nav_profile_link");
  return Boolean(uid && upw && loginBtn && !profile);
};

const isDashboardPage = () => {
  if (location.pathname.includes("/dashboard")) return true;
  if (document.querySelector("#DashboardCard_Container")) return true;
  if (document.querySelector("#dashboard.ic-dashboard-app")) return true;
  return false;
};

const handleLoginIfNeeded = async (credentials) => {
  if (!detectLoginPage()) return false;

  const userId = credentials?.userId?.trim();
  const password = credentials?.password || "";
  const autoLogin = Boolean(credentials?.autoLogin);
  if (!autoLogin || !userId || !password) {
    await reportDebug("login_wait", "로그인 페이지 감지 (자동 입력 비활성/정보 없음)");
    return false;
  }
  if (!oncePer("login_attempt", 8000)) return false;

  const uid = document.querySelector("#uid");
  const upw = document.querySelector("#upw");
  const loginBtn = document.querySelector("#login_btn");
  if (!uid || !upw || !loginBtn) return false;

  uid.focus();
  uid.value = userId;
  uid.dispatchEvent(new Event("input", { bubbles: true }));
  upw.focus();
  upw.value = password;
  upw.dispatchEvent(new Event("input", { bubbles: true }));

  safeClick(loginBtn);
  await reportDebug("login_attempt", "로그인 버튼 클릭");
  return true;
};

const getCourseIdFromText = (text) => {
  if (!text) return "";
  return text.match(/\/courses\/(\d+)\/external_tools\/140/)?.[1] || "";
};

const parseLectureRows = (doc) => {
  const rows = doc.querySelectorAll("#root > div > div > div > div:nth-child(2) > div");
  const lectures = [];
  rows.forEach((row) => {
    const linkEl = row.querySelector(
      "div > div.xnmb-module_item-left-wrapper > div > div.xnmb-module_item-meta_data-left-wrapper > div > a"
    );
    const title = linkEl?.textContent?.trim() || "";
    const href = linkEl?.href || "";
    const completedEl = row.querySelector(
      "div > div.xnmb-module_item-right-wrapper > span.xnmb-module_item-completed.completed"
    );
    lectures.push({
      title,
      href,
      completed: Boolean(completedEl),
    });
  });
  return lectures;
};

const clickFirstUnlearnedLecture = async (doc, learnedLectures, sourceLabel) => {
  const lectures = parseLectureRows(doc);
  if (lectures.length === 0) return { status: "none", lectures };

  const target = lectures.find((lec) => lec.href && !lec.completed && !learnedLectures.includes(lec.href));
  if (!target) {
    await reportDebug("course_done_check", `${sourceLabel}: 미수강 강의 없음`, { detectedLectures: lectures });
    return { status: "empty", lectures };
  }

  const linkEl = Array.from(
    doc.querySelectorAll(
      "div > div.xnmb-module_item-left-wrapper > div > div.xnmb-module_item-meta_data-left-wrapper > div > a"
    )
  ).find((a) => a.href === target.href);

  if (safeClick(linkEl)) {
    await reportDebug("lecture_open", `${sourceLabel}: 강의 진입`, { detectedLectures: lectures, nextLectureUrl: target.href });
    return { status: "clicked", lectures, lectureUrl: target.href };
  }

  return { status: "none", lectures };
};

const signalCourseFinishedIfNeeded = async (courseId, lectures = []) => {
  if (courseId && oncePer(`course_finished:${courseId}`, 10000)) {
    await send("COURSE_FINISHED", { courseId });
    await reportDebug("course_finished", `과목 ${courseId} 완료`, { detectedLectures: lectures });
    return true;
  }
  return false;
};

const tryReadLectureRowsFromIframe = async (learnedLectures) => {
  const frame = document.querySelector("#tool_content");
  if (!frame || !frame.contentDocument) return false;

  const result = await clickFirstUnlearnedLecture(frame.contentDocument, learnedLectures, "top->tool_content");
  if (result.status === "clicked") return true;
  if (result.status === "empty") {
    const courseId = getCourseIdFromText(location.href);
    await signalCourseFinishedIfNeeded(courseId, result.lectures);
    return true;
  }
  return false;
};

const lectureCompleteText = (text) => text && text.trim() === "완료";

const handlePdfInFrame = async () => {
  const completeSpan =
    document.querySelector("#root > div > div.xnlail-pdf-component > div.xnbc-progress-info-container > span:nth-child(2)") ||
    document.querySelector("#root > div > div.xnlail-pdf-component > div.xnvc-progress-info-container > span:nth-child(2)");

  if (completeSpan && lectureCompleteText(completeSpan.textContent || "")) {
    if (oncePer("lecture_complete_signal", 10000)) {
      await send("LECTURE_COMPLETED");
      await reportDebug("lecture_completed", "PDF 완료 상태 감지");
    }
    return true;
  }

  const progressButton = document.querySelector(
    "#root > div > div.xnlail-pdf-component > div.xnvc-progress-info-container > button"
  );
  if (progressButton) {
    safeClick(progressButton);
    await reportDebug("pdf_progress_click", "PDF 진행 버튼 클릭");
    return true;
  }
  return false;
};

const handleVideoInFrame = async () => {
  const startBtn = document.querySelector(
    "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div"
  );
  const okBtn = document.querySelector(
    "#confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-ok-btn.confirm-btn"
  );
  const completeSpan = document.querySelector(
    "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > span:nth-child(3)"
  );
  const progressButton = document.querySelector(
    "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > button"
  );

  if (startBtn) {
    safeClick(startBtn);
    await reportDebug("video_start_click", "동영상 시작 버튼 클릭");
    return true;
  }
  if (okBtn) {
    safeClick(okBtn);
    await reportDebug("video_resume_confirm", "이어보기 확인 클릭");
    return true;
  }
  if (completeSpan && lectureCompleteText(completeSpan.textContent || "")) {
    if (oncePer("lecture_complete_signal", 10000)) {
      await send("LECTURE_COMPLETED");
      await reportDebug("lecture_completed", "동영상 완료 상태 감지");
    }
    return true;
  }
  if (progressButton) {
    safeClick(progressButton);
    await reportDebug("video_progress_click", "동영상 진행 버튼 클릭");
    return true;
  }
  return false;
};

const handleFrame = async (store) => {
  if (!store.isRunning) return;
  const learned = store.learnedLectures || [];

  const lectureResult = await clickFirstUnlearnedLecture(document, learned, "iframe");
  if (lectureResult.status === "clicked") return;
  if (lectureResult.status === "empty") {
    const courseId = getCourseIdFromText(location.href) || getCourseIdFromText(document.referrer);
    await signalCourseFinishedIfNeeded(courseId, lectureResult.lectures);
    return;
  }

  const handledPdf = await handlePdfInFrame();
  if (handledPdf) return;
  const handledVideo = await handleVideoInFrame();
  if (handledVideo) return;

  await reportDebug("frame_idle", "강의 목록/플레이어 요소 대기 중");
};

const handleTopFrame = async (store) => {
  if (!store.isRunning || location.hostname !== LMS_HOST) return;

  const didLogin = await handleLoginIfNeeded(store.credentials || {});
  if (didLogin) return;

  if (isDashboardPage()) {
    let courses = parseCoursesFromEnv();
    if (courses.length === 0) {
      const ids = parseCourseIdsFromDashboard();
      courses = ids.map((id) => ({ id, name: "" }));
    }
    if (courses.length === 0) {
      courses = await fetchCoursesFromDashboardApi();
    }
    const courseIds = courses.map((c) => c.id);

    if (courseIds.length > 0 && oncePer("discover_courses", 7000)) {
      await send("COURSES_DISCOVERED", { courses: courseIds });
      await reportDebug("courses_discovered", `대시보드 과목 ${courseIds.length}개`, {
        discoveredCourses: courses,
      });
    } else {
      await reportDebug("dashboard_wait", "대시보드 과목 탐색 중");
    }
    return;
  }

  const plainCourseMatch = location.href.match(/\/courses\/(\d+)\/?$/);
  if (plainCourseMatch?.[1]) {
    const nextUrl = `https://${LMS_HOST}/courses/${plainCourseMatch[1]}/external_tools/140`;
    await reportDebug("redirect_external_tool", `과목 ${plainCourseMatch[1]} 도구 페이지로 이동`);
    location.href = nextUrl;
    return;
  }

  const isToolPage = /\/courses\/\d+\/external_tools\/140/.test(location.href);
  if (isToolPage) {
    const handled = await tryReadLectureRowsFromIframe(store.learnedLectures || []);
    if (!handled) {
      await reportDebug("tool_page_wait", "tool_content iframe 로드 대기");
    }
    return;
  }

  const isLikelyLecturePage =
    !location.pathname.includes("/dashboard") &&
    !location.pathname.includes("/external_tools/140") &&
    !plainCourseMatch;
  if (isLikelyLecturePage) {
    await send("UPDATE_CURRENT_LECTURE_URL", { url: location.href });
    await reportDebug("lecture_page_seen", "강의 상세 페이지 감지");
    return;
  }

  await reportDebug("top_idle", "처리 대상 페이지 대기");
};

const tick = async () => {
  if (state.busy) return;
  state.busy = true;
  try {
    const store = await getStore(["isRunning", "credentials", "learnedLectures"]);
    if (!store.isRunning) return;

    if (window === window.top) {
      await handleTopFrame(store);
    } else {
      await handleFrame(store);
    }
  } catch (err) {
    console.error("[HanyangAuto] tick error", err);
    await sleep(500);
  } finally {
    state.busy = false;
  }
};

setInterval(tick, TICK_MS);
tick();

chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "AUTOMATION_STARTED") {
    tick();
    return;
  }
  if (message.action === "AUTOMATION_STOPPED" || message.action === "AUTOMATION_COMPLETED") {
    sessionStorage.removeItem("hya:login_attempt");
    sessionStorage.removeItem("hya:discover_courses");
  }
});
