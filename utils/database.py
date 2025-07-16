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

# AES 암호화/복호화 키 (실서비스는 환경변수 등 안전한 방식으로 관리)
SECRET_KEY = b'hanyang_secretkey_'  # 16/24/32 bytes

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
        c.execute('INSERT INTO Admin (NUM, ID, PWD_Encrypted) VALUES (1, ?, ?)', ('admin', 'admin'))
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

def add_admin(admin_id, pwd_encrypted):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO Admin (NUM, ID, PWD_Encrypted) VALUES (1, ?, ?)', (admin_id, pwd_encrypted))
    conn.commit()
    conn.close()

def update_admin_pwd(admin_id, pwd_encrypted):
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