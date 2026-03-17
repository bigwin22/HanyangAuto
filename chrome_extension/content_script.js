const LMS_HOST = "learning.hanyang.ac.kr";
const HYCMS_HOST = "hycms.hanyang.ac.kr";
const TICK_MS = 2500;
const STATUS_REFRESH_MS = 45000;

const state = {
  busy: false,
  panelMounted: false,
  debugPanelEnabled: false,
};

const getStore = (keys) => chrome.storage.local.get(keys);
const send = (action, payload = {}) => chrome.runtime.sendMessage({ action, ...payload });

const normalizeText = (value) => (value || "").replace(/\s+/g, " ").trim();
const toAbsoluteLmsUrl = (value) => {
  if (!value) return "";
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  return new URL(value, `${location.protocol}//${LMS_HOST}`).toString();
};

const ensureDebugPanel = () => {
  if (!state.debugPanelEnabled || state.panelMounted || window !== window.top) return;
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

const removeDebugPanel = () => {
  const panel = document.getElementById("hanyang-auto-debug-panel");
  if (panel) panel.remove();
  state.panelMounted = false;
};

const syncDebugPanelEnabled = async () => {
  const store = await getStore(["showDebugPanel"]);
  state.debugPanelEnabled = Boolean(store.showDebugPanel);
  if (!state.debugPanelEnabled) {
    removeDebugPanel();
  }
};

const renderDebugPanel = (data) => {
  if (!state.debugPanelEnabled) {
    removeDebugPanel();
    return;
  }
  ensureDebugPanel();
  const panel = document.getElementById("hanyang-auto-debug-panel");
  if (!panel) return;

  panel.innerHTML = [
    "<div style='font-weight:700;color:#93c5fd;margin-bottom:6px'>HanyangAuto Debug</div>",
    `<div>Step: ${data.step || "-"}</div>`,
    `<div>Detail: ${data.detail || "-"}</div>`,
    `<div>Frame: ${data.frame || "-"}</div>`,
    `<div>URL: ${data.url || "-"}</div>`,
    `<div>RemainingLectures: ${data.remainingLectures ?? "-"}</div>`,
    `<div>LearnedCount: ${data.learnedCount ?? "-"}</div>`,
    `<div>CurrentLecture: ${data.currentLectureUrl || "-"}</div>`,
    `<div style='margin-top:8px;color:#93c5fd'>Updated: ${new Date().toLocaleTimeString()}</div>`,
  ].join("");
};

const reportDebug = async (step, detail, extra = {}) => {
  const store = await getStore(["lectureQueue", "learnedLectures", "currentLectureUrl"]);
  const payload = {
    step,
    detail,
    url: location.href,
    frame: window === window.top ? "top" : "iframe",
    remainingLectures: (store.lectureQueue || []).length,
    learnedCount: (store.learnedLectures || []).length,
    currentLectureUrl: store.currentLectureUrl || "",
    ...extra,
  };
  renderDebugPanel(payload);
  await send("REPORT_DEBUG_STATE", { debugState: payload }).catch(() => {});
};

const reportFrameMetric = async (kind, rect) => {
  if (!rect) return;
  await send("REPORT_FRAME_METRIC", { kind, rect }).catch(() => {});
};

const oncePer = (key, ms) => {
  const cacheKey = `hya:${key}`;
  const last = Number(sessionStorage.getItem(cacheKey) || "0");
  if (Date.now() - last < ms) return false;
  sessionStorage.setItem(cacheKey, String(Date.now()));
  return true;
};

const safeClick = (element) => {
  if (!element) return false;
  element.scrollIntoView({ block: "center", behavior: "auto" });
  element.click();
  return true;
};

const rawClick = (element) => {
  if (!element) return false;
  element.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
  element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
  element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  if (typeof element.click === "function") {
    element.click();
  }
  return true;
};

const queryVisible = (selectors) => {
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (!element) continue;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (style.display === "none" || style.visibility === "hidden") continue;
    if (rect.width === 0 || rect.height === 0) continue;
    return element;
  }
  return null;
};

const parseCanvasJson = (text) => {
  const cleaned = text.replace(/^while\(1\);/, "");
  return JSON.parse(cleaned);
};

const fetchJson = async (url) => {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json+canvas-string-ids, application/json" },
  });
  if (!response.ok) throw new Error(`${url} => ${response.status}`);
  const text = await response.text();
  return parseCanvasJson(text);
};

const fetchCoursesFromDashboardApi = async () => {
  const cards = await fetchJson("/api/v1/dashboard/dashboard_cards");
  if (!Array.isArray(cards)) return [];
  return cards
    .map((card) => ({
      id: String(card.id || ""),
      name: card.shortName || card.courseCode || card.originalName || card.longName || "",
    }))
    .filter((course) => course.id);
};

