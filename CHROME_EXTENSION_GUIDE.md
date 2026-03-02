# Chrome 익스텐션 전환 및 업로드 가이드

이 문서는 기존 Selenium 기반의 자동화 서비스를 Chrome 익스텐션으로 전환하고, 이를 다른 사용자들이 사용할 수 있도록 업로드하는 방법을 설명합니다.

---

## 🏗 아키텍처 전환 전략: Selenium에서 JavaScript로

기존 시스템은 서버의 Python(Selenium)이 브라우저를 조종했지만, 익스텐션은 **사용자의 브라우저 내에서 직접 JavaScript**가 동작합니다.

### 1. 주요 구성 요소 (Manifest V3 기준)

- **`manifest.json`**: 익스텐션의 메타데이터 및 권한 정의 (가장 중요)
- **`content.js`**: 실제 한양대 LMS 페이지(`learning.hanyang.ac.kr`)의 DOM을 조작하는 로직 (기존 `automation.py`의 JavaScript 버전)
- **`popup.html/js`**: 사용자가 클릭했을 때 나타나는 작은 UI (시작/중지 버튼 등)
- **`background.js` (Service Worker)**: 익스텐션의 상태 관리 및 장기 실행 작업 처리

### 2. 코드 변환 예시

| 기존 로직 (Python/Selenium) | 익스텐션 로직 (JavaScript/Content Script) |
| :--- | :--- |
| `driver.find_element(By.ID, "uid").send_keys(id)` | `document.getElementById("uid").value = id;` |
| `obj_click(driver, "#login_btn")` | `document.querySelector("#login_btn").click();` |
| `WebDriverWait(driver, 10).until(...)` | `new Promise(resolve => setTimeout(resolve, 1000));` 또는 `MutationObserver` 사용 |

---

## 🛠 익스텐션 개발 및 테스트 방법

### 1. 개발용 파일 준비
익스텐션 폴더(예: `chrome_extension/`)를 만들고 아래 파일을 작성합니다.
- `manifest.json`: 권한(`"permissions": ["activeTab", "storage"]`) 및 도메인(`"matches": ["*://learning.hanyang.ac.kr/*"]`) 설정
- `content.js`: `automation.py`의 로직을 JS로 구현
- `popup.html`: "자동 수강 시작" 버튼이 있는 UI

### 2. 로컬에서 로드하여 테스트
1. Chrome 브라우저에서 `chrome://extensions/` 주소로 이동합니다.
2. 우측 상단의 **'개발자 모드'**를 켭니다.
3. **'압축해제된 확장 프로그램을 로드합니다'** 버튼을 클릭하고 프로젝트 폴더를 선택합니다.
4. 한양대 LMS 페이지에 접속하여 익스텐션이 정상적으로 작동하는지 확인합니다.

---

## 🚀 Chrome 웹 스토어 업로드 및 배포

다른 사람들이 이 익스텐션을 설치하게 하려면 Chrome 웹 스토어에 등록해야 합니다.

### 1. 개발자 계정 등록
- [Chrome 웹 스토어 개발자 대시보드](https://chrome.google.com/webstore/devconsole/)에 접속합니다.
- 개발자 등록비($5, 일회성)를 결제해야 합니다.

### 2. 압축 파일 만들기
- 프로젝트 폴더의 모든 파일을 `.zip` 파일로 압축합니다. (`manifest.json`이 루트에 있어야 함)

### 3. 아이템 등록
1. 대시보드에서 **'+ 신규 아이템'**을 클릭합니다.
2. 압축한 `.zip` 파일을 업로드합니다.
3. 익스텐션 이름, 설명, 아이콘(128x128), 스크린샷 등을 입력합니다.

### 4. 심사 및 게시
- '게시를 위해 제출' 버튼을 클릭하면 구글의 심사가 시작됩니다. (보통 1~3일 소요)
- 심사가 완료되면 공개(Public) 또는 비공개(Unlisted)로 배포할 수 있습니다.

---

## 💡 팁: 더 쉬운 배포 방법 (개인용)

공식 스토어 등록 없이 공유하고 싶다면:
1. 코드를 GitHub에 올립니다.
2. 사용자들에게 코드를 다운로드(또는 git clone)하게 합니다.
3. 사용자들에게 위의 **'로컬에서 로드하여 테스트'** 단계를 직접 수행하도록 안내합니다.

---

## ⚠️ 주의사항

- **보안**: 사용자의 비밀번호는 절대 외부 서버로 전송하지 마세요. `chrome.storage.local` 등을 활용해 브라우저 내에만 저장해야 합니다.
- **정책**: 한양대학교 LMS의 이용 약관을 준수해야 하며, 과도한 요청은 서버에 부하를 줄 수 있으므로 주의가 필요합니다.
