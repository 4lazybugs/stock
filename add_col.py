import os
import io
import zipfile
import datetime
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 공용 세션 + 재시도 설정
def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    retry = Retry(total=5, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

SESSION = make_session()

def date2quart(date_str: str) -> tuple:
    """
    'YYYY.MM.DD' 문자열을 받아서 (연도, reprt_code) 반환
    reprt_code:
      11013 = 1분기 (3월말 기준)
      11012 = 반기 (6월말 기준)
      11014 = 3분기 (9월말 기준)
      11011 = 사업보고서/연간 (12월말 기준)
    """
    dt = datetime.datetime.strptime(date_str, "%Y.%m.%d")
    year = dt.year

    month = dt.month
    if month <= 3:
        return year, "11013"   # 1분기
    elif month <= 6:
        return year, "11012"   # 반기
    elif month <= 9:
        return year, "11014"   # 3분기
    else:
        return year, "11011"   # 사업보고서 (연간)


def stk_to_corp(api_key: str, stk_code: str, xml_path="CORPCODE.xml") -> str:
    # xml 없으면 다운로드
    if not os.path.exists(xml_path):
        url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
        r = SESSION.get(url, timeout=60); r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extract(z.namelist()[0], ".")
            os.rename(z.namelist()[0], xml_path)

    # xml 파싱해서 찾기
    root = ET.parse(xml_path).getroot()
    for el in root.iter("list"):
        if (el.findtext("stock_code") or "").strip() == stk_code:
            return (el.findtext("corp_code") or "").strip()
    raise ValueError(f"{stk_code} 매핑 실패")

def _to_number(x):
    """문자열을 숫자로 변환 (쉼표 제거, None 처리)"""
    if x is None: return None
    s = str(x).replace(",", "").strip()
    try: return float(s)
    except: return None

# XBRL 태그 기반 매칭 패턴
ID_PATTERNS = {
    "EPS_basic": r"ifrs.*BasicEarnings.*PerShare|dart.*BasicEarnings.*PerShare",
    "EPS_diluted": r"ifrs.*DilutedEarnings.*PerShare|dart.*DilutedEarnings.*PerShare",
    "EPS_any": r"Earnings.*PerShare",  # 최후의 보루
}

def get_financial_item(api_key: str, corp_code: str, year: int, col_pattern: str,
                       fs_divs=("CFS","OFS"), report_code: str = None,
                       amount_field: str = "thstrm_amount") -> Optional[float]:
    """
    DART 단일계정 API에서 특정 계정(col_pattern)에 해당하는 금액만 추출
    - col_pattern: 찾고 싶은 계정명(정규식 가능), 예: "기본주당이익", "자기자본이익률", "총자산이익률"
    - amount_field: "thstrm_amount" (당기) 또는 "thstrm_add_amount" (누적)
    - return: 금액 (float) or None
    """
    for fs in fs_divs:
        try:
            url = (f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?"
                   f"crtfc_key={api_key}&corp_code={corp_code}&bsns_year={year}"
                   f"&reprt_code={report_code}&fs_div={fs}")
            r = SESSION.get(url, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"{year}년 {fs} 요청 실패: {e}")
            continue

        if data.get("status") != "000" or not data.get("list"):
            continue

        df = pd.DataFrame(data["list"])
        for col in ("account_nm","account_id"):
            if col not in df: df[col] = ""
            df[col] = df[col].astype(str)

        # 1차: 넓은 한글 정규식
        mask = df["account_nm"].str.contains(col_pattern, case=False, regex=True, na=False)

        # 2차: 태그(account_id)로 기본EPS 우선 탐색
        if not mask.any():
            m_basic = df["account_id"].str.contains(ID_PATTERNS["EPS_basic"], case=False, regex=True, na=False)
            m_dilu  = df["account_id"].str.contains(ID_PATTERNS["EPS_diluted"], case=False, regex=True, na=False)
            m_any   = df["account_id"].str.contains(ID_PATTERNS["EPS_any"], case=False, regex=True, na=False)
            if m_basic.any(): mask = m_basic
            elif m_dilu.any(): mask = m_dilu
            elif m_any.any():  mask = m_any

        # 3차: 그래도 없으면 '주당' 키워드로 완전 보조 탐색
        if not mask.any():
            mask = df["account_nm"].str.contains(r"주당", case=False, regex=True, na=False)

        if mask.any():
            cand = df.loc[mask, ["account_nm","account_id", amount_field]].copy()

            # 우선순위: 기본 > 희석 > 나머지
            cand["prio"] = 2
            cand.loc[cand["account_nm"].str.contains("기본", na=False) |
                     cand["account_id"].str.contains("Basic", case=False, na=False), "prio"] = 0
            cand.loc[cand["account_nm"].str.contains("희석", na=False) |
                     cand["account_id"].str.contains("Diluted", case=False, na=False), "prio"] = 1

            row = cand.sort_values(["prio","account_nm","account_id"]).iloc[0]
            val = _to_number(row.get(amount_field))
            if val is not None and str(val) != "-":
                return val
    return None

if __name__ == "__main__":
    # API key for DART (한국전자공시 시스템 - 지표 다운로드)
    API_KEY = "3957b81997e850b1a08e448a63e193dd0f630a25"

    metrics_patterns = {
        "EPS": r"(기본|희석)\s*주당\s*(?:이익|손실|이익\(손실\)|손실\(이익\)|순이익)",
        #"ROE": r"자기자본\s*이익률|ROE",
        #"ROA": r"총자산\s*이익률|ROA",
    }

    # 조선 관련 주식 code 
    stk_codes = [
        '042660',  # 한화오션 (구 대우조선해양)
        '009540',  # HD한국조선해양
        '010140',  # 삼성중공업
        '010620',  # 현대미포조선
        '329180',  # 현대중공업
        '097230',  # HJ중공업 (구 한진중공업)
        '238490',  # 현대힘스
        '077970',  # STX엔진
        '267250',  # HD현대마린엔진
    ]

    updated_dfs = {}

    for stk_code in stk_codes:
        # corp_code 변환을 루프 밖에서 한 번만 수행
        corp_code = stk_to_corp(API_KEY, stk_code)
        df_stock = pd.read_excel('ship_stock_prices.xlsx', sheet_name=stk_code, index_col=0, header=0)
        
        # 중복 호출 방지 캐시
        cache = {}  # {(year, report_code, metric): value}

        for date in df_stock.index:
            year, report_code = date2quart(date)

            for metric, pattern in metrics_patterns.items():
                key = (year, report_code, metric)
                if key not in cache:
                    # EPS는 분기/반기/3분기에서 누적값 사용
                    amount_field = "thstrm_add_amount" if (metric == "EPS" and report_code != "11011") else "thstrm_amount"
                    val = get_financial_item(API_KEY, corp_code, year, pattern,
                                             report_code=report_code, amount_field=amount_field)
                    cache[key] = val
                else:
                    val = cache[key]

                if metric not in df_stock.columns:
                    df_stock[metric] = pd.NA
                
                df_stock.loc[date, metric] = val
                print(f"[{stk_code}, {date}] {metric} = {val}")

            updated_dfs[stk_code] = df_stock

        # 원본 파일 덮어쓰기
    with pd.ExcelWriter("ship_stock_prices.xlsx", engine="openpyxl", mode="w") as writer:
        for stk_code, df in updated_dfs.items():
            df.to_excel(writer, sheet_name=stk_code)


                