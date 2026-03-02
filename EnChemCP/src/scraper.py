import asyncio
import os
import shutil
from pathlib import Path

import nodriver as uc
from nodriver import Browser, Tab

from src.utils import get_config, setup_logger

logger = setup_logger(__name__)

# 시스템 URL 및 인증 정보
FINANCE_SYSTEM_URL = get_config("FINANCE_SYSTEM_URL")
SSO_ID = get_config("SSO_ID")
SSO_PW = get_config("SSO_PW")

# 다운로드 디렉토리 설정 (운영체제에 따라 다를 수 있음, 기본적으로 nodriver는 시스템 기본 다운로드 폴더 사용)
# 파일 이동을 위한 다운로드 폴더 경로 (Mac 기준)
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads"

class FinanceScraper:
    def __init__(self, target_dir: Path):
        self.browser: Browser = None
        self.tab: Tab = None
        self.target_dir = target_dir

    async def initialize(self):
        """nodriver 브라우저 초기화"""
        logger.info("Initializing nodriver browser...")
        try:
            self.browser = await uc.start(
                headless=False, # SSO 로그인 등을 위해 False 권장, 안정화 후 True 검토
                browser_args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            self.tab = self.browser.main_tab
            logger.info("Browser initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def login_sso(self):
        """SSO 연동 로그인 처리"""
        if not FINANCE_SYSTEM_URL or not SSO_ID or not SSO_PW:
            logger.error("Missing SSO credentials or URL in environment variables.")
            raise ValueError("SSO credentials missing.")

        logger.info(f"Navigating to {FINANCE_SYSTEM_URL}")
        try:
            await self.tab.get(FINANCE_SYSTEM_URL)
            await self.tab.sleep(3) # 로딩 대기

            # TODO: 실제 사이트의 DOM 요소 ID/클래스에 맞게 수정 필요
            logger.info("Attempting to input SSO credentials.")
            
            # 아이디 입력 (예시: input element id 'userId')
            # element_id = await self.tab.select('#userId') 
            # await element_id.send_keys(SSO_ID)
            
            # 비밀번호 입력 (예시: input element id 'password')
            # element_pw = await self.tab.select('#password')
            # await element_pw.send_keys(SSO_PW)

            # 로그인 버튼 클릭 (예시: button element id 'btnLogin')
            # btn_login = await self.tab.select('#btnLogin')
            # await btn_login.click()
            
            # 로그인 완료 대기
            # await self.tab.sleep(5) 
            logger.info("[Mock] SSO Login sequence complete (requires exact DOM selectors).")
            
        except Exception as e:
            logger.error(f"Error during SSO login: {e}")
            raise

    async def download_report(self, report_type: str):
        """
        특정 리포트(요약손익계산서/월별손익계산서) 조회 및 다운로드.
        
        Args:
            report_type (str): 'week' (요약손익계산서) 또는 'month' (월별손익계산서)
        """
        logger.info(f"Starting download process for report type: {report_type}")
        try:
            # 1. 대상 메뉴 이동
            # await self.tab.get("리포트_경로_URL")
            # await self.tab.sleep(2)
            
            # 2. 조회 조건 설정 (예: 날짜 세팅 등)
            
            # 3. 조회 버튼 클릭
            # btn_search = await self.tab.select('#btnSearch')
            # await btn_search.click()
            # await self.tab.sleep(3) # 데이터 로딩 대기
            
            # 4. 엑셀 다운로드 버튼 클릭
            logger.info("Clicking Excel download button...")
            # btn_excel = await self.tab.select('#btnExcelDownload')
            # await btn_excel.click()
            
            # 다운로드 완료 대기 (파일 생성 시간 등 고려)
            # await self.tab.sleep(5)
            logger.info(f"[Mock] Report ({report_type}) download initiated.")
        except Exception as e:
            logger.error(f"Error downloading report ({report_type}): {e}")
            raise

    def move_downloaded_file(self, expected_prefix: str, final_filename: str):
        """
        다운로드 폴더에서 새로 생성된 파일을 찾아 대상 폴더로 이동.
        
        Args:
            expected_prefix (str): 다운로드될 파일의 접두사 (예: '요약손익계산서')
            final_filename (str): 저장할 최종 파일 이름
        """
        logger.info(f"Looking for downloaded file with prefix '{expected_prefix}'...")
        try:
            # 다운로드 폴더에서 expected_prefix로 시작하는 가장 최근 파일 찾기
            files = list(DEFAULT_DOWNLOAD_DIR.glob(f"{expected_prefix}*.xlsx"))
            if not files:
                logger.error(f"No downloaded file found matching prefix '{expected_prefix}'.")
                raise FileNotFoundError(f"File {expected_prefix}*.xlsx not found in {DEFAULT_DOWNLOAD_DIR}")
            
            # 가장 최근에 생성된 파일 선택
            latest_file = max(files, key=os.path.getctime)
            
            dest_path = self.target_dir / final_filename
            
            # 목적지 디렉토리 보장
            os.makedirs(dest_path.parent, exist_ok=True)
            
            logger.info(f"Moving file from {latest_file} to {dest_path}")
            shutil.move(str(latest_file), str(dest_path))
            
            logger.info("File successfully moved.")
            
        except Exception as e:
            logger.error(f"Failed to move downloaded file: {e}")
            raise

    async def close(self):
        """브라우저 자원 반환"""
        if self.browser:
            logger.info("Closing browser...")
            self.browser.stop()
            logger.info("Browser closed.")

async def run_scraper(target_date_type: str, target_dir: Path):
    """
    Scraper 모듈 메인 실행 함수.
    
    Args:
        target_date_type (str): 'week' 또는 'month'
        target_dir (Path): 데이터가 저장될 대상 디렉토리 경로
    """
    scraper = FinanceScraper(target_dir=target_dir)
    try:
        await scraper.initialize()
        await scraper.login_sso()
        
        if target_date_type == "week":
            await scraper.download_report("week")
            scraper.move_downloaded_file("요약손익계산서", "요약손익계산서.xlsx")
        elif target_date_type == "month":
            await scraper.download_report("month")
            scraper.move_downloaded_file("월별손익계산서", "월별손익계산서.xlsx")
        else:
            logger.error(f"Unknown target_date_type: {target_date_type}")
            
    except Exception as e:
        logger.error(f"Scraper execution failed: {e}")
        raise
    finally:
        await scraper.close()
