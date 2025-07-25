'''
## 프로젝트의 목적

1. 이 프로젝트는 한양대 학교의 녹화 온라인 강의를 자동으로 재생해주기 위한 프로젝트 입니다.
2. 많은 사람이 웹 페이지를 통해 자신의 계정을 등록하면 서버에서 그 계정으로 자동 로그인 후 강의를 재생해줍니다.

당신의 역할

1. 당신은 최고의 PM이자 조력자입니다.
2. 당신은 최고의 프로그래머입니다.
3. 당신의 최고의 서버 엔지니어입니다.
4. 당신의 최고의 백엔드 엔지니어 입니다.

## 준수해야야할 것

1. 반말하지 마세요.
2. 정확한 것만 말하고 확실하지 않은 것은 모른다고 말하십시오.
3. 대화들의 내용을 중요내용의 '키-값'형태로 기억하도 다른 모든 대화에서 이 기억들을 활용하십시오.
4. 이전에 주었던 프로젝트에 대한 정보(소스코드, 서비스 구성 방식 등)을 기억하고 활용하십시오
5. 요청하지 않은 그 어떤 것이라도 추가하거나 정보를 주지 마세요.
6. 지시한 것만 정확하게 수행하십시오

## 웹페이지 구성(@/web)

### 메인페이지 (/)

1. 배경: 하늘색의 그라데이션
2. favicon: 한양대 로고
3. 가운데에 로그인 폼 있음
    1. 하얀색의 둥근 사각형
    2. 한양대 ID/PWD입력하는 두개의 칸
        1. pwd칸에는 입력한 pwd보여주는 토글 버튼 있음
    3. 두개의 칸 위에 한양대 로고 있음

### 로그인 성공페이지(/sucess)

1.기본적 디자인은 메인페이지와 동일

### ADMIN 관련 페이지

1. 로그인 페이지(/admin/login)
    1. 배경: 밝은 회색의 그라데이션
    2. 가운데에 로그인 폼 있음
    3. 하얀색의 둥근 사각형
        1. ID/PWD입력칸만 있음
2. 대쉬보드(/admin/dashboard)
    1. 상단
        1. 현재 총 등록된 유저수 보여주기
        2. 현재 수강 완료된 유저 수 보여주기
        3. 현재 수강 중인 유저수 보여주기
        4. 에러난 유저들 보여주기
    2. 하단
        1. 유저들 리스트 보여주기
            1. 유저 한 칸당 있을 정보(등록된 일시/아이디/현재 상태/삭제 버튼)
            2. 아이디를 누르면 현재 수강한 강의 리스트가 밑에 뜸
            3. 삭제 버튼을 누르면 그 유저에 관련된 모든 DB삭제
            4. 현재 상태 버튼을 누르면 그 유저에 관한 최근 생성된 로그 폴더의 로그 보여주기
3. 비밀번호 변경(/admin/chage-password)
    1. 기본적인 디자인은 로그인 페이지와 동일
    2. 현재 비밀번호/새 비밀번호/새 비밀번호 확인 으로만 구성

## 실제 서비스 프로그램

1. @automation.py가 실제 서비스의 기반이 됩니다.

## 서비스 작동 방식

1. {USER}의 웹페이지에서 hanyang계정 입력
2. 만약 신규 등록자일 경우
    1. 계정을 DB에 등록 시키기
    2. @automaiton.py의 로직 실행시키기
3. 만약 기존 등록자일 경우
    1. DB에 비밀번호를 업데이트 하기
    2. @automation.py의 로직 실행시키기

## 원하는 기능

1. 새로 등록된 강의가 있는지 확인하고 새로 등록된 강의가 있다면 재생(스케쥴)
    1. 매일 아침 7시에
    2. 서비스(서버)가 재시작 될 때
2. 들은 강의는 DB에 저장해서 스케쥴이나 서비스 재시작시 두번 듣게 하지 않게 하기
3. 여러 유저가 동시에 강의가 수강되게 만들기

## 네트워크 구성

1. Traefik 의 리버스 프록싱을 통해 해당 서비스의 접속
    1. Traefik은 이미 서버에서 작동 중임
2. 해당 서비스의 도메인: hanyang.newme.dev
3. 해당 서비스의 내부 접속 포트 번호: 8000

## 개발 환경

Apple Mac Silicon M4

Model: Apple Mac pro M4 14

파이썬: 3.12

## DB구성

### User

| Col Name | Type | Restrict Condition | Description |
| --- | --- | --- | --- |
| NUM | INT | PRIMARY KEY | 생성순서 |
| ID | TEXT | UNIQUE, NOT NULL | 한양대 로그인 ID |
| PWD_Encrypted | TEXT | NOT NULL | 암호화된 비밀번호(추후 복호화해서 입력할거임) |
| Created_at | TIMESTAMP | DEFAULT now() | 계정 등록 일시 |
| Stae | TEXT | NOT NULL | 현재 상태(수강 완료, 수강 중, 오류발생) |

### Admin

| Col Name | Type | Restrict Condition | Description |
| --- | --- | --- | --- |
| NUM | INT | PRIMARY KEY | 얘는 1밖에 없긴해 |
| ID | TEXT | UNIQUE, NOT NULL | 어드민 아이디 |
| PWD_Encrypted | TEXT | NOT NULL | 얘는 복호화할 필요 없음 평문을 암호화할 때 저장된 값과 일치하는지만 보면 됨 |
| Modifited_at | TIMESTAMP | DEFAULT now() | 계정 정보 수정 일시 |

### Learned_Lecture

| Col Name | Type | Restrict Condition | Description |
| --- | --- | --- | --- |
| Account_ID | INT | FK → `account(num)`, NOT NULL | 유저 번호 |
| lecture_ID | TEXT | NOT NULL | 강의 URL에 있음 |
| PRIMARY KEY | -  | (account_id, lecture_id) | 중복 수강 방지 |

### Admin

1. 기본적으로 ADMIN의 계정은 다음과 같습니다.
    1. ID: admin / PWD: admin
2. 어드민 계정으로 로그인시 1-a의 정보라면 ID및 PWD를 변경하게 해주세요.
    1. 이를 위한 웹페이지를 만들고 서버에 경로를 추가해도 됨

### DB관리

1. DB에 관한 함수들을 database.py에서 합시다.
2. 처음 서비스를 시작하고 DB파일이 없을시 빈 DB데이터를 만드세요

## 폴더 트리 구성

### docker내라고 가정

```
WORKDIR = /app
/app

|-/utils
|--selenium_utils.py
|--security.py
|--logger.py
|--database.py
|-/dist
|--/public
|---이미지나 기타 정적 파일들
|--작업환경 내 web폴더의 dist를 따름
|-/data
|--DB
|--암호화 키.key → 키가 필요하게 프로젝트가 구성되면 이 경로로 넣을 것
|-/logs
|--/서버가켜진 {YYYYMMDD}
|---/system
|----log{n}.log
|---/user
|----/{user_id}
|-----log{n}.log
|----/users
|-----log{n}.log
|-/shFILES -> 필요시
|--*.sh 
|-main.py → FASTAPI SERVER
|-automation.py → 실제 서비스
|-start.sh -> 기존 도커 내리고 리빌드하고 올리는 등의 모든 작업 자동화(필요시 권한 설정도)
|-entrypoint.sh -> 필요시 작성
------------------
여기 나오는 이름들은 필요시 변경해도 됨. 필요시 해당 구조를 변경해도 됨. 단 효율적일 경우에만 변경할 것
```

### 작업환경 내

```
/(도커의 내용과 동일)
/web(웹관련 원본 파일들)
/docker-compose.yml
/Dockerfile
/.gitignore
/requirements.txt
-----------------
이름과 경로들은 필요시 변경해도 됨
```

## 도커 구성(Dockerfile, docker-compose)

컨테이너 명: hanyang-automation

파이썬: 3.12-slim

마운트해야할 데이터:

1. 로그 파일들 전부
2. DB

네트워크: traefik-net(external:true)

라벨:

```
      - "traefik.enable=true"
      - "traefik.http.routers.hanyang-learning.rule=Host(`hanyang.newme.dev`)"
      - "traefik.http.routers.hanyang-learning.entrypoints=web,websecure"
      - "traefik.http.routers.hanyang-learning.tls.certresolver=letsencrypt"
      - "traefik.http.services.hanyang-learning.loadbalancer.server.port=8000"
```

유저 및 그룹 아이디: 호스트와 동일하게(읽고 쓸 때 권한 문제를 방지하기 위함)(이상이 없다면 수정 및 생략 가능)

크롬 및 크롬드라이버 다운 받는 경로:

- 최신 안정화 버전 확인하기: https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE →$STABLE
- 최신 안정화 크롬 설치하기: [https://storage.googleapis.com/chrome-for-testing-public/{$STABLE}/linux64/chrome-linux64.zip](https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.92/linux64/chrome-linux64.zip)
- 최신 안정화 크롬 드라이버 설치하기: [https://storage.googleapis.com/chrome-for-testing-public/{$STABLE}/linux64/chromedriver-linux64.zip](https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.92/linux64/chromedriver-linux64.zip)

## 권한 구성

1. 기본적으로 읽고 쓰고 실행하는데 아무문제 없게 만들기
2. 마운트한 파일들 때문에 문제 발생하지 않게 하기
3. 파일, 디렉토리의 읽기/쓰기/실행 권한에 문제 없도록 설정
4. 마운트한 파일이나 로그/DB 디렉토리에 접근 시 권한 오류 발생하지 않도록 조치

## 기억해야할 것

1. 이 밖에 필요하다고 생각하는 행동들은 서비스의 작동 및 동작에 영향을 미치 않는 선에서 수행해도 된다.

## **보안·프라이버시 가이드라인**

1. 기본적인 보안은 해결해라(SQL INJECTION,CSRF/XSS 방어 등 코드 내의 보안 결함은 전부다)
2. .dev도메인을 사용하기에 HTTPS를 사용할 것이다. 이를 위해 해당 프로젝트에서 취해야할 조치가 있다면 취하여라
3. 인증서 발급 등을 여기서 해야한다면 해라. Traefik에서 자동으로 해야하는 것, 즉 이 프로젝트의 소관이 아닌 경우는 하지 마라.

## **아키텍처 다이어그램**

기본적으로 hanyang.newme.dev에서 오는 요청은 Traefik에서 해당 서비스로 넘겨주는 리버스 프록싱 방식이다.

## **개발 환경 & 코드 규칙**

파이썬: 3.12

## 로그 구성

로그 폴더의 구성

```
|-/logs
|--/서버가켜진 {YYYYMMDD}
|---/system
|----log{n}.log
|---/user
|----/{user_id}
|-----log{n}.log
|----/users
|-----log{n}.log
```

1. 로그 종류 구분 잘해라.
2. 모든 print는 로그로 치환해라.
3. 로그의 작성
    1. 시간(서울 시간대)
    2. 로그의 주체(system, user:id)
    3. 로그의 종류(INFO, WARN etc….)
    4. 로그의 내용

필요시 해당 지침을 프로젝트 및 작동에 영향이 안가는 선에서 수정하여 수행해도 됨

---
'''