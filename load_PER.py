import requests, pandas as pd
from typing import Optional
from bs4 import BeautifulSoup

API_KEY = "3957b81997e850b1a08e448a63e193dd0f630a25"
BASE = "https://opendart.fss.or.kr/api"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def _to_number(x: Optional[str]) -> Optional[float]:
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

def get_stock_price(stock_code: str, year: int) -> Optional[float]:
    """네이버 금융에서 현재 주가 가져오기"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 현재 주가 찾기
        price_element = soup.find('p', class_='no_today')
        if price_element:
            price_text = price_element.find('span', class_='blind').text
            return float(price_text.replace(',', ''))
        
        return None
    except Exception as e:
        print(f"  {year}년 주가 데이터 가져오기 실패: {e}")
        return None

def get_financial_data(api_key: str, corp_code: str, year: int) -> dict:
    """JSON API로 재무 데이터 가져오기 (EPS, PER, PBR, ROE, ROA)"""
    result = {"EPS": None, "PER": None, "PBR": None, "ROE": None, "ROA": None}
    
    for fs_div in ["CFS", "OFS"]:
        try:
            url = (f"{BASE}/fnlttSinglAcntAll.json?"
                   f"crtfc_key={api_key}&corp_code={corp_code}&bsns_year={year}&reprt_code=11011&fs_div={fs_div}")
            r = requests.get(url, headers=HEADERS, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"  {year}년 {fs_div} 데이터 요청 실패: {e}")
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
        
        # PER (주가수익비율) - 직접 계산 불가, 주가 데이터 필요
        # PBR (주가순자산비율) - 직접 계산 불가, 주가 데이터 필요
        
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
        
        # ROE, ROA가 없으면 계산해보기
        if result["ROE"] is None:
            # 당기순이익 / 자본총계
            net_income_mask = df["account_nm"].str.contains(r"당기순이익\(손실\)", case=False, regex=True)
            equity_mask = df["account_nm"].str.contains(r"자본총계", case=False, regex=True)
            
            if net_income_mask.any() and equity_mask.any():
                net_income = _to_number(df.loc[net_income_mask].iloc[0].get("thstrm_amount"))
                equity = _to_number(df.loc[equity_mask].iloc[0].get("thstrm_amount"))
                if net_income and equity and equity != 0:
                    result["ROE"] = (net_income / equity) * 100
        
        if result["ROA"] is None:
            # 당기순이익 / 자산총계
            net_income_mask = df["account_nm"].str.contains(r"당기순이익\(손실\)", case=False, regex=True)
            total_assets_mask = df["account_nm"].str.contains(r"자산총계", case=False, regex=True)
            
            if net_income_mask.any() and total_assets_mask.any():
                net_income = _to_number(df.loc[net_income_mask].iloc[0].get("thstrm_amount"))
                total_assets = _to_number(df.loc[total_assets_mask].iloc[0].get("thstrm_amount"))
                if net_income and total_assets and total_assets != 0:
                    result["ROA"] = (net_income / total_assets) * 100
    
    return result

def get_financial_series(api_key: str, stock_code: str, start_year=2015, end_year=2025) -> pd.DataFrame:
    """연도별 재무 데이터 수집 (EPS, PER, PBR, ROE, ROA)"""
    corp_code = get_corp_code(api_key, stock_code)
    print(f"corp_code: {corp_code}")
    
    rows = []
    for year in range(start_year, end_year + 1):
        print(f"수집 중: {year}년")
        
        # 2015년 이후는 JSON API 사용
        if year >= 2015:
            financial_data = get_financial_data(api_key, corp_code, year)
            financial_data["year"] = year
            
            # 주가 데이터 가져와서 PER, PBR 계산
            stock_price = get_stock_price(stock_code, year)
            if stock_price and financial_data["EPS"]:
                # PER = 주가 / EPS
                financial_data["PER"] = stock_price / financial_data["EPS"]
                
                # PBR 계산을 위해 BPS (주당순자산) 필요
                # BPS = 자본총계 / 발행주식수 (발행주식수는 별도 API 필요)
                # 일단 PER만 계산하고 PBR은 None으로 두기
                financial_data["PBR"] = None
        else:
            financial_data = {
                "year": year,
                "EPS": None, "PER": None, "PBR": None, "ROE": None, "ROA": None
            }
        
        rows.append(financial_data)
    
    return pd.DataFrame(rows).set_index("year").sort_index()

if __name__ == "__main__":
    STOCK = "005930"  # 삼성전자
    df = get_financial_series(API_KEY, STOCK, 2015, 2023)
    print(df)
    
    out = f"Financial_{STOCK}_2015_2023.csv"
    df.to_csv(out, encoding="utf-8-sig")
    print(f"저장 완료: {out}")