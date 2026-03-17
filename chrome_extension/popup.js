const statusDiv = document.getElementById("status");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const userIdInput = document.getElementById("userId");
const passwordInput = document.getElementById("password");
const autoLoginInput = document.getElementById("autoLogin");
const resetLearnedInput = document.getElementById("resetLearned");
const debugDiv = document.getElementById("debug");

const getStore = (keys) => chrome.storage.local.get(keys);
const setStore = (obj) => chrome.storage.local.set(obj);

const queryActiveTab = () =>
  chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);

const sendToBackground = (payload) => chrome.runtime.sendMessage(payload);

const updateStatus = async () => {
  const state = await sendToBackground({ action: "GET_AUTOMATION_STATE" });
  if (!state?.ok) {
    statusDiv.innerText = "상태 조회 실패";
    return;
  }

  const queueLen = (state.courseQueue || []).length;
  const learnedLen = (state.learnedLectures || []).length;
  statusDiv.innerText = state.isRunning
    ? `실행 중 | 남은 과목 ${queueLen}개 | 완료 강의 ${learnedLen}개`
    : `대기 중 | 완료 강의 ${learnedLen}개`;

  const dbg = state.debugState || {};
  const detectedCount = (dbg.detectedLectures || []).length;
  debugDiv.innerText = [
    `step: ${dbg.step || "-"}`,
    `detail: ${dbg.detail || dbg.message || "-"}`,
    `url: ${dbg.url || "-"}`,
    `detected lectures: ${detectedCount}`,
    `updated: ${dbg.updatedAt ? new Date(dbg.updatedAt).toLocaleTimeString() : "-"}`,
  ].join("\n");
};

const loadCredentials = async () => {
  const { credentials } = await getStore(["credentials"]);
  userIdInput.value = credentials?.userId || "";
  passwordInput.value = credentials?.password || "";
  autoLoginInput.checked = Boolean(credentials?.autoLogin);
};

startBtn.addEventListener("click", async () => {
  const credentials = {
    userId: userIdInput.value.trim(),
    password: passwordInput.value,
    autoLogin: autoLoginInput.checked,
  };

  await setStore({ credentials });

  const activeTab = await queryActiveTab();
  if (!activeTab?.id) {
    statusDiv.innerText = "활성 탭을 찾을 수 없습니다.";
    return;
  }

  await sendToBackground({
    action: "START_AUTOMATION",
    credentials,
    resetLearned: resetLearnedInput.checked,
  });

  statusDiv.innerText = "자동화 시작됨";
  window.close();
});

stopBtn.addEventListener("click", async () => {
  const activeTab = await queryActiveTab();
  if (!activeTab?.id) {
    statusDiv.innerText = "활성 탭을 찾을 수 없습니다.";
    return;
  }

  await sendToBackground({ action: "STOP_AUTOMATION" });
  await updateStatus();
});

loadCredentials().then(async () => {
  await updateStatus();
  setInterval(updateStatus, 2000);
});
