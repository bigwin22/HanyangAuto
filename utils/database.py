import os
import sqlite3
from datetime import datetime
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'hanyang.db')

USER_TABLE = '''
CREATE TABLE IF NOT EXISTS User (
    NUM INTEGER PRIMARY KEY AUTOINCREMENT,
    ID TEXT UNIQUE NOT NULL,
    PWD_Encrypted TEXT NOT NULL,
    Created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Status TEXT NOT NULL
);
'''

ADMIN_TABLE = '''
CREATE TABLE IF NOT EXISTS Admin (
    NUM INTEGER PRIMARY KEY,
    ID TEXT UNIQUE NOT NULL,
    PWD_Encrypted TEXT NOT NULL,
    Modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''

LEARNED_LECTURE_TABLE = '''
CREATE TABLE IF NOT EXISTS Learned_Lecture (
    Account_ID INTEGER NOT NULL,
    Lecture_ID TEXT NOT NULL,
    PRIMARY KEY (Account_ID, Lecture_ID),
    FOREIGN KEY (Account_ID) REFERENCES User(NUM)
);
'''

# AES 암호화/복호화 키
# Docker Secret 경로 (/run/secrets/hanyang_master_key) 또는 환경변수(DB_SECRET_KEY_BASE64)만 허용
DOCKER_SECRET_PATH_DEFAULT = "/run/secrets/hanyang_master_key"

def _try_decode_base64_maybe(data: bytes) -> bytes:
    try:
        # validate=True로 엄격한 Base64 판별
        decoded = base64.b64decode(data.strip(), validate=True)
        # 성공했고 디코딩 결과가 비어있지 않으면 사용
        if decoded:
            return decoded
    except Exception:
        pass
    return data


def load_or_generate_key():
    """
    마스터 키 로드 우선순위
    1) Docker Secret 파일 (/run/secrets/hanyang_master_key 또는 환경변수 HANYANG_MASTER_KEY_FILE)
    2) 환경변수(DB_SECRET_KEY_BASE64)

    주의: 신규 키 자동 생성은 하지 않습니다. (재부팅 후 불변 요구 충족 및 운영자 접근 억제)
    """
    # 1) Docker Secret 파일
    secret_path = os.getenv("HANYANG_MASTER_KEY_FILE", DOCKER_SECRET_PATH_DEFAULT)
    try:
        if os.path.exists(secret_path):
            with open(secret_path, 'rb') as f:
                raw = f.read()
            key = _try_decode_base64_maybe(raw)
            if len(key) in (16, 24, 32):
                return key
            # 길이가 맞지 않아도 AES는 16/24/32만 허용하므로 명시 오류
            raise RuntimeError("Invalid Docker secret key length. Expect 16/24/32 bytes or base64 of that.")
    except Exception:
        # 비정상 파일 접근/권한 문제 등은 다음 경로로 폴백
        pass

    # 2) 환경변수 (base64)
    env_key_b64 = os.getenv('DB_SECRET_KEY_BASE64')
    if env_key_b64:
        try:
            key = base64.b64decode(env_key_b64)
            if len(key) in (16, 24, 32):
                return key
        except Exception:
            pass

    # 신규 키 자동 생성은 금지: 운영 정책상 명시적 Secret 제공 필요
    raise RuntimeError(
        "Master key not found. Provide Docker secret at /run/secrets/hanyang_master_key or set DB_SECRET_KEY_BASE64."
    )

SECRET_KEY = load_or_generate_key()

# 비밀번호 암호화 함수
def encrypt_password(plain_pwd: str) -> str:
    cipher = AES.new(SECRET_KEY, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plain_pwd.encode('utf-8'), AES.block_size))
    iv = base64.b64encode(cipher.iv).decode('utf-8')
    ct = base64.b64encode(ct_bytes).decode('utf-8')
    return f'{iv}:{ct}'

# 비밀번호 복호화 함수
def decrypt_password(enc_pwd: str) -> str:
    iv, ct = enc_pwd.split(':')
    iv = base64.b64decode(iv)
    ct = base64.b64decode(ct)
    cipher = AES.new(SECRET_KEY, AES.MODE_CBC, iv)
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt.decode('utf-8')

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn

import secrets
import string

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(USER_TABLE)
    c.execute(ADMIN_TABLE)
    c.execute(LEARNED_LECTURE_TABLE)
    conn.commit()
    # 어드민 계정이 없으면 생성
    c.execute('SELECT * FROM Admin WHERE NUM = 1')
    if not c.fetchone():
        from .database import encrypt_password
        admin_password = "admin"
        # print(f"Generated admin password: {admin_password}")
        c.execute('INSERT INTO Admin (NUM, ID, PWD_Encrypted) VALUES (1, ?, ?)', ('admin', encrypt_password(admin_password)))
        conn.commit()
    conn.close()

def add_user(user_id, plain_pwd, status="active"):
    pwd_encrypted = encrypt_password(plain_pwd)
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO User (ID, PWD_Encrypted, Status) VALUES (?, ?, ?)', (user_id, pwd_encrypted, status))
    conn.commit()
    conn.close()

def update_user_pwd(user_id, plain_pwd):
    pwd_encrypted = encrypt_password(plain_pwd)
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE User SET PWD_Encrypted = ? WHERE ID = ?', (pwd_encrypted, user_id))
    conn.commit()
    conn.close()

def update_user_status(user_id, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE User SET Status = ? WHERE ID = ?', (status, user_id))
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM User WHERE ID = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_admin(admin_id, plain_pwd):
    pwd_encrypted = encrypt_password(plain_pwd)
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO Admin (NUM, ID, PWD_Encrypted) VALUES (1, ?, ?)', (admin_id, pwd_encrypted))
    conn.commit()
    conn.close()

def update_admin_pwd(admin_id, plain_pwd):
    pwd_encrypted = encrypt_password(plain_pwd)
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE Admin SET PWD_Encrypted = ?, Modified_at = CURRENT_TIMESTAMP WHERE ID = ?', (pwd_encrypted, admin_id))
    conn.commit()
    conn.close()

def get_admin():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM Admin WHERE NUM = 1')
    admin = c.fetchone()
    conn.close()
    return admin

def add_learned_lecture(account_id, lecture_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO Learned_Lecture (Account_ID, Lecture_ID) VALUES (?, ?)', (account_id, lecture_id))
    conn.commit()
    conn.close()

def get_learned_lectures(account_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT Lecture_ID FROM Learned_Lecture WHERE Account_ID = ?', (account_id,))
    lectures = c.fetchall()
    conn.close()
    return [row[0] for row in lectures]

def delete_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM User WHERE ID = ?', (user_id,))
    conn.commit()
    conn.close()

def delete_user_by_num(user_num):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM User WHERE NUM = ?', (user_num,))
    conn.commit()
    conn.close()

def delete_learned_lectures(account_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM Learned_Lecture WHERE Account_ID = ?', (account_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM User')
    users = c.fetchall()
    conn.close()
    return users

if __name__ == "__main__":
    # DB 및 테이블 생성
    init_db()
    # 테스트 데이터 추가
    try:
        add_user('testuser', 'encrypted_pwd1')
    except Exception as e:
        print(f"User insert error: {e}")
    try:
        add_admin('admin', 'admin')
    except Exception as e:
        print(f"Admin insert error: {e}")
    try:
        user = get_user_by_id('testuser')
        if user:
            add_learned_lecture(user[0], 'lecture_001')
    except Exception as e:
        print(f"Learned_Lecture insert error: {e}")
    print("DB 초기화 및 테스트 데이터 추가 완료.") 