#!/bin/bash
# 서버에서 배포를 실행하는 스크립트

# 에러 발생 시 즉시 중단
set -e



#파일 및 환경변수 ###############
# .env 파일이 없으면 생성하고, 환경 변수들을 기록

# logs와 data 폴더가 없으면 생성
[ -d "./logs" ] || mkdir ./logs
[ -d "./data" ] || mkdir ./data

# data 폴더에 '암호화 키.key' 파일이 없으면 32바이트 임의의 값으로 생성 (os.urandom(32)와 같은 역할, 꼭 urandom일 필요 없음)
if [ ! -f "./data/암호화 키.key" ]; then
  echo "'./data/암호화 키.key' 파일이 없어 새로 생성합니다."
  # base64로 32바이트 임의값 생성 (openssl rand 사용, urandom에 의존하지 않음)
  openssl rand -base64 32 | head -c 32 > "./data/암호화 키.key"
fi

cat <<EOF > "$PROJECT_DIR/.env"
DOCKER_IMAGE=${DOCKER_IMAGE}
DOMAIN=${DOMAIN}
CONTAINER_NAME=${CONTAINER_NAME}
PORT=${PORT}
DB_ENCRYPTION_KEY_B64=$(base64 < ./data/암호화\ 키.key)
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$CONTAINER_NAME}"
EOF


# Docker Compose 프로젝트 이름을 환경별로 고유하게 설정
export CONTAINER_NAME="${CONTAINER_NAME}"
echo "CONTAINER_NAME=${CONTAINER_NAME}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$CONTAINER_NAME}"
echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}"

echo "배포를 시작합니다..."

# 1. 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR" || { echo "프로젝트 디렉토리를 찾을 수 없습니다: $PROJECT_DIR"; exit 1; }

# 3. Docker Hub에서 최신 이미지를 가져옴
echo "Docker Hub에서 최신 이미지를 가져옵니다: $DOCKER_IMAGE"
docker pull "$DOCKER_IMAGE"

# 4. Docker Compose로 서비스 재시작
echo "Docker Compose로 서비스를 재시작합니다... (project: ${COMPOSE_PROJECT_NAME})"

# (안전장치) 동일 이름의 컨테이너가 남아있으면 강제 제거
EXISTING=$(docker ps -aq -f name="^/${CONTAINER_NAME}$" || true)
if [ -n "$EXISTING" ]; then
  echo "기존 컨테이너(${CONTAINER_NAME})를 제거합니다: $EXISTING"
  docker rm -f "$CONTAINER_NAME" || true
fi



# 외부 네트워크가 없다면 생성 (traefik-net)
docker network inspect traefik-net >/dev/null 2>&1 || docker network create traefik-net || true

docker-compose -p "${COMPOSE_PROJECT_NAME}" down --remove-orphans -v || true
docker-compose -p "${COMPOSE_PROJECT_NAME}" up -d --pull always --no-build

echo "배포가 성공적으로 완료되었습니다."
