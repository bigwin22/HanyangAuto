const STORAGE_KEYS = {
  IS_RUNNING: "isRunning",
  CREDENTIALS: "credentials",
  COURSE_QUEUE: "courseQueue",
  LEARNED_LECTURES: "learnedLectures",
  CURRENT_LECTURE_URL: "currentLectureUrl",
  DEBUG_STATE: "debugState",
};

const LMS_ORIGIN = "https://learning.hanyang.ac.kr";

const getStore = (keys) => chrome.storage.local.get(keys);
const setStore = (obj) => chrome.storage.local.set(obj);

const unique = (arr) => [...new Set(arr)];

const navigateToCourseTool = async (tabId, courseId) => {
  await chrome.tabs.update(tabId, {
    url: `${LMS_ORIGIN}/courses/${courseId}/external_tools/140`,
  });
};

const goBackInTab = async (tabId) => {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      history.back();
    },
  });
};

chrome.runtime.onInstalled.addListener(async () => {
  await setStore({
    [STORAGE_KEYS.IS_RUNNING]: false,
    [STORAGE_KEYS.COURSE_QUEUE]: [],
    [STORAGE_KEYS.LEARNED_LECTURES]: [],
    [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
    [STORAGE_KEYS.DEBUG_STATE]: {},
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const tabId = sender.tab?.id;
    const action = message?.action;

    if (action === "START_AUTOMATION") {
      const current = await getStore([
        STORAGE_KEYS.LEARNED_LECTURES,
      ]);
      const learnedLectures = message.resetLearned ? [] : (current.learnedLectures || []);

      await setStore({
        [STORAGE_KEYS.IS_RUNNING]: true,
        [STORAGE_KEYS.CREDENTIALS]: message.credentials || {},
        [STORAGE_KEYS.COURSE_QUEUE]: [],
        [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
        [STORAGE_KEYS.LEARNED_LECTURES]: learnedLectures,
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "started",
          message: "자동화 시작",
          updatedAt: Date.now(),
        },
      });

      if (tabId) {
        chrome.tabs.sendMessage(tabId, { action: "AUTOMATION_STARTED" }).catch(() => {});
      }

      sendResponse({ ok: true });
      return;
    }

    if (action === "STOP_AUTOMATION") {
      await setStore({
        [STORAGE_KEYS.IS_RUNNING]: false,
        [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
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

    if (action === "COURSES_DISCOVERED") {
      if (!tabId || !Array.isArray(message.courses) || message.courses.length === 0) {
        sendResponse({ ok: false });
        return;
      }

      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.COURSE_QUEUE,
      ]);

      if (!store.isRunning) {
        sendResponse({ ok: false });
        return;
      }

      const existingQueue = store.courseQueue || [];
      if (existingQueue.length > 0) {
        sendResponse({ ok: true, skipped: true });
        return;
      }

      const queue = unique(message.courses);
      await setStore({ [STORAGE_KEYS.COURSE_QUEUE]: queue });
      await setStore({
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "course_queue_ready",
          message: `과목 ${queue.length}개 수집`,
          courses: queue,
          updatedAt: Date.now(),
        },
      });
      await navigateToCourseTool(tabId, queue[0]);
      sendResponse({ ok: true, queue });
      return;
    }

    if (action === "COURSE_FINISHED") {
      if (!tabId || !message.courseId) {
        sendResponse({ ok: false });
        return;
      }

      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.COURSE_QUEUE,
      ]);

      if (!store.isRunning) {
        sendResponse({ ok: false });
        return;
      }

      const nextQueue = (store.courseQueue || []).filter((id) => id !== message.courseId);
      await setStore({ [STORAGE_KEYS.COURSE_QUEUE]: nextQueue });

      if (nextQueue.length > 0) {
        await navigateToCourseTool(tabId, nextQueue[0]);
      } else {
        await setStore({
          [STORAGE_KEYS.IS_RUNNING]: false,
          [STORAGE_KEYS.CURRENT_LECTURE_URL]: "",
          [STORAGE_KEYS.DEBUG_STATE]: {
            step: "completed",
            message: "모든 과목 처리 완료",
            updatedAt: Date.now(),
          },
        });
        chrome.tabs.sendMessage(tabId, { action: "AUTOMATION_COMPLETED" }).catch(() => {});
      }

      sendResponse({ ok: true, queue: nextQueue });
      return;
    }

    if (action === "LECTURE_COMPLETED") {
      if (!tabId) {
        sendResponse({ ok: false });
        return;
      }

      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.LEARNED_LECTURES,
        STORAGE_KEYS.CURRENT_LECTURE_URL,
      ]);

      if (!store.isRunning) {
        sendResponse({ ok: false });
        return;
      }

      const lectureUrl = message.lectureUrl || store.currentLectureUrl;
      if (lectureUrl) {
        const updated = unique([...(store.learnedLectures || []), lectureUrl]);
        await setStore({ [STORAGE_KEYS.LEARNED_LECTURES]: updated });
      }
      await setStore({
        [STORAGE_KEYS.DEBUG_STATE]: {
          step: "lecture_completed",
          message: "강의 완료 처리",
          lectureUrl: lectureUrl || "",
          updatedAt: Date.now(),
        },
      });

      await goBackInTab(tabId);
      sendResponse({ ok: true, lectureUrl });
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

    if (action === "GET_AUTOMATION_STATE") {
      const store = await getStore([
        STORAGE_KEYS.IS_RUNNING,
        STORAGE_KEYS.COURSE_QUEUE,
        STORAGE_KEYS.LEARNED_LECTURES,
        STORAGE_KEYS.CREDENTIALS,
        STORAGE_KEYS.DEBUG_STATE,
      ]);
      sendResponse({ ok: true, ...store });
      return;
    }

    sendResponse({ ok: false, reason: "unknown_action" });
  })();

  return true;
});