const fetchLectureItemsForCourse = async (courseId) => {
  const modules = await fetchJson(`/api/v1/courses/${courseId}/modules?include[]=items&per_page=100`);
  if (!Array.isArray(modules)) return [];
  const lectures = [];
  for (const module of modules) {
    for (const item of module.items || []) {
      const contentId = String(item.content_id || "");
      const externalUrl = item.external_url || "";
      if (item.type !== "ExternalTool") continue;
      if (contentId !== "138" && !externalUrl.includes("/learningx/lti/lecture_attendance/items/view/")) continue;
      if (!item.html_url) continue;
      lectures.push({
        courseId,
        moduleName: module.name || "",
        title: item.title || "",
        url: toAbsoluteLmsUrl(item.html_url),
        externalUrl: toAbsoluteLmsUrl(externalUrl),
        itemId: String(item.id || ""),
      });
    }
  }
  return lectures;
};

const discoverLectures = async () => {
  const courses = await fetchCoursesFromDashboardApi();
  const lectures = [];
  for (const course of courses) {
    const items = await fetchLectureItemsForCourse(course.id);
    lectures.push(...items);
  }
  return lectures;
};

const isDashboardPage = () =>
  location.hostname === LMS_HOST &&
  (location.pathname === "/" ||
    location.pathname.includes("/dashboard") ||
    Boolean(document.querySelector("#DashboardCard_Container")));

const isLecturePage = () => /\/courses\/\d+\/modules\/items\/\d+/.test(location.pathname);

const isLoginPage = () => Boolean(document.querySelector("#uid") && document.querySelector("#login_btn"));

const handleTopFrame = async (store) => {
  if (location.hostname !== LMS_HOST) return;

  if (isLoginPage()) {
    await reportDebug("login_required", "로그인된 LMS 탭에서 시작해야 합니다.");
    return;
  }

  const lectureQueue = store.lectureQueue || [];
  const current = lectureQueue[0];

  if (isDashboardPage() && lectureQueue.length === 0) {
    if (!oncePer("discover_lectures", 10000)) {
      await reportDebug("discover_wait", "강의 목록 수집 대기");
      return;
    }

    try {
      const lectures = await discoverLectures();
      if (lectures.length === 0) {
        await reportDebug("discover_empty", "수강 가능한 동영상 강의를 찾지 못했습니다.");
        return;
      }
      await send("LECTURES_DISCOVERED", { lectures });
      await reportDebug("lectures_discovered", `강의 ${lectures.length}개 수집`);
    } catch (error) {
      await reportDebug("discover_error", `강의 목록 수집 실패: ${error.message}`);
    }
    return;
  }

  if (!current) {
    await reportDebug("idle", "대기 중");
    return;
  }

  await send("UPDATE_CURRENT_LECTURE_URL", { url: current.url }).catch(() => {});

  const toolFrame = document.querySelector('iframe[name="tool_content"]')?.getBoundingClientRect();
  if (toolFrame) {
    await reportFrameMetric("toolFrameRect", {
      x: toolFrame.x,
      y: toolFrame.y,
      width: toolFrame.width,
      height: toolFrame.height,
    });
  }

  if (location.href !== current.url && (isDashboardPage() || !isLecturePage())) {
    await reportDebug("navigate_next", `다음 강의로 이동: ${current.title || current.url}`);
    location.href = current.url;
    return;
  }

  if (isLecturePage()) {
    if (oncePer(`lecture_page:${current.url}`, 15000)) {
      await reportDebug("lecture_page", `강의 페이지 확인: ${current.title || current.url}`);
    }
    return;
  }
};

const getAttendanceSnapshot = () => {
  const refreshButton = Array.from(document.querySelectorAll("button")).find(
    (button) => normalizeText(button.textContent) === "학습 상태 확인"
  );
  const parent = refreshButton?.parentElement || null;
  const statusParts = parent
    ? Array.from(parent.children)
        .map((node) => normalizeText(node.textContent))
        .filter(Boolean)
        .filter((text) => text !== "학습 상태 확인")
    : [];
  const completed = statusParts.includes("완료");
  const bodyText = normalizeText(document.body.innerText || "");
  const nonVideo = !document.querySelector("iframe") && /교안|pdf|파일/i.test(bodyText);

  return {
    refreshButton,
    statusParts,
    completed,
    nonVideo,
    bodyText,
  };
};

const isScheduledLecture = (snapshot) => {
  const combined = [...(snapshot.statusParts || []), snapshot.bodyText || ""].join(" ");
  return [
    "학습이 가능합니다",
    "부터 학습이 가능합니다",
    "학습 예정",
    "오픈 예정",
    "수강 예정",
    "아직 학습할 수 없습니다",
  ].some((marker) => combined.includes(marker));
};

