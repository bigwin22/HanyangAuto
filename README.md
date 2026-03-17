# HanyangAuto

한양대학교 LMS 강의 자동 수강 프로젝트입니다.

현재 기본 실행 방식은 **Chrome 익스텐션(클라이언트 단독 실행)** 입니다.  
서버에서 Selenium을 돌리지 않고, 사용자의 브라우저에서만 자동화가 동작합니다.

## 핵심 동작

익스텐션은 기존 `automation/automation.py` 흐름을 클라이언트에서 그대로 재현합니다.

1. 로그인 페이지에서 계정 자동 입력/로그인(옵션)
2. 대시보드에서 수강 과목 ID 수집
3. 과목별 `external_tools/140` 진입
4. 미완료 강의만 순차 진입
5. 영상/PDF 강의 완료 처리
6. 완료 강의 URL을 로컬 저장소(`chrome.storage.local`)에 기록
7. 과목 큐가 비면 자동 종료

## 디렉터리

```text
HanyangAuto/
├── chrome_extension/   # 클라이언트 전용 Chrome Extension (권장)
├── automation/         # 기존 Selenium 자동화 엔진(레거시 참조)
├── back/               # 기존 백엔드(레거시)
├── front/              # 기존 프론트엔드(레거시)
└── CHROME_EXTENSION_GUIDE.md
```

## Chrome 익스텐션 설치

1. Chrome에서 `chrome://extensions` 접속
2. 우측 상단 `개발자 모드` 활성화
3. `압축해제된 확장 프로그램 로드` 클릭
4. 프로젝트의 `chrome_extension` 폴더 선택

## 사용 방법

1. 한양대 LMS 탭(`https://learning.hanyang.ac.kr`)을 연다.
2. 익스텐션 팝업에서 아이디/비밀번호(선택)와 옵션을 설정한다.
3. `자동 수강 시작` 클릭
4. 자동화가 끝나면 상태가 완료로 바뀐다.

자세한 설정/디버깅/배포는 `CHROME_EXTENSION_GUIDE.md`를 참고하세요.
