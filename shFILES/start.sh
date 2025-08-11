#!/bin/bash
# 서버에서 배포를 실행하는 스크립트

# 에러 발생 시 즉시 중단
set -e

# 필수 환경 변수 확인 (GitHub Actions 또는 실행 환경에서 주입되어야 함)
if [ -z "${PROJECT_DIR:-}" ]; then echo "PROJECT_DIR 환경 변수가 필요합니다"; exit 1; fi
if [ -z "${DOCKER_IMAGE:-}" ]; then echo "DOCKER_IMAGE 환경 변수가 필요합니다"; exit 1; fi
if [ -z "${DOMAIN:-}" ]; then echo "DOMAIN 환경 변수가 필요합니다"; exit 1; fi
if [ -z "${CONTAINER_NAME:-}" ]; then echo "CONTAINER_NAME 환경 변수가 필요합니다"; exit 1; fi
if [ -z "${PORT:-}" ]; then echo "PORT 환경 변수가 필요합니다"; exit 1; fi

# Docker Compose 프로젝트 이름을 환경별로 고유하게 설정
export COMPOSE_PROJECT_NAME="${CONTAINER_NAME}"
echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}"

echo "배포를 시작합니다..."

# 1. 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR" || { echo "프로젝트 디렉토리를 찾을 수 없습니다: $PROJECT_DIR"; exit 1; }

# 3. Docker Hub에서 최신 이미지를 가져옴
echo "Docker Hub에서 최신 이미지를 가져옵니다: $DOCKER_IMAGE"
docker pull "$DOCKER_IMAGE"

# 4. Docker Compose로 서비스 재시작
echo "Docker Compose로 서비스를 재시작합니다... (project: ${COMPOSE_PROJECT_NAME})"
docker-compose -p "${COMPOSE_PROJECT_NAME}" down --remove-orphans -v
docker-compose -p "${COMPOSE_PROJECT_NAME}" up -d --pull always --no-build

echo "배포가 성공적으로 완료되었습니다."
