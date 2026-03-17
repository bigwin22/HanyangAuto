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
    # Docker 환경에 최적화된 Chrome 옵션을 설정합니다.
    chrome_options.binary_location = "/opt/chrome/chrome"
    chrome_options.add_argument("--headless=new")  # GUI 없이 실행
    chrome_options.add_argument("--no-sandbox")  # Sandbox 프로세스 비활성화 (컨테이너 환경 필수)
    chrome_options.add_argument("--disable-dev-shm-usage")  # /dev/shm 대신 /tmp 사용
    chrome_options.add_argument("--disable-gpu")  # GPU 가속 비활성화
    chrome_options.add_argument("--window-size=1920,1080")  # 창 크기 지정

    # 자동화 탐지 회피 옵션
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # ChromeDriver 서비스 경로를 명시적으로 설정합니다.
    service = Service(executable_path="/opt/chromedriver/chromedriver")
 
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