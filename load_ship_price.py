from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import date
from pathlib import Path
import pandas as pd
import glob, os, time


def setup_driver(download_dir: str, headless: bool = True):
    """크롬 드라이버 초기화"""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1920,1080")
    prefs = {"download.default_directory": download_dir}
    opts.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=opts)


def download_file(driver, url: str, start_date: str, end_date: str, \
                  ship_type: str = "TANKER",wait_sec: int = 3):
    """사이트 접속 후 파일 다운로드"""
    driver.get(url)
    wait = WebDriverWait(driver, wait_sec)

    # 드롭다운 대신 직접 탭 선택 (TANKER / BULKER)
    option = wait.until(EC.element_to_be_clickable(
        (By.XPATH, f"//li[contains(@class,'sts')]/a[normalize-space(text())='{ship_type.upper()}']")))
    option.click()
    time.sleep(wait_sec)

    start_input = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//label[contains(.,'시작일')]/following::input[1]")
    ))
    end_input = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//label[contains(.,'종료일')]/following::input[1]"))
    )

    driver.execute_script("""
        arguments[0].value = arguments[2];
        arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
        arguments[1].value = arguments[3];
        arguments[1].dispatchEvent(new Event('input', {bubbles:true}));
        arguments[1].dispatchEvent(new Event('change', {bubbles:true}));
    """, start_input, end_input, start_date, end_date)

    search_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@class='calSearch' and @type='submit']")))
    search_btn.click()
    time.sleep(wait_sec)

    download_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button.fDown.m1")))
    download_btn.click()
    time.sleep(wait_sec)


def process_file(download_dir: str, start_date: str, end_date: str):
    """다운로드된 TANKER 파일을 xlsx로 변환 후 원본 삭제"""
    files = glob.glob(os.path.join(download_dir, f"{ship_type}*"))
    if not files:
        raise FileNotFoundError(f"{ship_type} 파일을 찾을 수 없습니다.")
    fpath = files[0]
    
    df = pd.read_excel(fpath, header=1).set_index("DATE")
    df = df.drop(columns=['번호'])

    save_dir = "./economic_data"
    os.makedirs(save_dir, exist_ok=True)

    start_date = start_date.replace("-", "")
    end_date = end_date.replace("-", "")
    
    fname = f"{release_type['name']}_{ship_type}_ship_price_{start_date}_{end_date}"
    save_path = os.path.join(save_dir, f"{fname}.xlsx")
    
    df.to_excel(save_path, index=True, header=True)

    os.remove(fpath)

    print(f"{release_type['name']} 저장 완료 : {save_path}")


if __name__ == "__main__":    
    old_ship = {'code' :'0402000000', 'name' : "used"} # 중고선가
    new_ship = {'code' : '0401000000', 'name' : "new"} # 신고선가
    # 중고선가 / 신고선가 선택
    release_type = new_ship

    bulk_ship = "bulker"
    tank_ship = "tanker"
    # BULKER(곡물, 석탄, 철광) / TANKER(원유, 석유제품, 액체 화물) 선택
    ship_type = tank_ship

    start_date = date(2016, 8, 4).strftime("%Y-%m-%d")
    end_date = date(2024, 9, 14).strftime("%Y-%m-%d")

    url_base = "https://www.kobc.or.kr/ebz/shippinginfo/sts/gridList.do?mId="
    url = url_base + release_type['code']
    down_dir = r"C:\Users\LG\OneDrive\Desktop\창고\Stock Price Prediction\src"

    driver = setup_driver(down_dir, headless=True)
    try:
        download_file(driver, url, start_date, end_date)
    finally:
        driver.quit()

    process_file(down_dir, start_date, end_date)