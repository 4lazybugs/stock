import requests, pandas as pd
from typing import Optional
from bs4 import BeautifulSoup

API_KEY = "3957b81997e850b1a08e448a63e193dd0f630a25"
BASE = "https://opendart.fss.or.kr/api"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def _to_number(x: Optional[str]) -> Optional[float]:
    """문자열을 숫자로 변환"""
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "-", "NaN", "nan", "None"):
        return None
    try:
        return float(s.replace(",", ""))
    except:
        return None

def get_corp_code(api_key: str, stock_code: str) -> str:
    """종목코드로 corp_code 찾기"""
    url = f"{BASE}/corpCode.xml?crtfc_key={api_key}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    
    import io, zipfile, xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        with z.open(z.namelist()[0]) as f:
            tree = ET.parse(f)
    
    root = tree.getroot()
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc == stock_code:
            return (el.findtext("corp_code") or "").strip()
    raise ValueError(f"종목코드 {stock_code} 의 corp_code를 찾지 못함")

def get_financial_data(api_key: str, corp_code: str, year: int, quarter: str = "11014") -> dict:
    """재무 데이터 가져오기 (EPS, ROE, ROA)"""
    result = {"EPS": None, "ROE": None, "ROA": None}
    
    for fs_div in ["CFS", "OFS"]:
        try:
            url = (f"{BASE}/fnlttSinglAcntAll.json?"
                   f"crtfc_key={api_key}&corp_code={corp_code}&bsns_year={year}&reprt_code={quarter}&fs_div={fs_div}")
            r = requests.get(url, headers=HEADERS, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"  {year}년 {quarter}분기 {fs_div} 데이터 요청 실패: {e}")
            continue
        
        if data.get("status") != "000" or not data.get("list"):
            continue
            
        df = pd.DataFrame(data["list"])
        df["account_nm"] = df["account_nm"].astype(str)
        
        # EPS (기본주당이익)
        eps_mask = df["account_nm"].str.contains(r"기본\s*주당\s*(?:이익|순이익)", case=False, regex=True)
        if eps_mask.any():
            row = df.loc[eps_mask].iloc[0]
            val = _to_number(row.get("thstrm_amount"))
            if val is not None and result["EPS"] is None:
                result["EPS"] = val
        
        # ROE (자기자본이익률)
        roe_mask = df["account_nm"].str.contains(r"자기자본\s*이익률|ROE", case=False, regex=True)
        if roe_mask.any():
            row = df.loc[roe_mask].iloc[0]
            val = _to_number(row.get("thstrm_amount"))
            if val is not None and result["ROE"] is None:
                result["ROE"] = val
        
        # ROA (총자산이익률)
        roa_mask = df["account_nm"].str.contains(r"총자산\s*이익률|ROA", case=False, regex=True)
        if roa_mask.any():
            row = df.loc[roa_mask].iloc[0]
            val = _to_number(row.get("thstrm_amount"))
            if val is not None and result["ROA"] is None:
                result["ROA"] = val
        
        # ROE, ROA가 없으면 계산
        if result["ROE"] is None:
            net_income_mask = df["account_nm"].str.contains(r"당기순이익\(손실\)", case=False, regex=True)
            equity_mask = df["account_nm"].str.contains(r"자본총계", case=False, regex=True)
            
            if net_income_mask.any() and equity_mask.any():
                net_income = _to_number(df.loc[net_income_mask].iloc[0].get("thstrm_amount"))
                equity = _to_number(df.loc[equity_mask].iloc[0].get("thstrm_amount"))
                if net_income and equity and equity != 0:
                    result["ROE"] = (net_income / equity) * 100
        
        if result["ROA"] is None:
            net_income_mask = df["account_nm"].str.contains(r"당기순이익\(손실\)", case=False, regex=True)
            total_assets_mask = df["account_nm"].str.contains(r"자산총계", case=False, regex=True)
            
            if net_income_mask.any() and total_assets_mask.any():
                net_income = _to_number(df.loc[net_income_mask].iloc[0].get("thstrm_amount"))
                total_assets = _to_number(df.loc[total_assets_mask].iloc[0].get("thstrm_amount"))
                if net_income and total_assets and total_assets != 0:
                    result["ROA"] = (net_income / total_assets) * 100
    
    return result

