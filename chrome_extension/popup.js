const statusDiv = document.getElementById("status");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const resetLearnedInput = document.getElementById("resetLearned");
const showDebugPanelInput = document.getElementById("showDebugPanel");
const debugDiv = document.getElementById("debug");
const updateStatusTextDiv = document.getElementById("updateStatusText");
const versionMetaTextDiv = document.getElementById("versionMetaText");
const checkUpdateBtn = document.getElementById("checkUpdateBtn");
const openUpdatePageBtn = document.getElementById("openUpdatePageBtn");

const queryActiveTab = () =>
  chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);

const sendToBackground = (payload) => chrome.runtime.sendMessage(payload);

const formatCheckedAt = (value) => {
  if (!value) return "-";
  return new Date(value).toLocaleString();
};

const getUpdateStatusText = (info) => {
  if (info.status === "update_available") return "새 버전이 있습니다.";
  if (info.status === "up_to_date") return `최신 버전 입니다. (현재 버전: ${info.currentVersion || "-"})`;
  if (info.status === "ahead_of_remote") return `현재 버전이 최신 릴리즈보다 높습니다. (현재 버전: ${info.currentVersion || "-"})`;
  if (info.status === "no_release") return "GitHub Release가 아직 없습니다.";
  if (info.status === "error") return "릴리즈 확인에 실패했습니다.";
  return "버전 상태를 아직 확인하지 않았습니다.";
};

const renderUpdateInfo = (info) => {
  if (!info) {
    updateStatusTextDiv.innerText = "버전 정보를 불러오지 못했습니다.";
    versionMetaTextDiv.innerText = "현재 버전: - , 최신 버전: -";
    openUpdatePageBtn.style.display = "none";
    return;
  }

  updateStatusTextDiv.innerText = getUpdateStatusText(info);
  versionMetaTextDiv.innerText = `현재 버전: ${info.currentVersion || "-"} , 최신 버전: ${info.latestVersion || "-"}`;

  openUpdatePageBtn.style.display =
    info.hasUpdate || info.status === "no_release" ? "block" : "none";
  openUpdatePageBtn.innerText =
    info.hasUpdate ? "릴리즈 페이지 열기" : "Releases 페이지 열기";
};

const updateVersionInfo = async (force = false) => {
  const response = await sendToBackground({
    action: "CHECK_EXTENSION_UPDATE",
    force,
  });
  if (!response?.ok) {
    renderUpdateInfo(null);
    return;
  }

  renderUpdateInfo(response.updateInfo);
};

const updateStatus = async () => {
  const state = await sendToBackground({ action: "GET_AUTOMATION_STATE" });
  if (!state?.ok) {
    statusDiv.innerText = "상태 조회 실패";
    return;
  }

  const queueLen = (state.lectureQueue || []).length;
  const learnedLen = (state.learnedLectures || []).length;
  statusDiv.innerText = state.isRunning
    ? `실행 중 | 남은 강의 ${queueLen}개 | 처리 완료 ${learnedLen}개`
    : `대기 중 | 처리 완료 ${learnedLen}개`;

  const dbg = state.debugState || {};
  showDebugPanelInput.checked = Boolean(state.showDebugPanel);
  debugDiv.innerText = [
    `step: ${dbg.step || "-"}`,
    `detail: ${dbg.detail || dbg.message || "-"}`,
    `url: ${dbg.url || state.currentLectureUrl || "-"}`,
    `updated: ${dbg.updatedAt ? new Date(dbg.updatedAt).toLocaleTimeString() : "-"}`,
  ].join("\n");
};

startBtn.addEventListener("click", async () => {
  const activeTab = await queryActiveTab();
  if (!activeTab?.id) {
    statusDiv.innerText = "활성 탭을 찾을 수 없습니다.";
    return;
  }

  await sendToBackground({
    action: "START_AUTOMATION",
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

showDebugPanelInput.addEventListener("change", async () => {
  const result = await sendToBackground({
    action: "SET_DEBUG_PANEL",
    enabled: showDebugPanelInput.checked,
  });
  if (!result?.ok) {
    statusDiv.innerText = "디버그 패널 설정 저장 실패";
    return;
  }
  await updateStatus();
});

checkUpdateBtn.addEventListener("click", async () => {
  updateStatusTextDiv.innerText = "버전 확인 중...";
  versionMetaTextDiv.innerText = "현재 버전: - , 최신 버전: -";
  await updateVersionInfo(true);
});

openUpdatePageBtn.addEventListener("click", async () => {
  await sendToBackground({ action: "OPEN_EXTENSION_UPDATE_PAGE" });
});

updateStatus().then(() => {
  setInterval(updateStatus, 2000);
});
updateVersionInfo(false);
