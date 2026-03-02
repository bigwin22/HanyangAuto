# HanyangAuto - 한양대학교 강의 자동 수강 서비스

HanyangAuto는 한양대학교 Learning Management System(LMS)의 강의 수강을 자동화하여 사용자의 편의성을 높이는 프로젝트입니다.

## 🚀 프로젝트 개요

현재 이 프로젝트는 백엔드(Python/FastAPI), 자동화 엔진(Selenium), 프론트엔드(React/TypeScript)로 구성되어 있습니다. 사용자가 웹 대시보드에서 로그인하면 서버에서 Selenium 드라이버를 실행하여 실제 브라우저를 에뮬레이트하고 강의를 수강합니다.

### 주요 기능
- **자동 로그인**: 한양대 계정으로 LMS 자동 로그인
- **강의 목록 추출**: 수강해야 할 강의 및 동영상 목록 자동 파악
- **자동 수강**: 동영상 강의 및 PDF 강의 자동 수강 완료 처리
- **관리자 대시보드**: 사용자 관리 및 자동화 상태 모니터링

---

## 🛠 기술 스택

- **Backend**: Python, FastAPI, SQLite
- **Automation**: Selenium WebDriver (Chrome)
- **Frontend**: React, TypeScript, Tailwind CSS, Vite
- **Infrastructure**: Docker, Docker Compose

---

## 📂 프로젝트 구조

```text
HanyangAuto/
├── automation/       # Selenium 기반 강의 자동화 로직 (Python)
├── back/             # API 서버 및 사용자 관리 (FastAPI)
├── front/            # 사용자 및 관리자 웹 인터페이스 (React)
│   └── web/          # Vite 기반 React 프로젝트
├── utils/            # DB, 로거, 셀레늄 유틸리티
└── docker-compose.yml # 컨테이너 오케스트레이션
```

---

## 🛣 로드맵: Chrome 익스텐션 전환

현재의 서버 기반 자동화 방식에서 벗어나, 사용자의 브라우저에서 직접 동작하는 **Chrome 익스텐션**으로 전환할 계획입니다.

### 왜 Chrome 익스텐션인가요?
1. **서버 비용 절감**: 서버에서 수십 개의 Selenium 인스턴스를 돌릴 필요가 없어집니다.
2. **보안 강화**: 사용자의 비밀번호를 서버에 저장하지 않고 브라우저 내에서 직접 처리할 수 있습니다.
3. **사용자 경험**: 별도의 웹사이트 방문 없이 LMS 페이지에서 바로 자동화를 실행할 수 있습니다.

**전환 방법 및 가이드는 `CHROME_EXTENSION_GUIDE.md`를 참고하세요.**

---

## 🔧 설치 및 실행 (현재 버전)

1. **환경 변수 설정**: `genkey.sh` 등을 통해 필요한 키를 생성합니다.
2. **Docker 실행**:
   ```bash
   docker-compose up --build
   ```
3. **접속**:
   - 프론트엔드: `http://localhost:8080`
   - 백엔드 API: `http://localhost:8000`

---

## 📄 라이선스
이 프로젝트는 교육 및 연구 목적으로 제작되었습니다.
