# data 폴더에 '암호화 키.key' 파일이 없으면 32바이트 임의의 값으로 생성 (os.urandom(32)와 같은 역할, 꼭 urandom일 필요 없음)
if [ ! -f "./data/암호화 키.key" ]; then
  echo "'./data/암호화 키.key' 파일이 없어 새로 생성합니다."
  # base64로 32바이트 임의값 생성 (openssl rand 사용, urandom에 의존하지 않음)
  openssl rand -base64 32 | head -c 32 > "./data/암호화 키.key"
fi