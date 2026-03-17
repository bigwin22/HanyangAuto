const statusDiv = document.getElementById("status");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const resetLearnedInput = document.getElementById("resetLearned");
const debugDiv = document.getElementById("debug");

const queryActiveTab = () =>
  chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);

const sendToBackground = (payload) => chrome.runtime.sendMessage(payload);

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

updateStatus().then(() => {
  setInterval(updateStatus, 2000);
});
