# CHROME_EXTENSION_GUIDE

이 문서는 HanyangAuto를 **서버 없는 클라이언트 전용 Chrome 익스텐션**으로 사용하는 방법을 설명합니다.

## 1. 현재 아키텍처

- 자동화 실행 위치: 사용자 브라우저(로컬)
- 상태 저장: `chrome.storage.local`
- 서버 통신: 없음
- 대상 사이트: `https://learning.hanyang.ac.kr/*`

## 2. Python 로직과의 1:1 대응

기존 Python([automation.py](/Users/kth88/Documents/CODING/HanyangAuto/server/automation/automation.py))의 핵심 함수를 다음처럼 대응시켰습니다.

1. `login(...)`
- 팝업에 저장한 계정으로 로그인 페이지(`#uid`, `#upw`, `#login_btn`) 자동 입력/클릭

2. `get_courses(...)`
- 대시보드 `#DashboardCard_Container > div > div`에서 과목 ID 추출
- 추출 결과를 과목 큐(`courseQueue`)로 저장

3. `get_lectures(...)`
- `courses/{id}/external_tools/140`의 강의 목록에서 완료 배지(`.completed`) 없는 항목만 선택

4. `learn_lecture(...)`
- 영상 강의: 시작 버튼 클릭, 이어보기 확인, 진행 버튼/완료 상태 확인
- PDF 강의: 완료 상태 확인 후 진행 버튼 클릭
- 완료 시 `LECTURE_COMPLETED` 이벤트 전송

5. `run_user_automation(...)`
- background worker가 과목 큐/완료 강의 목록을 관리하며 순차 진행
- 과목 큐가 비면 자동 종료

## 3. 파일별 역할

- `manifest.json`
  - 권한, 호스트, content script/background/popup 등록
- `background.js`
  - 자동화 상태 관리(실행 여부, 과목 큐, 완료 강의)
  - 메시지 처리: 시작/중지/과목 완료/강의 완료
- `content_script.js`
  - LMS DOM 조작
  - 로그인/대시보드/강의목록/플레이어 자동화
- `popup.html`, `popup.js`
  - 사용자 입력(UI), 시작/중지 제어

## 4. 설치 방법

1. Chrome에서 `chrome://extensions` 열기
2. `개발자 모드` 켜기
3. `압축해제된 확장 프로그램 로드`
4. `chrome_extension` 폴더 선택

## 5. 사용 순서

1. LMS 탭을 열고 익스텐션 팝업을 연다.
2. 아이디/비밀번호 입력(선택), `로그인 자동 입력 사용` 체크 여부 선택
3. 필요하면 `기존 완료 기록 초기화 후 시작` 체크
4. `자동 수강 시작` 클릭
5. 익스텐션이 과목/강의를 순차 처리
6. 팝업 상태에서 남은 과목 수와 완료 강의 수 확인

## 6. 주의사항

- 브라우저 탭이 닫히면 자동화가 중단됩니다.
- LMS UI가 변경되면 CSS 셀렉터 보정이 필요할 수 있습니다.
- 계정 정보는 브라우저 로컬 저장소에 저장되므로 개인 PC 사용을 권장합니다.

## 7. 배포(선택)

Chrome 웹 스토어 배포 시:

1. `chrome_extension` 폴더를 zip으로 압축 (`manifest.json` 루트 위치 유지)
2. Chrome 웹 스토어 개발자 대시보드에서 신규 아이템 등록
3. 설명/아이콘/스크린샷 입력 후 심사 제출
