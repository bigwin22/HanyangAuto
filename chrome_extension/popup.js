const statusDiv = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');

// 팝업 열릴 때 상태 확인
chrome.storage.local.get("isRunning", ({ isRunning }) => {
  statusDiv.innerText = isRunning ? "자동화 실행 중..." : "대기 중";
});

const sendMessageToActiveTab = (action) => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action });
    }
  });
};

startBtn.addEventListener('click', () => {
  chrome.storage.local.set({ isRunning: true }, () => {
    statusDiv.innerText = "자동화 실행 중...";
    sendMessageToActiveTab("START_AUTOMATION");
    window.close(); // 팝업 닫기 (실행을 위해)
  });
});

stopBtn.addEventListener('click', () => {
  chrome.storage.local.set({ isRunning: false }, () => {
    statusDiv.innerText = "중지됨";
    sendMessageToActiveTab("STOP_AUTOMATION");
  });
});