const isNonRequiredRecording = (snapshot) => {
  const title = normalizeText(document.title || "");
  const combined = [...(snapshot.statusParts || []), snapshot.bodyText || "", title].join(" ");
  return ["강의녹화", "녹화", "대면", "대면 강의"].some((marker) => combined.includes(marker));
};

const handleAttendanceFrame = async () => {
  const hycmsFrame = document.querySelector("iframe")?.getBoundingClientRect();
  if (hycmsFrame) {
    await reportFrameMetric("hycmsFrameRect", {
      x: hycmsFrame.x,
      y: hycmsFrame.y,
      width: hycmsFrame.width,
      height: hycmsFrame.height,
    });
  }

  const snapshot = getAttendanceSnapshot();
  if (isScheduledLecture(snapshot)) {
    if (oncePer(`lecture_scheduled:${location.href}`, 10000)) {
      await send("LECTURE_SKIPPED", {
        lectureUrl: window.top.location.href,
        reason: "학습 예정 강의로 판단되어 스킵",
        markProcessed: false,
      }).catch(() => {});
      await reportDebug("lecture_scheduled", "학습 예정 강의 스킵", { statusParts: snapshot.statusParts });
    }
    return;
  }

  if (isNonRequiredRecording(snapshot)) {
    if (oncePer(`lecture_non_required:${location.href}`, 10000)) {
      await send("LECTURE_SKIPPED", {
        lectureUrl: window.top.location.href,
        reason: "대면/강의녹화 유형으로 판단되어 스킵",
        markProcessed: true,
      }).catch(() => {});
      await reportDebug("lecture_non_required", "대면/강의녹화 강의 스킵", { statusParts: snapshot.statusParts });
    }
    return;
  }

  if (snapshot.completed) {
    if (oncePer(`lecture_completed:${location.href}`, 10000)) {
      await send("LECTURE_COMPLETED", { lectureUrl: window.top.location.href }).catch(() => {});
      await reportDebug("lecture_completed", "완료 상태 감지", { statusParts: snapshot.statusParts });
    }
    return;
  }

  if (snapshot.nonVideo) {
    if (oncePer(`lecture_skipped:${location.href}`, 10000)) {
      await send("LECTURE_SKIPPED", {
        lectureUrl: window.top.location.href,
        reason: "비디오가 아닌 항목으로 판단되어 스킵",
      }).catch(() => {});
      await reportDebug("lecture_skipped", "비디오가 아닌 항목 스킵");
    }
    return;
  }

  if (snapshot.refreshButton && oncePer(`refresh:${location.href}`, STATUS_REFRESH_MS)) {
    safeClick(snapshot.refreshButton);
    await reportDebug("status_refresh", `학습 상태 확인 클릭 (${snapshot.statusParts.join(" | ") || "-"})`);
    return;
  }

  await reportDebug("attendance_wait", `학습 상태 대기 (${snapshot.statusParts.join(" | ") || "-"})`);
};

const findButtonByText = (text) =>
  Array.from(document.querySelectorAll("button, [role='button'], div, span, a")).find(
    (button) => normalizeText(button.textContent) === text
  );

const parsePlayerTime = (text) => {
  const match = normalizeText(text).match(/(\d{1,2}):(\d{2})\s*\/\s*(\d{1,2}):(\d{2})/);
  if (!match) return null;
  return {
    currentSeconds: Number(match[1]) * 60 + Number(match[2]),
    totalSeconds: Number(match[3]) * 60 + Number(match[4]),
  };
};

const getHycmsSnapshot = () => {
  const timeText = normalizeText(document.querySelector(".vc-pctrl-play-time-text-area")?.textContent);
  const timing = parsePlayerTime(timeText);
  const frontScreenButton = queryVisible([
    "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div",
    "#front-screen .vc-front-screen-btn-wrapper.video1-btn > div",
    "#front-screen .vc-front-screen-btn-wrapper > div",
    "#front-screen",
  ]);
  const playPauseButton = queryVisible([
    "#play-controller .vc-pctrl-play-pause-btn",
    ".vc-pctrl-play-pause-btn",
    ".player-center-control-wrapper",
    ".player-restart-btn",
    ".vjs-big-play-button",
  ]);
  const player = queryVisible([
    "#svp-video",
    "#vp1-video1",
    "#vp4-video1",
    ".video-js",
  ]);

  return {
    timeText,
    timing,
    frontScreenButton,
    playPauseButton,
    playPauseClass: document.querySelector(".vc-pctrl-play-pause-btn")?.className || "",
    playerClass: player?.className || "",
    mediaStates: Array.from(document.querySelectorAll("video, audio")).map((media, index) => ({
      index,
      paused: media.paused,
      muted: media.muted,
      currentTime: Number(media.currentTime || 0),
      readyState: Number(media.readyState || 0),
      tag: media.tagName,
    })),
  };
};

