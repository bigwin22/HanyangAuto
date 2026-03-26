# HanyangAuto

한양대학교 LMS 동영상 강의 자동 수강 프로젝트입니다.

현재는 두 가지 실행 방식을 제공합니다.

1. 서버 방식
   Playwright 워커가 로그인부터 수강까지 전부 자동화합니다.
2. Chrome 익스텐션 방식
   사용자가 로그인한 브라우저 세션을 그대로 사용합니다.

## 핵심 동작

공통적으로 다음 흐름을 사용합니다.

1. 대시보드에서 수강 과목 수집
2. 각 과목의 Canvas 모듈 API 조회
3. `ExternalTool(content_id=138)` 기반 lecture attendance 항목 수집
4. 동영상 강의 페이지 진입
5. 플레이어 재생 및 이어보기 처리
6. `학습 상태 확인`으로 서버 상태 재동기화
7. 완료 강의는 기록하고 다음 강의로 이동

## 디렉터리

```text
HanyangAuto/
├── chrome_extension/   # 로그인된 브라우저 세션을 사용하는 확장 프로그램
├── server/
│   ├── automation/     # Playwright 기반 서버 자동화 워커
│   ├── back/           # 서버 백엔드
│   ├── front/          # 서버 프론트엔드
│   ├── utils/          # 서버 공용 유틸
│   └── docker/         # docker compose 및 Dockerfile 모음
└── CHROME_EXTENSION_GUIDE.md
```

## Chrome 익스텐션 설치

1. Chrome에서 `chrome://extensions` 접속
2. 우측 상단 `개발자 모드` 활성화
3. `압축해제된 확장 프로그램 로드` 클릭
4. 프로젝트의 `chrome_extension` 폴더 선택

## 사용 방법

1. 한양대 LMS 탭(`https://learning.hanyang.ac.kr`)에 로그인한다.
2. 익스텐션 팝업을 연다.
3. `자동 수강 시작` 클릭
4. 자동화가 끝나면 상태가 완료로 바뀐다.

## 서버 워커 실행

```bash
cd server
uvicorn automation.main:app --reload --port 7000
```

## 도커 실행

도커 관련 파일은 `server/docker/` 폴더에 모아두었습니다.

실행 전에 루트의 환경 파일을 준비합니다.

```bash
cp .env.example .env
```

채워야 하는 핵심 값:

- `DB_ENCRYPTION_KEY_B64`
- `SESSION_SECRET_B64`
- `DOCKER_IMAGE`
- `CONTAINER_NAME`

키 생성 예시:

```bash
openssl rand -base64 32
```

```bash
docker compose -f server/docker/docker-compose.yml build
docker compose -f server/docker/docker-compose.yml up
```

자동화 서버만 먼저 확인하려면:

```bash
docker compose -f server/docker/docker-compose.yml up back automation
```

Playwright Chromium 설치가 포함된 자동화 이미지는 [automation.Dockerfile](/Users/kth88/Documents/CODING/HanyangAuto/server/docker/automation.Dockerfile)입니다.

## Private GHCR 기반 배포

운영 배포는 GitHub-hosted runner가 이미지를 빌드해서 private GHCR로 올리고, self-hosted runner가 서버에서 이미지를 pull해서 재시작만 하도록 구성되어 있습니다.

### 추가된 파일

- [ci.yml](/Users/kth88/Documents/CODING/HanyangAuto/.github/workflows/ci.yml)
- [deploy.yml](/Users/kth88/Documents/CODING/HanyangAuto/.github/workflows/deploy.yml)
- [docker-compose.prod.yml](/Users/kth88/Documents/CODING/HanyangAuto/server/docker/docker-compose.prod.yml)
- [deploy.sh](/Users/kth88/Documents/CODING/HanyangAuto/server/docker/deploy.sh)

### GitHub Secrets

- `SERVER_APP_PATH`
- `GHCR_OWNER`
- `GHCR_USERNAME`
- `GHCR_TOKEN`
- `CONTAINER_NAME`
- `DOMAIN`
- `PORT`
- `DB_ENCRYPTION_KEY_B64`
- `SESSION_SECRET_B64`
- `ADMIN_INITIAL_PASSWORD`

`SERVER_APP_PATH`는 self-hosted runner가 설치된 서버에서 운영용 `.env`, `data`, `logs`를 보관할 절대 경로입니다. 이 경로 자체가 git repo일 필요는 없습니다.

### 배포 시 생성되는 `.env`

배포 job은 위 개별 secrets를 합쳐 `${SERVER_APP_PATH}/.env`를 매번 다시 생성합니다. `IMAGE_TAG`는 workflow가 자동으로 현재 커밋 SHA를 넣습니다.
컨테이너 볼륨은 `${SERVER_APP_PATH}/data`, `${SERVER_APP_PATH}/logs`를 사용합니다.
아래 값들은 workflow 기본값으로 고정되어 별도 secret이 필요 없습니다.

- `RECEIVE_SERVER_URL=http://automation:7000`
- `CORS_ALLOW_ORIGINS=http://localhost:8000,http://127.0.0.1:8000`
- `PLAYWRIGHT_HEADLESS=true`

### 운영 배포 흐름

1. `main` 브랜치에 push
2. GitHub-hosted runner가 `front`, `back`, `automation` 이미지를 빌드
3. 각 이미지를 private GHCR에 `latest`와 커밋 SHA 태그로 push
4. self-hosted runner가 workflow workspace에 최신 코드를 checkout
5. GitHub Secrets 값으로 `${SERVER_APP_PATH}/.env`를 재생성
6. 서버에서 `${SERVER_APP_PATH}/data`, `${SERVER_APP_PATH}/logs` 디렉터리를 보장
7. checkout된 `deploy.sh`와 `docker-compose.prod.yml`로 pull-only 배포 실행

### 서버에서 수동 배포

```bash
IMAGE_TAG=latest bash server/docker/deploy.sh
```

자세한 설정/디버깅/배포는 `CHROME_EXTENSION_GUIDE.md`를 참고하세요.
