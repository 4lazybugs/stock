import os
import requests
import pandas as pd
from pprint import pprint

def save_ecos(static_code: str, period: str, \
              start_date: str, end_date :str, table_code: str, table_name: str ):
    API_KEY = '5O3QUZG5ICSESDI650G2'
    start_idx = 1
    end_idx = 100000 # 10만일이면 270년 정도 되므로 이정도 하드 코딩은 상관없음
    language = 'kr'
    RETURN_TYPE = "json"
    
    url_base = "https://ecos.bok.or.kr/api/StatisticSearch/"
    path_params = f"{API_KEY}/{RETURN_TYPE}/{language}/{start_idx}/{end_idx}/{static_code}/{period}/{start_date}/{end_date}/{table_code}"
    url = url_base + path_params

    resp = requests.get(url, timeout=20)
    data = resp.json()

    data = data['StatisticSearch']['row']
    data = pd.DataFrame(data)

    df_data = data[['TIME', 'DATA_VALUE']].copy()
    df_data['date'] = pd.to_datetime(df_data['TIME'], format="%Y%m%d")
    df_data[f'{table_name}'] = df_data['DATA_VALUE']

    # 컬럼 정리
    df_data = df_data[['date', f'{table_name}']].sort_values('date')
    
    start_date = start_date.replace("-", "")
    end_date = end_date.replace("-", "")

    save_dir = "./economic_data"
    os.makedirs(save_dir, exist_ok=True)

    fname = f"{table_name}_{start_date}_{end_date}"
    save_path = os.path.join(save_dir, f"{fname}.xlsx")
    with pd.ExcelWriter(save_path, engine="xlsxwriter", 
                        datetime_format="yyyy-mm-dd") as writer:
        df_data.to_excel(writer, index=False)
    
    print(f"{fname}.xlsx 저장 완료 : {save_path}")


if __name__ == "__main__":

    static_code = '731Y001' # 환율 통계
    period = 'D' 
    start_date = "20200304"
    end_date = "20230402"
    table_code = "0000001" # 원 달러 환율
    table_name = "usd_krw"

    save_ecos(static_code, period, start_date, end_date, table_code, table_name)

