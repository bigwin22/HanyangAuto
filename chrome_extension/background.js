const STORAGE_KEYS = {
  IS_RUNNING: "isRunning",
  LECTURE_QUEUE: "lectureQueue",
  LEARNED_LECTURES: "learnedLectures",
  CURRENT_LECTURE_URL: "currentLectureUrl",
  DEBUG_STATE: "debugState",
  FRAME_METRICS: "frameMetrics",
  SHOW_DEBUG_PANEL: "showDebugPanel",
};

const LMS_ORIGIN = "https://learning.hanyang.ac.kr";
const DEBUGGER_VERSION = "1.3";

const getStore = (keys) => chrome.storage.local.get(keys);
const setStore = (obj) => chrome.storage.local.set(obj);

const uniqueLectures = (lectures) => {
  const seen = new Set();
  return (lectures || []).filter((lecture) => {
    const key = lecture?.url || lecture?.htmlUrl || "";
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const navigateToLecture = async (tabId, lecture) => {
  if (!tabId || !lecture?.url) return;
  await setStore({ [STORAGE_KEYS.CURRENT_LECTURE_URL]: lecture.url });
  await chrome.tabs.update(tabId, { url: lecture.url });
};

const updateFrameMetrics = async (tabId, kind, rect) => {
  if (!tabId || !kind || !rect) return;
  const store = await getStore([STORAGE_KEYS.FRAME_METRICS]);
  const frameMetrics = { ...(store.frameMetrics || {}) };
  frameMetrics[String(tabId)] = {
    ...(frameMetrics[String(tabId)] || {}),
    [kind]: rect,
    updatedAt: Date.now(),
  };
  await setStore({ [STORAGE_KEYS.FRAME_METRICS]: frameMetrics });
};

const ensureDebuggerAttached = async (tabId) => {
  const target = { tabId };
  try {
    await chrome.debugger.attach(target, DEBUGGER_VERSION);
  } catch (error) {
    if (!String(error?.message || "").includes("Another debugger is already attached")) {
      const sessions = await chrome.debugger.getTargets().catch(() => []);
      const alreadyAttached = (sessions || []).some((item) => item.tabId === tabId && item.attached);
      if (!alreadyAttached) throw error;
    }
  }
};

const dispatchRealMouseClick = async (tabId, x, y) => {
  await ensureDebuggerAttached(tabId);
  const target = { tabId };
  await chrome.debugger.sendCommand(target, "Page.enable").catch(() => {});
  await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x,
    y,
    button: "left",
  });
  await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x,
    y,
    button: "left",
    buttons: 1,
    clickCount: 1,
  });
  await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x,
    y,
    button: "left",
    buttons: 1,
    clickCount: 1,
  });
};

chrome.debugger.onEvent.addListener(async (source, method) => {
  if (method !== "Page.javascriptDialogOpening" || !source.tabId) return;

  try {
    const store = await getStore([STORAGE_KEYS.IS_RUNNING, STORAGE_KEYS.DEBUG_STATE]);
    if (!store.isRunning) return;

    await chrome.debugger.sendCommand({ tabId: source.tabId }, "Page.handleJavaScriptDialog", {
      accept: true,
    });

    await setStore({
      [STORAGE_KEYS.DEBUG_STATE]: {
        ...(store.debugState || {}),
        step: "dialog_accepted",
        message: "사이트 이동 확인 팝업 자동 수락",
        updatedAt: Date.now(),
      },
    });
  } catch (error) {
    console.warn("[HanyangAuto] dialog auto-accept failed", error);
  }
});