def get_quarterly_financial_data(api_key: str, stock_code: str, year: int) -> dict:
    """분기별 누적 재무 데이터 가져오기"""
    quarters = {
        "11011": "1분기",
        "11012": "2분기", 
        "11013": "3분기",
        "11014": "4분기"
    }
    
    quarterly_data = {}
    
    for quarter_code, quarter_name in quarters.items():
        try:
            corp_code = get_corp_code(api_key, stock_code)
            financial_data = get_financial_data(api_key, corp_code, year, quarter_code)
            
            quarterly_data[quarter_name] = {
                "EPS": financial_data.get("EPS"),
                "ROE": financial_data.get("ROE"),
                "ROA": financial_data.get("ROA")
            }
            
        except Exception as e:
            print(f"  {year}년 {quarter_name} 데이터 수집 실패: {e}")
            quarterly_data[quarter_name] = {
                "EPS": None,
                "ROE": None, 
                "ROA": None
            }
    
    return quarterly_data

def get_financial_series(api_key: str, stock_code: str, start_year=2015, end_year=2025) -> pd.DataFrame:
    """연도별 재무 데이터 수집"""
    corp_code = get_corp_code(api_key, stock_code)
    print(f"corp_code: {corp_code}")
    
    rows = []
    for year in range(start_year, end_year + 1):
        print(f"수집 중: {year}년")
        
        if year >= 2015:
            financial_data = get_financial_data(api_key, corp_code, year)
            financial_data["year"] = year
        else:
            financial_data = {
                "year": year,
                "EPS": None, "ROE": None, "ROA": None
            }
        
        rows.append(financial_data)
    
    return pd.DataFrame(rows).set_index("year").sort_index()

def get_quarterly_financial_series(api_key: str, stock_code: str, start_year=2015, end_year=2025) -> pd.DataFrame:
    """분기별 누적 재무 데이터 수집"""
    print(f"분기별 누적 재무 데이터 수집 시작: {stock_code}")
    
    all_data = []
    
    for year in range(start_year, end_year + 1):
        print(f"\n{year}년 분기별 데이터 수집 중...")
        
        quarterly_data = get_quarterly_financial_data(api_key, stock_code, year)
        
        for quarter_name, data in quarterly_data.items():
            row = {
                "year": year,
                "quarter": quarter_name,
                "EPS": data.get("EPS"),
                "ROE": data.get("ROE"),
                "ROA": data.get("ROA")
            }
            all_data.append(row)
    
    df = pd.DataFrame(all_data)
    df["year_quarter"] = df["year"].astype(str) + "_" + df["quarter"]
    df = df.set_index("year_quarter")
    
    return df

if __name__ == "__main__":
    STOCK = "005930"  # 삼성전자
    
    print("=== 연간 재무 데이터 ===")
    annual_df = get_financial_series(API_KEY, STOCK, 2023, 2023)
    print(annual_df)
    
    print("\n=== 분기별 누적 재무 데이터 ===")
    quarterly_df = get_quarterly_financial_series(API_KEY, STOCK, 2023, 2023)
    print(quarterly_df)
    
    # 파일 저장
    annual_out = f"Financial_Annual_{STOCK}_2023.csv"
    quarterly_out = f"Financial_Quarterly_{STOCK}_2023.csv"
    
    annual_df.to_csv(annual_out, encoding="utf-8-sig")
    quarterly_df.to_csv(quarterly_out, encoding="utf-8-sig")
    
    print(f"\n저장 완료:")
    print(f"- 연간 데이터: {annual_out}")
    print(f"- 분기별 데이터: {quarterly_out}")