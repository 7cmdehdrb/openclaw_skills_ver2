import os
import time
import argparse
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# .env 파일 로드
load_dotenv()
USER_ID = os.getenv("USER_ID")
USER_PW = os.getenv("USER_PW")


def setup_driver():
    options = webdriver.ChromeOptions()

    # Ubuntu 서버 구동을 위한 필수 옵션 (Windows 디버깅 시에는 아래 3줄 주석 처리 가능)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Headless 모드에서 요소 클릭 에러를 방지하기 위해 창 크기 지정
    options.add_argument("window-size=1920x1080")

    # Windows 일반 Chrome User-Agent로 위장
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # 드라이버 자동 다운로드 및 실행
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def main(is_weekend=False, lab_no=49):
    driver = None
    try:
        driver = setup_driver()
        # Explicit Wait (최대 10초 대기)
        wait = WebDriverWait(driver, 10)

        # 1. 메인 페이지 접속
        print("[1] 메인 페이지 접속 중...")
        driver.get("https://safety.ssu.ac.kr/ushm/main/home.do")

        # 2. 리모트 메뉴 3번 클릭
        print("[2] 원격 메뉴 클릭...")
        menu_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "#Integration_remote_area_wrap > div > div > a.remote_menu_3",
                )
            )
        )
        driver.execute_script("arguments[0].click();", menu_btn)

        # 3. 유저 버튼 클릭
        print("[3] 로그인 선택 버튼 클릭...")
        user_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btnUser")))
        driver.execute_script("arguments[0].click();", user_btn)

        # 4. ID / PW 입력
        print("[4] 계정 정보 입력 중...")
        id_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#userid"))
        )
        pw_input = driver.find_element(By.CSS_SELECTOR, "#pwd")

        id_input.send_keys(USER_ID)
        pw_input.send_keys(USER_PW)

        # 5. 로그인 버튼 클릭
        print("[5] 로그인 버튼 클릭...")
        login_btn = driver.find_element(
            By.CSS_SELECTOR,
            "#sLogin > div > div.area_login > form > div > div:nth-child(2) > a",
        )
        driver.execute_script("arguments[0].click();", login_btn)

        # 5.2. 리다이렉션 대기 및 Fallback 처리
        print("[5.2] 로그인 리다이렉션 대기 중...")
        try:
            # 로그인이 완료되어 특정 메인 페이지 요소가 로드되거나 URL이 변경될 때까지 대기
            wait.until(EC.url_changes(driver.current_url))
            time.sleep(2)  # 서버 응답에 따른 안정적인 세션 쿠키 저장을 위해 약간 대기
        except TimeoutException:
            print("리다이렉션 지연 감지. 강제로 메인 홈으로 이동합니다.")
            driver.get("https://safety.ssu.ac.kr/ushm/main/home.do")

        # 6. 세션 유지된 상태로 점검 페이지 이동
        print(f"[6] 일일 점검 페이지 이동 (labNo={lab_no})...")
        driver.get(f"https://safety.ssu.ac.kr/mmbr/check/daily/main.do?labNo={lab_no}")

        # 7. 리스트 내 대상 버튼 클릭
        print("[7] 점검 항목 열기 (DOM 렌더링 대기 중)...")
        try:
            # 페이지의 기본 뼈대(#divList)가 로드될 때까지 대기
            wait.until(EC.presence_of_element_located((By.ID, "divList")))

            # 서버 환경에 따라 내부 테이블 데이터가 AJAX로 뒤늦게 붙을 수 있으므로 강제 대기
            time.sleep(2)

            # CSS Selector 사용 (XPath보다 구조 변화에 상대적으로 강함)
            target_selector = "#divList > div.table_wrap_1200 > table > tbody > tr > td > p > a:nth-child(4)"

            # 요소가 클릭 가능해질 때까지 대기
            check_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, target_selector))
            )
            driver.execute_script("arguments[0].click();", check_btn)
        except TimeoutException:
            print("[-] Step 7 요소를 찾지 못했습니다. Linux 렌더링 상태를 캡처합니다.")
            driver.save_screenshot("step7_error_screenshot.png")
            with open("step7_error_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(
                "[-] 'step7_error_screenshot.png' 및 'step7_error_source.html' 파일이 저장되었습니다."
            )
            raise

        # 8. 모달/팝업 내 작업 수행
        print("[8] 팝업 창 내 테이블 확인 및 Radio 버튼 클릭...")

        # 8.1. 테이블 tbody 확인
        tbody = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#check_tblList > tbody"))
        )

        # 8.2. 내부 tr 모두 찾기
        rows = tbody.find_elements(By.TAG_NAME, "tr")

        # 8.3. GroupChecked가 포함된 tr만 필터링
        target_rows = []
        for row in rows:
            # 해당 tr 내부에 onclick 속성 값으로 'GroupChecked'를 포함하는 요소가 하나라도 있는지 검사
            group_checked_elements = row.find_elements(
                By.XPATH, ".//*[@onclick and contains(@onclick, 'GroupChecked')]"
            )
            if group_checked_elements:
                target_rows.append(row)

        print(f"[*] GroupChecked가 할당된 tr 발견 개수: {len(target_rows)}개")

        # 8.4. 정상적으로 7개가 찾아졌는지 확인 후 로직 수행
        if len(target_rows) == 7:
            for idx, row in enumerate(target_rows):
                try:
                    # --weekend: 전부 4번째 radio
                    if is_weekend:
                        radio = row.find_element(By.XPATH, "./th[4]/input[@type='radio']")
                    else:
                        # 기본 동작: 1~6번째는 2번째, 7번째는 4번째 radio
                        if idx < 6:
                            radio = row.find_element(
                                By.XPATH, "./th[2]/input[@type='radio']"
                            )
                        else:
                            radio = row.find_element(
                                By.XPATH, "./th[4]/input[@type='radio']"
                            )

                    # 체크되어 있지 않은 경우에만 클릭
                    if not radio.is_selected():
                        driver.execute_script("arguments[0].click();", radio)
                except Exception as e:
                    print(f"[-] {idx + 1}번째 대상 처리 중 요소를 찾을 수 없음: {e}")
        else:
            print(
                "[-] 경고: 예상한 대상 개수(7개)와 일치하지 않습니다. 스크립트 구조가 변경되었는지 확인하세요."
            )
            raise RuntimeError(
                f"예상한 대상 개수(7개)와 일치하지 않습니다: {len(target_rows)}개"
            )

        # 8.5. 모든 radio 처리 완료 후 제출 버튼 클릭
        print("[8.5] 저장 버튼 클릭...")
        save_btn_selector = "#frmOn > div > div.popup_btn_set > a.btn.green.popup.mr3"
        save_btn = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, save_btn_selector))
        )
        driver.execute_script("arguments[0].click();", save_btn)

        # 9. 끝!
        print("[9] 모든 작업이 성공적으로 완료되었습니다!")
        time.sleep(2)  # 저장이 서버에 반영될 수 있도록 잠시 대기

    except Exception as e:
        print(f"에러 발생: {e}")
        raise

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weekend",
        action="store_true",
        help="주말 모드: 7개 대상 모두 4번째 th의 radio 선택",
    )
    parser.add_argument(
        "--lab",
        type=int,
        default=49,
        help="점검 대상 실험실 번호(labNo). 예: --lab 30",
    )
    args = parser.parse_args()

    if args.lab < 0:
        parser.error("--lab must be a non-negative integer")

    if args.weekend:
        print("[*] weekend 모드 활성화: 모든 대상에 대해 4번째 radio를 선택합니다.")
    else:
        print("[*] 일반 모드: 1~6번째는 2번째, 7번째는 4번째 radio를 선택합니다.")

    print(f"[*] labNo 설정값: {args.lab}")

    main(is_weekend=args.weekend, lab_no=args.lab)
