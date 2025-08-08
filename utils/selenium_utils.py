from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import uuid
from selenium.webdriver.chrome.service import Service

def init_driver() -> webdriver.Chrome:
    """
    웹 드라이버 초기화 함수
    """
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chrome"
    service = Service(executable_path="/usr/bin/chromedriver")

    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(f"--user-data-dir=/app/data/chrome_user_data/{uuid.uuid4()}")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
 
    return webdriver.Chrome(service=service, options=chrome_options)

def obj_click(driver: webdriver.Chrome, css_selector: str, wait_time: int = 3, times: int = 2) -> bool:
    """
    오브젝트 클릭 함수
    Args:
        driver: 웹 드라이버
        css_selector: 오브젝트 선택자
        wait_time: 대기 시간
        times: 클릭 시도 횟수
    Returns:
        bool: 클릭 성공 여부
    """
    try:
        element_present = EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
        WebDriverWait(driver, wait_time).until(element_present)
        try:
            time.sleep(0.1)
            driver.find_element(By.CSS_SELECTOR, css_selector).click()
            return True
        except Exception:
            # 1회 즉시 재시도 후 실패 처리
            try:
                time.sleep(0.2)
                driver.find_element(By.CSS_SELECTOR, css_selector).click()
                return True
            except Exception:
                pass
    except Exception:
        pass
    # 재귀 재시도: 반환 누락 버그 수정(반환 연결)
    if times > 0:
        return obj_click(driver, css_selector, wait_time, times - 1)
    return False