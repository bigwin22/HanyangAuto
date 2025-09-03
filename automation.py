from typing import Dict, List, Union
from utils.selenium_utils import init_driver, obj_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


def login(driver: webdriver.Chrome, id: str, pwd: str, logger=None) -> Dict[str, Union[bool, str]]:
    """
    한양대학교 Learning Management System에 로그인합니다.
    
    Args:
        driver (webdriver.Chrome): Selenium Chrome WebDriver 인스턴스
        id (str): 로그인 아이디
        pwd (str): 로그인 비밀번호
        logger (Optional): 로그 기록용 객체
    
    Returns:
        Dict[str, Union[bool, str]]: 로그인 성공 여부와 메시지를 포함한 딕셔너리
            - login (bool): 로그인 성공 여부
            - msg (str): 로그인 결과 메시지
    
    Raises:
        Exception: 로그인 과정에서 발생하는 모든 예외를 처리하여 실패 메시지로 반환
    """
    # 로그인 페이지로 이동  
    driver.get("https://learning.hanyang.ac.kr/")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#login_btn"))
        )
        # 로그인 버튼 클릭
        driver.find_element(By.CSS_SELECTOR, "#uid").send_keys(id)
        driver.find_element(By.CSS_SELECTOR, "#upw").send_keys(pwd)

        obj_click(driver, "#login_btn")  # 로그인 버튼 클릭
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            if logger:
                logger.info('login', f'로그인 팝업: {alert_text}')
            alert.accept()
            # 로그인 성공 여부를 #global_nav_profile_link 요소로 검증
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#global_nav_profile_link"))
                )
            except Exception as e:
                if logger:
                    logger.error('login', f'로그인 실패: 프로필 링크 없음 ({e})')
                return {"login": False, "msg": "로그인 실패: 프로필 링크 없음"}
        except Exception as e:
            pass
        if logger:
            logger.info('login', '로그인 성공')
        return {"login": True, "msg": "로그인 성공"}
        # 로그인 버튼 클릭
    except TimeoutException:
        if logger:
            logger.error('login', '로그인 페이지 로드 실패: 시간 초과')
        return {"login": False, "msg": "로그인 페이지 로드 실패: 시간 초과"}
    except NoSuchElementException as e:
        if logger:
            logger.error('login', f'로그인 요소 찾기 실패: {e}')
        return {"login": False, "msg": f"로그인 요소 찾기 실패: {e}"}
    except Exception as e:
        if logger:
            logger.error('login', f'로그인 실패: {e}')
        return {"login": False, "msg": f"로그인 실패: {e}"}

