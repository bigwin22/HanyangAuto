/**
 * HanyangAuto Content Script (V4 - 초정밀 디버깅 모드)
 */

// 화면에 상세 로그 표시용 UI
const createDebugConsole = () => {
    let container = document.getElementById('hanyang-debug-console');
    if (!container) {
        container = document.createElement('div');
        container.id = 'hanyang-debug-console';
        container.style.cssText = 'position:fixed; top:10px; right:10px; z-index:999999; background:rgba(0,0,0,0.9); color:#0f0; padding:15px; border-radius:8px; font-family:monospace; font-size:11px; max-width:400px; max-height:80vh; overflow-y:auto; border:1px solid #0f0; box-shadow:0 0 10px rgba(0,255,0,0.5); pointer-events:none;';
        document.body.appendChild(container);
    }
    return container;
};

const debugLog = (category, msg) => {
    const console = createDebugConsole();
    const time = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.style.marginBottom = '4px';
    logLine.innerHTML = `<span style="color:#aaa">[${time}]</span> <span style="color:#ff0">[${category}]</span> ${msg}`;
    
    // 최신 로그가 위에 오도록 추가
    console.insertBefore(logLine, console.firstChild);
    
    // 로그가 너무 많으면 삭제
    if (console.children.length > 30) console.lastChild.remove();
};

const processAutomation = async () => {
    const { isRunning } = await chrome.storage.local.get("isRunning");
    if (!isRunning) {
        const console = document.getElementById('hanyang-debug-console');
        if (console) console.style.display = 'none';
        return;
    }

    const debugConsole = createDebugConsole();
    debugConsole.style.display = 'block';
    
    const url = window.location.href;
    const isIframe = window !== window.top;
    
    debugLog("CONTEXT", `URL: ${url.substring(0, 50)}... | Frame: ${isIframe ? 'iFrame' : 'MAIN'}`);

    // 1. 대시보드 처리
    if (url.includes("/dashboard")) {
        const cards = document.querySelectorAll(".ic-DashboardCard");
        debugLog("DASHBOARD", `발견된 강의 카드: ${cards.length}개`);
        if (cards.length > 0) {
            const firstLink = cards[0].querySelector("a.ic-DashboardCard__link");
            if (firstLink) {
                debugLog("ACTION", "첫 번째 강의 진입 시도...");
                firstLink.click();
            }
        }
        return;
    }

    // 2. 강의 메인 페이지 -> 온라인 강의 도구로 리다이렉트
    if (url.includes("/courses/") && !url.includes("/external_tools/")) {
        const courseId = url.match(/courses\/(\d+)/)?.[1];
        if (courseId) {
            debugLog("ACTION", `온라인 강의 도구(140)로 이동 중... (ID: ${courseId})`);
            window.location.href = `https://learning.hanyang.ac.kr/courses/${courseId}/external_tools/140`;
        }
        return;
    }

    // 3. 강의 목록 찾기 (가장 핵심적인 부분)
    // 모든 <a> 태그 중에서 '수강하기' 또는 특정 패턴을 가진 링크 탐색
    const allLinks = document.querySelectorAll("a");
    const lectureLinks = Array.from(allLinks).filter(a => {
        // 한양대 LMS 강의 목록 링크 패턴 (예상)
        return a.href.includes("viewer") || a.innerText.includes("수강") || a.className.includes("lecture");
    });

    debugLog("SCRAPER", `현재 화면 전체 링크: ${allLinks.length}개 | 강의 후보 링크: ${lectureLinks.length}개`);

    // 수강 완료 여부 판단 (옆에 '완료'라는 텍스트가 있는지 확인)
    let foundAny = false;
    for (const link of lectureLinks) {
        const parent = link.closest("div");
        const isCompleted = parent && (parent.innerText.includes("완료") || parent.innerText.includes("100%"));
        
        if (!isCompleted) {
            debugLog("LECTURE", `미수강 강의 포착: "${link.innerText.trim().substring(0, 15)}..."`);
            link.click();
            foundAny = true;
            break; 
        }
    }

    // 4. 동영상/PDF 플레이어 대응
    const videoBtn = document.querySelector(".video1-btn, .vc-front-screen-play-btn, [class*='play-btn']");
    if (videoBtn) {
        debugLog("PLAYER", "비디오 재생 버튼 발견!");
        videoBtn.click();
        
        // 이어보기 팝업
        setTimeout(() => {
            const okBtns = Array.from(document.querySelectorAll("button, div")).filter(el => 
                el.innerText.includes("확인") || el.innerText.includes("예") || el.className.includes("ok-btn")
            );
            if (okBtns.length > 0) {
                debugLog("POPUP", "이어보기 확인 버튼 클릭");
                okBtns[0].click();
            }
        }, 2000);
    }

    const pdfBtn = document.querySelector(".xnlail-pdf-component button, .xnvc-progress-info-container button");
    if (pdfBtn && !pdfBtn.disabled) {
        debugLog("PLAYER", "PDF 완료 버튼 발견!");
        pdfBtn.click();
    }

    // 5. 완료 체크 후 목록 복귀
    if (document.body.innerText.includes("학습 완료") || document.body.innerText.includes("100% 완료")) {
        debugLog("STATUS", "수강 완료 확인! 5초 후 이전 페이지로...");
        setTimeout(() => window.history.back(), 5000);
    }
};

// 2.5초마다 반복 실행
setInterval(processAutomation, 2500);

chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "START_AUTOMATION") {
        chrome.storage.local.set({ isRunning: true }, () => {
            debugLog("SYSTEM", "자동화 시작됨 (V4-DEBUG)");
            processAutomation();
        });
    } else if (request.action === "STOP_AUTOMATION") {
        chrome.storage.local.set({ isRunning: false }, () => {
            debugLog("SYSTEM", "자동화 중지됨");
            setTimeout(() => {
                const console = document.getElementById('hanyang-debug-console');
                if (console) console.remove();
            }, 2000);
        });
    }
});
