#!/bin/bash
# 서버에서 배포를 실행하는 스크립트

# 에러 발생 시 즉시 중단
set -e

# --- 사용자 설정 필요한 부분 ---
PROJECT_DIR=${PROJECT_DIR} # 깃허브 액션에서 환경변수로 입력할 것이다.
DOCKER_IMAGE=${DOCKER_IMAGE} # 2. 실제 Docker Hub 이미지 주소로 수정하세요. 깃허브 액션에서 환경변수로 입력할 것이다.
# --------------------------

echo "배포를 시작합니다..."

# 1. 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR" || { echo "프로젝트 디렉토리를 찾을 수 없습니다: $PROJECT_DIR"; exit 1; }

# 3. Docker Hub에서 최신 이미지를 가져옴
echo "Docker Hub에서 최신 이미지를 가져옵니다: $DOCKER_IMAGE"
docker pull "$DOCKER_IMAGE"

# 4. Docker Compose로 서비스 재시작
echo "Docker Compose로 서비스를 재시작합니다..."
docker-compose down --remove-orphans -v
docker-compose up -d --pull always --no-build

echo "배포가 성공적으로 완료되었습니다."
