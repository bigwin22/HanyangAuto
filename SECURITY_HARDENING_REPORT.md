# Security Hardening Report

작성일: 2026-03-27

## 1. 작업 목적

다음 보안 문제를 코드 수준에서 우선 해결했다.

- 기본 관리자 계정 및 약한 초기 관리자 비밀번호 허용
- 관리자/사용자 로그인 및 LMS 계정 검증 API에 대한 무차별 대입, 대량 요청 방어 부재
- `back -> automation` 내부 API 호출에 대한 호출자 인증 부재
- OAuth callback URL, 토큰성 문자열, 민감 예외 메시지의 로그 노출
- 관리자 비밀번호를 복호화 가능한 형태로 저장하던 구조

## 2. 수정한 파일과 변경 내용

### `/Users/kth88/Documents/CODING/HanyangAuto/server/utils/security.py`

신규 파일 추가.

- `SlidingWindowRateLimiter` 추가
  - 로그인/검증 API에 공통으로 쓸 수 있는 sliding window rate limiter 구현
- `get_client_ip()` 추가
  - `CF-Connecting-IP`, `X-Forwarded-For`, `X-Real-IP` 우선 사용
- `mask_sensitive_text()`, `mask_sensitive_url()` 추가
  - `access_token`, `refresh_token`, `token`, `code`, `password`, `session` 등 민감 값을 로그에서 마스킹

### `/Users/kth88/Documents/CODING/HanyangAuto/server/utils/database.py`

관리자 비밀번호 저장 및 초기화 로직 강화.

- 관리자 비밀번호를 AES 복호화 방식 대신 `PBKDF2-HMAC-SHA256` 해시 저장 방식으로 변경
- `hash_admin_password()`, `verify_admin_password()`, `admin_password_needs_migration()` 추가
- 기존 Admin 레코드가 레거시 암호화 포맷이어도 로그인 성공 시 새 해시 포맷으로 마이그레이션 가능하도록 기반 추가
- 최초 admin 생성 시:
  - `ADMIN_INITIAL_PASSWORD` 미설정 금지
  - `admin` 같은 기본값 금지
  - 12자 미만 비밀번호 금지
- `__main__` 테스트용 insecure admin/test user 삽입 코드 제거

### `/Users/kth88/Documents/CODING/HanyangAuto/server/back/main.py`

백엔드 인증/세션/API 호출 보안 강화.

- 세션 쿠키 강화
  - `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE` 환경변수 반영
  - 세션 쿠키 이름 명시
  - `Cache-Control: no-store`, `Pragma: no-cache` 추가
- 내부 API 토큰 강제
  - `INTERNAL_API_TOKEN` 미설정 시 서버 시작 실패
  - automation 호출 시 `X-Internal-Token` 헤더 추가
- 사용자 로그인 `/api/user/login`
  - IP 기준, 계정 기준 rate limit 추가
  - 입력 길이 검증 추가
  - 예외 메시지 마스킹 적용
- 관리자 로그인 `/api/admin/login`
  - IP 기준, 계정 기준 rate limit 추가
  - `admin/admin` 예외 허용 로직 제거
  - `verify_admin_password()` 사용
  - 레거시 admin 비밀번호는 로그인 성공 시 자동 해시 마이그레이션
  - 로그인 시 세션 초기화 후 재설정
- 관리자 비밀번호 변경 `/api/admin/change-password`
  - 현재 비밀번호 검증을 해시/레거시 호환 방식으로 변경
  - 새 비밀번호 최소 길이 12자 적용
- 로그 조회 `/api/admin/user/{user_id}/logs`
  - `sanitize_filename()` 사용으로 로그 경로 탐색 위험 완화
  - 최신 로그를 plain text로 반환하도록 정리
- 관리자 전체 자동화 트리거 `/api/admin/trigger-all`
  - 내부 토큰을 포함해 automation 서버 호출

### `/Users/kth88/Documents/CODING/HanyangAuto/server/automation/main.py`

내부 자동화 API 보호 및 검증 요청 제한 추가.

- `INTERNAL_API_TOKEN` 미설정 시 서버 시작 실패
- `require_internal_request()` 추가
  - `/start-automation`
  - `/on-user-registered`
  - `/verify-login`
  - `/trigger-daily`
  - 위 4개 엔드포인트에 `X-Internal-Token` 검증 강제
- `/verify-login` 에 IP/계정 기준 rate limit 추가
- 브라우저용 CORS는 기본 비활성화
  - 필요할 때만 `AUTOMATION_CORS_ALLOW_ORIGINS` 로 허용
- 입력 길이 검증 추가
- 예외 로그 마스킹 적용

### `/Users/kth88/Documents/CODING/HanyangAuto/server/automation/playwright_automation.py`

민감 로그 노출 완화.

- dialog 메시지 마스킹
- `login_submit` 결과의 URL/메시지 마스킹
- 로그인 후 이동 실패 URL 마스킹
- 자동화 오류/검증 오류의 예외 메시지 마스킹
- 사용자 응답에 내부 예외 문자열을 그대로 내보내지 않도록 정리

