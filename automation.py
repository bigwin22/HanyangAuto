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
def learn_lecture(driver: webdriver.Chrome, lecture_url: str) -> dict[str, bool | str]:
    """
    강의 학습 함수
    강의 URL을 받아 해당 강의를 학습하고 완료 여부를 반환합니다.
    :param driver: Selenium WebDriver 인스턴스
    :param lecture_url: 학습할 강의의 URL
    :return: 학습 완료 여부와 메시지를 포함한 딕셔너리
    :rtype: dict
    1. 강의 URL로 이동합니다.
    2. tool_content iframe으로 전환합니다.
    3. 강의가 PDF 형식인지 확인하고, 완료 상태를 확인합니다.
    4. PDF 강의가 아닐 경우 동영상 강의로 전환하고 학습을 시작합니다.
    5. 학습 완료 여부를 확인하고, 완료되면 True, 아니면 False를 반환합니다.
    6. 예외가 발생하면 학습 실패 메시지를 반환합니다.
    7. 학습 완료 메시지를 반환합니다.
    8. 학습 완료 여부와 메시지를 포함한 딕셔너리를 반환합니다.
    """
    driver.get(lecture_url)
    ##tool_content iframe으로 전환
    try:
        WebDriverWait(driver, 2).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#tool_content"))
        )
    except Exception as e:
        return {"learn": False, "msg": f"툴 컨텐츠 프레임 전환 실패: {e}"}

    try:
        WebDriverWait(driver, 0.5).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#root > div > div.xnlail-pdf-component > div.xnbc-progress-info-container > span:nth-child(2)"))
        ) #pdf강의일 경우
        complete_status = driver.find_elements(By.CSS_SELECTOR, "#root > div > div.xnlail-pdf-component > div.xnbc-progress-info-container > span:nth-child(2)")
        if complete_status and "완료" == complete_status[0].text:
            return {"learn": True, "msg": f"이미 완료된 강의: {lecture_url}"}
        progress_button = driver.find_element(By.CSS_SELECTOR, "#root > div > div.xnlail-pdf-component > div.xnvc-progress-info-container > button")
        progress_button.click()
            
    except Exception as e: # pdf 강의가 아닐 경우(예: 동영상 강의)
        try:
            WebDriverWait(driver, 0.5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnlailvc-commons-container > iframe"))
            )
        except Exception as e:
            return {"learn": False, "msg": f"동영상 강의 프레임 전환 실패: {e}"}
        # 동영상 강의 시작 버튼 클릭
        obj_click(driver,"#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div") # 동영상 강의 시작 버튼 클릭
        try:
            ##confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-ok-btn.confirm-btn 클릭해보고 안되면
            ##confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-cancel-btn.confirm-btn 클릭
            WebDriverWait(driver, 0.5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-ok-btn.confirm-btn"))
            )# 확인 버튼이 나타날 때까지 기다리기(이어 듣기에 관한 팝업)
            WebDriverWait(driver, 0.5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-ok-btn.confirm-btn"))
            )# 확인 버튼이 클릭 가능할 때까지 기다리기
            driver.find_element(By.CSS_SELECTOR, "#confirm-dialog > div > div > div.confirm-btn-wrapper > div.confirm-ok-btn.confirm-btn").click()
        except Exception as e:
            return {"learn": False, "msg": f"동영상 강의 요소 없음: {e}"}
        # 이전 iframe으로 돌아가기
        driver.switch_to.default_content()
        try:
            WebDriverWait(driver, 0.5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#tool_content"))
            )#수강 진행도 업데이트를 위해 전환함
        except Exception as e:
            return {"learn": False, "msg": f"툴 컨텐츠 프레임 전환 실패: {e}"}
        while True:
            try:
                WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > span:nth-child(3) > span"))
                )
                WebDriverWait(driver, 0.5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > button"))
                )
            except Exception as e:
                return {"learn": False, "msg": f"동영상 강의 진행 상태 요소 없음: {e}"}
            complete_status = driver.find_elements(By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > span:nth-child(3) > span")
            if complete_status and "완료" == complete_status[0].text:
                break
            progress_button = driver.find_element(By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > button")
            progress_button.click()

    return {"learn": True, "msg": f"강의 학습 완료: {lecture_url}"}

if __name__ == "__main__":
    driver = init_driver()
    print(login(driver, "kth88", "Noohackingplz08!"))
    for lecture in get_lectures(driver, get_cources(driver)):
        print(learn_lecture(driver, lecture), '\n' + lecture)
    driver.quit()
