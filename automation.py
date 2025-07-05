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

def get_cources(driver: webdriver.Chrome) -> list:
    """
    강의 목록 가져오기
    """
    course_list = []
    try:
        EC.presence_of_element_located((By.CSS_SELECTOR, "#primaryNavToggle"))
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#primaryNavToggle"))
        )
        EC.presence_of_element_located((By.CSS_SELECTOR, "#DashboardCard_Container > div > div"))
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#DashboardCard_Container > div > div"))
        )
        elements = driver.find_elements(By.CSS_SELECTOR, "#DashboardCard_Container > div > div")
        for element in elements:
            try:
                href_element = element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                if href_element:
                    href = href_element.split("/")[-1]
                else:
                    continue
                course_list.append(href)
            except Exception as e:
                pass    
        return course_list
    except Exception as e:
        return []

def get_lectures(driver: webdriver.Chrome, course_list: list) -> list:
    """
    강의 목록 가져오기
    """
    lecture_list = []
    for course in course_list:
        driver.get("https://learning.hanyang.ac.kr/" + "courses/" + course + "/external_tools/140")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#section-tabs > li:nth-child(3) > a"))
            )
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#tool_content"))
            )
            WebDriverWait(driver,10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#root > div > div > div > div:nth-child(2) > div"))
            )#frame전환후 프레임 내 요소 인식 기다리기
            lectures = driver.find_elements(By.CSS_SELECTOR, "#root > div > div > div > div:nth-child(2) > div")
            for lecture in lectures:
                try:
                    a = lecture.find_element(By.CSS_SELECTOR, "div > div.xnmb-module_item-left-wrapper > div > div.xnmb-module_item-meta_data-left-wrapper > div > a")
                    href = a.get_attribute("href")
                    learned = lecture.find_elements(By.CSS_SELECTOR, "div > div.xnmb-module_item-right-wrapper > span.xnmb-module_item-completed.completed")
                    if not learned:
                        lecture_list.append(href)
                except Exception as e:
                    pass
        except Exception as e:
            continue
    return lecture_list
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
    print(get_cources(driver))
    print(len(get_lectures(driver, get_cources(driver))))
    # learn_lecture()
    driver.quit()