### `/Users/kth88/Documents/CODING/HanyangAuto/server/docker/docker-compose.yml`

운영 compose 환경변수 전달 추가.

- `INTERNAL_API_TOKEN`
- `AUTOMATION_CORS_ALLOW_ORIGINS`
- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_SAMESITE`

### `/Users/kth88/Documents/CODING/HanyangAuto/server/docker/docker-compose.dev.yml`

개발 compose 환경변수 전달 추가.

- `SESSION_SECRET_B64`
- `ADMIN_INITIAL_PASSWORD`
- `RECEIVE_SERVER_URL`
- `CORS_ALLOW_ORIGINS`
- `INTERNAL_API_TOKEN`
- `AUTOMATION_CORS_ALLOW_ORIGINS`
- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_SAMESITE`

## 3. 해결된 문제 요약

### 문제 1. 기본 admin/admin 허용

이전 상태:

- 초기 admin 비밀번호 기본값이 `admin`
- 코드에서 `admin/admin` 로그인 자체를 특별 허용

현재 상태:

- 최초 부팅 시 `ADMIN_INITIAL_PASSWORD` 가 없거나 `admin` 이면 서버 시작 실패
- 12자 미만 초기 관리자 비밀번호도 거부
- `admin/admin` 특례 로그인 제거

### 문제 2. brute-force 및 curl 난사 방어 부재

이전 상태:

- `/api/user/login`, `/api/admin/login`, `/verify-login` 에 요청 제한 없음

현재 상태:

- IP/계정 기준 sliding window rate limiting 추가
- 초과 시 HTTP `429` 와 `Retry-After` 반환

### 문제 3. 컨테이너 내부 API 호출자 검증 부재

이전 상태:

- 내부 네트워크에 접근 가능한 어떤 주체든 automation 핵심 API 호출 가능

현재 상태:

- `X-Internal-Token` 기반 호출자 인증 강제
- 토큰 미설정 시 서버 부팅 실패

### 문제 4. 민감 로그 노출

이전 상태:

- OAuth callback URL, token성 파라미터, 예외 문자열이 로그에 그대로 남을 수 있었음

현재 상태:

- URL query/fragment 민감키 마스킹
- 토큰/비밀번호/session류 문자열 마스킹
- 사용자 응답에는 내부 예외를 직접 노출하지 않음

### 문제 5. 관리자 비밀번호 복호화 저장

이전 상태:

- Admin 비밀번호를 사용자 계정과 같은 복호화 가능 포맷으로 저장

현재 상태:

- Admin 비밀번호는 PBKDF2 해시로 저장
- 기존 레거시 admin 레코드는 로그인 성공 시 자동 마이그레이션

## 4. 운영 시 반영해야 할 환경변수

최소 필요값:

- `DB_ENCRYPTION_KEY_B64`
- `SESSION_SECRET_B64`
- `ADMIN_INITIAL_PASSWORD`
- `INTERNAL_API_TOKEN`

권장값:

- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_SAMESITE=lax`
- `AUTOMATION_CORS_ALLOW_ORIGINS` 는 비워두거나 꼭 필요한 origin만 명시

## 5. 검증 결과

실행한 검증:

1. `python -m compileall server`
2. 임시 virtualenv에서 backend/automation import 검증
3. admin 해시 생성/검증 함수 동작 확인

검증 결과:

- 구문 컴파일 성공
- `back.main`, `automation.main` import 성공
- admin 해시/검증 로직 정상 확인

## 6. 남은 주의사항

- 기존 로그 파일에 이미 남아 있는 민감 정보는 이번 패치로 자동 삭제되지 않는다.
- 사용자 LMS 비밀번호는 기능상 복호화가 여전히 필요하므로, 서버/DB/환경변수 접근 통제는 계속 중요하다.
- 다중 인스턴스 운영 시 현재 rate limiter는 프로세스 메모리 기반이므로 Redis 같은 중앙 저장소 기반으로 옮기는 것이 더 안전하다.

## 7. 운영 호환성 점검 결과

코드 변경 후 기존 운영과의 충돌 여부도 점검했다.

- 프론트와의 API 호환성:
  - `/api/admin/login` 은 여전히 `{ success, adminId }` 형식으로 동작하므로 관리자 로그인 화면과 충돌 없음
  - `/api/admin/user/{user_id}/logs` 는 plain text 반환으로 정리했지만, 현재 대시보드는 이미 `res.text()` 로 읽고 있어 충돌 없음
  - `/api/admin/trigger-all` 응답 형식은 기존 대시보드 사용 방식과 호환됨
- 기존 DB와의 호환성:
  - 기존 admin 비밀번호가 레거시 암호화 포맷이어도 첫 로그인 성공 시 해시 포맷으로 자동 마이그레이션됨
  - 기존 사용자 LMS 비밀번호 저장 방식은 유지했으므로 사용자 자동화 흐름과 충돌 없음
- 운영/배포 충돌:
  - 새 필수 환경변수 `INTERNAL_API_TOKEN` 이 없으면 서비스가 시작되지 않음
  - 이를 해결하기 위해 `deploy.sh`, `deploy.yml`, `.env.example`, 개발 문서를 함께 수정함
