# HanyangAuto

한양대학교 LMS에서 동영상 강의를 더 편하게 수강할 수 있도록 돕는 Chrome 확장 프로그램입니다.

이 프로젝트의 기본 사용 방식은 Chrome 확장 프로그램입니다. 사용자가 직접 `learning.hanyang.ac.kr`에 로그인한 뒤, 확장 프로그램이 현재 브라우저 세션을 그대로 사용해 강의 진행을 이어갑니다.

개발, 서버 운영, Docker, 배포 문서는 [README.developer.md](/Users/kth88/Documents/CODING/HanyangAuto/README.developer.md)에 정리되어 있습니다.

## 무엇을 하나요?

- LMS 대시보드에서 수강 중인 과목을 찾습니다.
- 각 과목의 강의 목록을 확인합니다.
- 동영상 강의 페이지에 들어가 재생을 진행합니다.
- `학습 상태 확인`을 통해 반영 상태를 다시 확인합니다.
- 완료한 강의는 기록하고 다음 강의로 넘어갑니다.

## 준비 사항

- Chrome 브라우저
- 한양대학교 LMS 계정
- `https://learning.hanyang.ac.kr` 로그인 완료 상태

## 설치 방법

1. 이 저장소를 내려받거나 압축 해제합니다.
2. Chrome에서 `chrome://extensions`로 이동합니다.
3. 우측 상단의 `개발자 모드`를 켭니다.
4. `압축해제된 확장 프로그램 로드`를 누릅니다.
5. 프로젝트의 [chrome_extension](/Users/kth88/Documents/CODING/HanyangAuto/chrome_extension) 폴더를 선택합니다.

## 사용 방법

1. Chrome에서 `https://learning.hanyang.ac.kr`를 열고 로그인합니다.
2. LMS 탭을 활성화한 상태로 확장 프로그램 팝업을 엽니다.
3. 필요하면 `기존 완료 기록 초기화 후 시작` 옵션을 선택합니다.
4. `자동 수강 시작` 버튼을 누릅니다.
5. 상태 영역에서 진행 상황을 확인합니다.
6. 중간에 멈추고 싶으면 `중지` 버튼을 누릅니다.

## 팝업 옵션 설명

- `기존 완료 기록 초기화 후 시작`: 이전 실행에서 저장된 완료 기록을 지우고 처음부터 다시 확인합니다.
- `페이지 디버그 패널 표시`: LMS 페이지 안에 디버그 정보를 표시합니다. 문제가 있을 때만 켜는 것을 권장합니다.

## 사용 팁

- 반드시 로그인된 LMS 탭에서 시작해야 합니다.
- 자동화 중에는 강의 탭을 닫지 않는 편이 안전합니다.
- 진행이 기대와 다르면 한 번 중지한 뒤 다시 시작해 보세요.
- LMS 구조가 바뀌면 일부 동작이 영향을 받을 수 있습니다.

## 문제 해결

### 시작이 안 될 때

- 현재 탭이 `learning.hanyang.ac.kr`인지 확인하세요.
- LMS 로그인 상태가 유지되어 있는지 확인하세요.
- 확장 프로그램이 정상적으로 로드되었는지 `chrome://extensions`에서 확인하세요.

### 진행이 멈춘 것 같을 때

- 팝업의 상태 표시가 바뀌는지 확인하세요.
- `페이지 디버그 패널 표시`를 켜고 어느 단계에서 멈췄는지 확인하세요.
- LMS 페이지를 새로고침한 뒤 다시 시작해 보세요.

### 완료 처리가 이상할 때

- LMS의 `학습 상태 확인` 반영에 시간이 걸릴 수 있습니다.
- 필요하면 `기존 완료 기록 초기화 후 시작`을 켠 뒤 다시 실행하세요.

## 참고 문서

- 확장 프로그램 중심 상세 가이드: [CHROME_EXTENSION_GUIDE.md](/Users/kth88/Documents/CODING/HanyangAuto/CHROME_EXTENSION_GUIDE.md)
- 개발자/운영 문서: [README.developer.md](/Users/kth88/Documents/CODING/HanyangAuto/README.developer.md)