const wakeHycmsControls = () => {
  const target = queryVisible([
    "#viewer-root",
    "#video-player-area",
    ".vc-vplay-video1",
    ".vc-vplay-video2",
    ".vc-vplay-video3",
    ".vc-vplay-video4",
    "#play-controller",
    "body",
  ]);
  if (!target) return false;
  ["mousemove", "mouseenter", "mouseover"].forEach((type) => {
    target.dispatchEvent(
      new MouseEvent(type, {
        bubbles: true,
        cancelable: true,
        clientX: Math.max(20, Math.floor(window.innerWidth / 2)),
        clientY: Math.max(20, Math.floor(window.innerHeight / 2)),
      })
    );
  });
  return true;
};

const handleHycmsFrame = async () => {
  const resumeYes = findButtonByText("예");
  if (resumeYes && oncePer(`resume:${location.href}`, 15000)) {
    rawClick(resumeYes);
    await reportDebug("resume_yes", "이어보기 확인 클릭");
    return;
  }

  wakeHycmsControls();
  const snapshot = getHycmsSnapshot();
  const timeCacheKey = `hya:hycms-time:${location.href}`;
  const prevSeconds = Number(sessionStorage.getItem(timeCacheKey) || "-1");
  const currentSeconds = snapshot.timing?.currentSeconds ?? -1;
  if (currentSeconds >= 0) {
    sessionStorage.setItem(timeCacheKey, String(currentSeconds));
  }

  const timeAdvanced = currentSeconds >= 0 && prevSeconds >= 0 && currentSeconds > prevSeconds;
  const playerLooksPlaying =
    snapshot.playerClass.includes("vjs-playing") ||
    snapshot.playPauseClass.includes("vc-pctrl-on-play") ||
    snapshot.playPauseClass.includes("vc-pctrl-on-playing");
  const playerLooksPaused =
    snapshot.playerClass.includes("vjs-paused") || snapshot.playPauseClass.includes("vc-pctrl-on-pause");

  if ((timeAdvanced || playerLooksPlaying) && !playerLooksPaused) {
    await reportDebug("playing", `플레이어 재생 중 (${snapshot.timeText || "-"})`);
    return;
  }

  if (snapshot.frontScreenButton && oncePer(`front-screen:${location.href}`, 10000)) {
    const rect = snapshot.frontScreenButton.getBoundingClientRect();
    const result = await send("CLICK_HYCMS_START", {
      targetRect: {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      },
    }).catch(() => ({ ok: false, reason: "message_failed" }));

    await reportDebug(
      result?.ok ? "front_screen_clicked" : "front_screen_click_failed",
      result?.ok ? "실좌표 시작 버튼 클릭" : `실좌표 클릭 실패 (${result?.reason || "unknown"})`
    );
    return;
  }

  if (snapshot.playPauseButton && oncePer(`play:${location.href}`, 10000)) {
    rawClick(snapshot.playPauseButton);
    await reportDebug(
      "play_clicked",
      `플레이어 재생 클릭 (${snapshot.timeText || snapshot.playPauseClass || "custom control"})`
    );
    return;
  }

  await reportDebug("player_wait", `플레이어 컨트롤 대기 (${snapshot.timeText || snapshot.playPauseClass || "-"})`, {
    mediaStates: snapshot.mediaStates,
  });
};

const tick = async () => {
  if (state.busy) return;
  state.busy = true;
  try {
    const store = await getStore(["isRunning", "lectureQueue", "learnedLectures", "currentLectureUrl"]);
    if (!store.isRunning) return;

    if (window === window.top) {
      await handleTopFrame(store);
      return;
    }

    if (location.hostname === LMS_HOST && location.pathname.includes("/learningx/lti/lecture_attendance/items/view/")) {
      await handleAttendanceFrame();
      return;
    }

    if (location.hostname === HYCMS_HOST) {
      await handleHycmsFrame();
    }
  } catch (error) {
    console.error("[HanyangAuto] tick error", error);
  } finally {
    state.busy = false;
  }
};

setInterval(tick, TICK_MS);
syncDebugPanelEnabled().then(() => {
  tick();
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "AUTOMATION_STARTED") {
    tick();
  }
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.showDebugPanel) return;
  state.debugPanelEnabled = Boolean(changes.showDebugPanel.newValue);
  if (!state.debugPanelEnabled) {
    removeDebugPanel();
    return;
  }
  tick();
});
