from typing import Dict, List, Union
from utils.selenium_utils import init_driver, obj_click
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from utils.selenium_utils import init_driver
from utils.logger import HanyangLogger
from utils.database import update_user_status
from utils.worker_util import *

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
            result = learn_lecture(driver, lec_url, user_id)
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