chrome.runtime.onInstalled.addListener(async () => {
  const current = await getStore([
    STORAGE_KEYS.IS_RUNNING,
    STORAGE_KEYS.LECTURE_QUEUE,
    STORAGE_KEYS.LEARNED_LECTURES,
    STORAGE_KEYS.CURRENT_LECTURE_URL,
    STORAGE_KEYS.DEBUG_STATE,
    STORAGE_KEYS.FRAME_METRICS,
    STORAGE_KEYS.SHOW_DEBUG_PANEL,
  ]);
  await setStore({
    [STORAGE_KEYS.IS_RUNNING]: false,
    [STORAGE_KEYS.LECTURE_QUEUE]: current.lectureQueue || [],
    [STORAGE_KEYS.LEARNED_LECTURES]: current.learnedLectures || [],
    [STORAGE_KEYS.CURRENT_LECTURE_URL]: current.currentLectureUrl || "",
    [STORAGE_KEYS.DEBUG_STATE]: current.debugState || {},
    [STORAGE_KEYS.FRAME_METRICS]: current.frameMetrics || {},
    [STORAGE_KEYS.SHOW_DEBUG_PANEL]: Boolean(current.showDebugPanel),
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const tabId = sender.tab?.id;
    const action = message?.action;

    if (action === "START_AUTOMATION") {
      const current = await getStore([STORAGE_KEYS.LEARNED_LECTURES]);
      const learnedLectures = message.resetLearned ? [] : current.learnedLectures || [];

      await setStore({
        [STORAGE_KEYS.IS_RUNNING]: true,
        [STORAGE_KEYS.LECTURE_QUEUE]: [],
        [STORAGE_KEYS.LEARNED_LECTURES]: learnedLectures,
        [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
        [STORAGE_KEYS.FRAME_METRICS]: {},
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "started",
          message: "자동화 시작",
          updatedAt: Date.now(),
        },
      });

      if (tabId) {
        await chrome.tabs.update(tabId, { url: LMS_ORIGIN });
        chrome.tabs.sendMessage(tabId, { action: "AUTOMATION_STARTED" }).catch(() => {});
      }

      sendResponse({ ok: true });
      return;
    }

    if (action === "STOP_AUTOMATION") {
      await setStore({
        [STORAGE_KEYS.IS_RUNNING]: false,
        [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
        [STORAGE_KEYS.FRAME_METRICS]: {},
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "stopped",
          message: "사용자 중지",
          updatedAt: Date.now(),
        },
      });

      if (tabId) {
        chrome.tabs.sendMessage(tabId, { action: "AUTOMATION_STOPPED" }).catch(() => {});
      }

      sendResponse({ ok: true });
      return;
    }

    if (action === "LECTURES_DISCOVERED") {
      if (!tabId || !Array.isArray(message.lectures) || message.lectures.length === 0) {
        sendResponse({ ok: false });
        return;
      }

      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.LECTURE_QUEUE,
        STORAGE_KEYS.LEARNED_LECTURES,
      ]);
      if (!store.isRunning) {
        sendResponse({ ok: false });
        return;
      }

      if ((store.lectureQueue || []).length > 0) {
        sendResponse({ ok: true, skipped: true });
        return;
      }

      const learnedSet = new Set(store.learnedLectures || []);
      const queue = uniqueLectures(message.lectures).filter((lecture) => !learnedSet.has(lecture.url));

      if (queue.length === 0) {
        await setStore({
          [STORAGE_KEYS.IS_RUNNING]: false,
          [STORAGE_KEYS.LECTURE_QUEUE]: [],
          [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
          [STORAGE_KEYS.DEBUG_STATE]: {
            step: "completed",
            message: "이미 처리된 강의만 남아 자동화를 종료합니다.",
            updatedAt: Date.now(),
          },
        });
        sendResponse({ ok: true, queueLength: 0 });
        return;
      }

      await setStore({
        [STORAGE_KEYS.LECTURE_QUEUE]: queue,
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "lecture_queue_ready",
          message: `강의 ${queue.length}개 수집`,
          updatedAt: Date.now(),
        },
      });

      await navigateToLecture(tabId, queue[0]);
      sendResponse({ ok: true, queueLength: queue.length });
      return;
    }

    if (action === "LECTURE_COMPLETED" || action === "LECTURE_SKIPPED") {
      if (!tabId) {
        sendResponse({ ok: false });
        return;
      }

      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.LECTURE_QUEUE,
        STORAGE_KEYS.LEARNED_LECTURES,
        STORAGE_KEYS.CURRENT_LECTURE_URL,
      ]);
      if (!store.isRunning) {
        sendResponse({ ok: false });
        return;
      }

      const currentUrl = message.lectureUrl || store.currentLectureUrl;
      const shouldMarkProcessed = action === "LECTURE_COMPLETED" || message.markProcessed !== false;
      const learned = shouldMarkProcessed
        ? [...new Set([...(store.learnedLectures || []), currentUrl].filter(Boolean))]
        : store.learnedLectures || [];
      const nextQueue = (store.lectureQueue || []).filter((lecture) => lecture?.url !== currentUrl);

      await setStore({
        [STORAGE_KEYS.LEARNED_LECTURES]: learned,
        [STORAGE_KEYS.LECTURE_QUEUE]: nextQueue,
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: action === "LECTURE_COMPLETED" ? "lecture_completed" : "lecture_skipped",
          message:
            action === "LECTURE_COMPLETED"
              ? "강의 완료 처리"
              : message.reason || "비디오가 아니거나 처리 불가 항목 스킵",
          lectureUrl: currentUrl || "",
          markProcessed: shouldMarkProcessed,
          updatedAt: Date.now(),
        },
      });

      if (nextQueue.length > 0) {
        await navigateToLecture(tabId, nextQueue[0]);
      } else {
        await setStore({
          [STORAGE_KEYS.IS_RUNNING]: false,
          [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
          [STORAGE_KEYS.DEBUG_STATE]: {
            step: "completed",
            message: "모든 강의 처리 완료",
            updatedAt: Date.now(),
          },
        });
        chrome.tabs.sendMessage(tabId, { action: "AUTOMATION_COMPLETED" }).catch(() => {});
      }

      sendResponse({ ok: true, queueLength: nextQueue.length });
      return;
    }

    if (action === "UPDATE_CURRENT_LECTURE_URL") {
      await setStore({ [STORAGE_KEYS.CURRENT_LECTURE_URL]: message.url || "" });
      sendResponse({ ok: true });
      return;
    }

    if (action === "REPORT_DEBUG_STATE") {
      const prev = await getStore([STORAGE_KEYS.DEBUG_STATE]);
      await setStore({
        [STORAGE_KEYS.DEBUG_STATE]: {
          ...(prev.debugState || {}),
          ...(message.debugState || {}),
          updatedAt: Date.now(),
        },
      });
      sendResponse({ ok: true });
      return;
    }

    if (action === "REPORT_FRAME_METRIC") {
      await updateFrameMetrics(tabId, message.kind, message.rect);
      sendResponse({ ok: true });
      return;
    }

    if (action === "CLICK_HYCMS_START") {
      const store = await getStore([STORAGE_KEYS.FRAME_METRICS]);
      const metrics = store.frameMetrics?.[String(tabId)] || {};
      const tool = metrics.toolFrameRect;
      const hycms = metrics.hycmsFrameRect;
      const targetRect = message.targetRect;
      if (!tool || !hycms || !targetRect) {
        sendResponse({ ok: false, reason: "missing_frame_metrics", metrics });
        return;
      }

      const x = tool.x + hycms.x + targetRect.x + targetRect.width / 2;
      const y = tool.y + hycms.y + targetRect.y + targetRect.height / 2;

      try {
        await dispatchRealMouseClick(tabId, x, y);
        await setStore({
          [STORAGE_KEYS.DEBUG_STATE]: {
            step: "front_screen_clicked",
            message: `실좌표 클릭 (${Math.round(x)}, ${Math.round(y)})`,
            updatedAt: Date.now(),
          },
        });
        sendResponse({ ok: true, x, y });
      } catch (error) {
        sendResponse({ ok: false, reason: String(error?.message || error) });
      }
      return;
    }

    if (action === "GET_AUTOMATION_STATE") {
      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.LECTURE_QUEUE,
        STORAGE_KEYS.LEARNED_LECTURES,
        STORAGE_KEYS.CURRENT_LECTURE_URL,
        STORAGE_KEYS.DEBUG_STATE,
        STORAGE_KEYS.FRAME_METRICS,
        STORAGE_KEYS.SHOW_DEBUG_PANEL,
      ]);
      sendResponse({ ok: true, ...store });
      return;
    }

    if (action === "SET_DEBUG_PANEL") {
      await setStore({
        [STORAGE_KEYS.SHOW_DEBUG_PANEL]: Boolean(message.enabled),
      });
      sendResponse({ ok: true, enabled: Boolean(message.enabled) });
      return;
    }

    sendResponse({ ok: false, reason: "unknown_action" });
  })();

  return true;
});