def get_courses(driver: webdriver.Chrome) -> List[str]:
    """
    대시보드에서 등록된 강의 목록을 가져옵니다.
    
    Args:
        driver (webdriver.Chrome): Selenium Chrome WebDriver 인스턴스
    
    Returns:
        List[str]: 강의 ID 목록. 각 강의의 고유 식별자가 포함됩니다.
                   오류 발생 시 빈 리스트를 반환합니다.
    
    Note:
        - 대시보드 카드 컨테이너에서 강의 링크를 찾아 ID를 추출합니다.
        - 각 강의의 URL에서 마지막 부분을 강의 ID로 사용합니다.
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
        ) # 대시보드 카드 컨테이너가 로드될 때까지 기다리기
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
        return [] # 오류 발생 시 빈 리스트 반환

def get_lectures(driver: webdriver.Chrome, course_list: List[str]) -> List[str]:
    """
    각 강의에서 수강하지 않은 개별 강의 목록을 가져옵니다.
    
    Args:
        driver (webdriver.Chrome): Selenium Chrome WebDriver 인스턴스
        course_list (List[str]): 강의 ID 목록
    
    Returns:
        List[str]: 수강하지 않은 개별 강의 URL 목록
                   완료되지 않은 강의만 포함됩니다.
    
    Note:
        - 각 강의의 외부 도구 페이지로 이동하여 강의 목록을 확인합니다.
        - iframe 내부의 강의 목록을 탐색하여 완료되지 않은 강의만 필터링합니다.
        - 예외 발생 시 해당 강의는 건너뛰고 다음 강의로 진행합니다.
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
def learn_lecture(driver: webdriver.Chrome, lecture_url: str) -> Dict[str, Union[bool, str]]:
    """
    개별 강의를 자동으로 수강하고 완료합니다.
    
    Args:
        driver (webdriver.Chrome): Selenium Chrome WebDriver 인스턴스
        lecture_url (str): 수강할 강의의 URL
    
    Returns:
        Dict[str, Union[bool, str]]: 수강 완료 여부와 메시지를 포함한 딕셔너리
            - learn (bool): 수강 완료 여부
            - msg (str): 수강 결과 메시지
    
    Note:
        강의 유형에 따라 다른 처리 방식을 사용합니다:
        - PDF 강의: 진행 상태를 확인하고 완료 버튼을 클릭
        - 동영상 강의: 비디오 플레이어를 시작하고 완료될 때까지 대기
        
        처리 과정:
        1. 강의 URL로 이동
        2. tool_content iframe으로 전환
        3. 강의 형식 확인 (PDF 또는 동영상)
        4. 각 형식에 맞는 수강 진행
        5. 완료 상태 확인 및 결과 반환
    
    Raises:
        Exception: 각 단계에서 발생하는 예외를 처리하여 실패 메시지로 반환
    """
    driver.get(lecture_url)
    ##tool_content iframe으로 전환
    try:
        WebDriverWait(driver, 2).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#tool_content"))
        )
    except NoSuchElementException as e:
        return {"learn": False, "msg": f"요소를 찾을 수 없음: {e}"}
    except TimeoutException:
        return {"learn": True, "msg": "기타 강의로 간주됨"}
    except Exception as e:
        return {"learn": False, "msg": f"툴 컨텐츠 프레임 전환 실패: {e}"}

    try:
        #이건 iframe이 아니라 단순 span입니다. frame_to_be_available_and_switch_to_it은 iframe 요소에만 써야 하며 여기선 잘못된 로직입니다. 라는 의견 있음
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
                pass # 확인 버튼이 없으면 그냥 넘어감
            # 이전 iframe으로 돌아가기
            driver.switch_to.default_content()
            try:
                WebDriverWait(driver, 0.5).until(
                    EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "#tool_content"))
                )#수강 진행도 업데이트를 위해 전환함
            except Exception as e:
                return {"learn": False, "msg": f"수강 진행도 확인을 위한 툴 컨텐츠 프레임 전환 실패: {e}"}
            while True:
                try:
                    WebDriverWait(driver, 0.5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > span:nth-child(3)"))
                    )
                    WebDriverWait(driver, 0.5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > button"))
                    )
                except Exception as e:
                    return {"learn": False, "msg": f"동영상 강의 진행 확인 상태 요소 없음: {e}"}
                complete_status = driver.find_elements(By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > span:nth-child(3)")
                if complete_status and "완료" == complete_status[0].text:
                    break
                progress_button = driver.find_element(By.CSS_SELECTOR, "#root > div > div.xnlail-video-component > div.xnvc-progress-info-container > button")
                progress_button.click()

        except Exception as e:
            pass # 동영상 강의가 아닐 경우(단순 파일 강의 일 가능성이 있음)
            #return {"learn": False, "msg": f"동영상 강의 프레임 전환 실패: {e}"}

    return {"learn": True, "msg": f"강의 학습 완료: {lecture_url}"}

def run_user_automation(user_id: str, pwd: str, learned_lectures: list, db_add_learned):
    """
    한 유저의 전체 자동 강의 수강 프로세스 실행
    Args:
        user_id (str): 한양대 로그인 ID
        pwd (str): 로그인 비밀번호
        learned_lectures (list): 이미 수강한 강의 URL 목록
        db_add_learned (callable): (account_id, lecture_id)로 DB에 수강 완료 기록하는 함수
    Returns:
        dict: {'success': bool, 'msg': str, 'learned': list}
    """
    from utils.selenium_utils import init_driver
    from utils.logger import HanyangLogger
    from utils.database import update_user_status
    driver = None
    user_logger = HanyangLogger('user', user_id=str(user_id))
    try:
        try:
            update_user_status(user_id, "active")  # Status 컬럼 사용
        except Exception as e:
            user_logger.error('automation', f'상태 업데이트 실패: {e}')
        try:
            driver = init_driver()
        except Exception as e:
            user_logger.error('automation', f'드라이버 초기화 실패: {e}')
            try:
                update_user_status(user_id, "error")  # Status 컬럼 사용
            except Exception as e2:
                user_logger.error('automation', f'상태 업데이트 실패: {e2}')
            return {'success': False, 'msg': f'드라이버 초기화 실패: {e}', 'learned': []}
        # 로그인 최대 2회 시도
        login_result = login(driver, user_id, pwd, logger=user_logger)
        if not login_result.get('login'):
            user_logger.info('login', f'1차 로그인 실패: {login_result.get("msg", "로그인 실패")}, 재시도')
            login_result = login(driver, user_id, pwd, logger=user_logger)
            if not login_result.get('login'):
                user_logger.error('login', f'2차 로그인 실패: {login_result.get("msg", "로그인 실패")}, 자동화 중단')
                try:
                    update_user_status(user_id, "error")
                except Exception as e2:
                    user_logger.error('automation', f'상태 업데이트 실패: {e2}')
                return {'success': False, 'msg': login_result.get('msg', '로그인 실패'), 'learned': []}
        user_logger.info('automation', '강의 목록 조회 시작')
        course_list = get_courses(driver)
        if not course_list:
            user_logger.info('automation', '강의 목록 없음')
            try:
                update_user_status(user_id, "completed")
            except Exception as e2:
                user_logger.error('automation', f'상태 업데이트 실패: {e2}')
            return {'success': False, 'msg': '강의 목록 없음', 'learned': []}
        lecture_list = get_lectures(driver, course_list)
        # 중복 수강 방지
        to_learn = [lec for lec in lecture_list if lec not in learned_lectures]
        learned = []
        for lec_url in to_learn:
            user_logger.info('lecture', f'강의 수강 시작: {lec_url}')
            result = learn_lecture(driver, lec_url)
            if result.get('learn'):
                user_logger.info('lecture', f'강의 수강 완료: {lec_url}')
                learned.append(lec_url)
                db_add_learned(user_id, lec_url)
            else:
                user_logger.error('lecture', f'강의 수강 실패: {lec_url} ({result.get("msg", "")})')
                try:
                    update_user_status(user_id, "error")
                except Exception as e2:
                    user_logger.error('automation', f'상태 업데이트 실패: {e2}')
                return {'success': False, 'msg': f'강의 수강 실패: {lec_url} ({result.get("msg", "")})', 'learned': learned}
        # 모든 강의가 정상적으로 완료된 경우에만
        try:
            update_user_status(user_id, "completed")
        except Exception as e2:
            user_logger.error('automation', f'상태 업데이트 실패: {e2}')
        return {'success': True, 'msg': f'{len(learned)}개 강의 수강 완료', 'learned': learned}
    except Exception as e:
        user_logger.error('automation', f'자동화 오류: {e}')
        try:
            update_user_status(user_id, "error")
        except Exception as e2:
            user_logger.error('automation', f'상태 업데이트 실패: {e2}')
        return {'success': False, 'msg': f'자동화 오류: {e}', 'learned': []}
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                user_logger.error('automation', f'드라이버 종료 실패: {e}')

if __name__ == "__main__":
    # 아래 코드는 테스트 목적으로만 사용해야 합니다.
    # 실제 운영 환경에서는 민감한 정보를 코드에 직접 포함하지 마세요.
    # 예: driver = init_driver()
    #     print(login(driver, "your_test_id", "your_test_password"))
    #     driver.quit()
    pass