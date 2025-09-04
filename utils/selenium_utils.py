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
    웹 드라이버 초기화 함수 (가상 디스플레이 사용)
    """
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chrome"
    service = Service(executable_path="/usr/bin/chromedriver")

    # 가상 디스플레이 설정
    # chrome_options.add_argument("--display=:99")
    # chrome_options.add_argument("--window-size=1920,1080")
    
    # 기본 Chrome 옵션
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
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
        element_present = EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        WebDriverWait(driver, wait_time).until(element_present)
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        # 스크롤 가능한 만큼 PAGE_DOWN 키로 내림

        while True:
            try:
                time.sleep(0.1)
                driver.find_element(By.CSS_SELECTOR, css_selector).click()
                return True
            except Exception as e:
                return False
    except Exception as e:
        if times > 0:
            obj_click(driver, css_selector, wait_time, times - 1)
        else:
            return False
    return False