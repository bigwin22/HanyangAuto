from utils.selenium_utils import init_driver, obj_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

def login(driver: webdriver.Chrome, id: str, pwd: str) -> dict:
    """
    로그인 함수
    """
        # 로그인 페이지로 이동  
    driver.get("https://learning.hanyang.ac.kr/")

    try:
        login_button = EC.presence_of_element_located((By.CSS_SELECTOR, "#login_btn"))
        WebDriverWait(driver, 10).until(login_button)
        # 로그인 버튼 클릭
        driver.find_element(By.CSS_SELECTOR, "#uid").send_keys(id)
        driver.find_element(By.CSS_SELECTOR, "#upw").send_keys(pwd)

        obj_click(driver, "#login_btn")  # 로그인 버튼 클릭
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.accept()
        except Exception as e:
            pass

        return {"login": True, "msg": "로그인 성공"}
        # 로그인 버튼 클릭
    except Exception as e:
        return {"login": False, "msg": f"로그인 실패: {e}"}

def get_cources() -> list:
    """
    강의 목록 가져오기
    """
    return []

def get_lectures() -> list:
    """
    강의 목록 가져오기
    """
    return []

def learn_lecture() -> dict:
    """
    강의 학습 함수
    """
    success = False
    msg = ""

    if success:
        msg = "강의 학습 성공"
    else:
        msg = "강의 학습 실패"

    return {"learn": success, "msg": msg}


if __name__ == "__main__":
    driver = init_driver()
    print(login(driver, "kth88", "Noohackingplz08!"))
    # get_cources()
    # get_lectures()
    # learn_lecture()
