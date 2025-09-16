from audioop import add
import pandas as pd
import os

def unify_index(index_list, date_type):
    """
    index_list: datetime-like 리스트
    date_type: 'year' | 'month' | 'day' | 'week'
    """
    idx = pd.DatetimeIndex(index_list)
    if date_type == "week":
        # 주 시작(월요일)로 내림해서 키 생성 (예: 2025-06-02~08 -> '25-06-02')
        wk_start = idx.to_period("W-MON").start_time
        return wk_start.strftime("%y-%m-%d").tolist()
    fmt = {"year": "%y", "month": "%y-%m", "day": "%y-%m-%d"}[date_type]
    return idx.strftime(fmt).tolist()


def add_col(df_orig, df_add, date_type):
    df_orig = df_orig.copy()

    # 인덱스 -> 키 리스트 변환
    orig_index_list = df_orig.index.to_list()
    add_index_list  = df_add.index.to_list()

    orig_key_list = unify_index(orig_index_list, date_type)
    add_key_list  = unify_index(add_index_list,  date_type)

    if date_type == "week":
        # 같은 주는 같은 키로 매칭: add의 주단위 값으로 orig의 해당 주(월~일) 채움
        key_to_row = {k: j for j, k in enumerate(add_key_list)}  # 마지막 값 우선
        for i, o_key in enumerate(orig_key_list):
            j = key_to_row.get(o_key)
            if j is None:
                continue
            for col in df_add.columns:
                df_orig.loc[orig_index_list[i], col] = df_add.iloc[j][col]
        return df_orig

    # day/month/year는 기존 방식 그대로
    for i, o_key in enumerate(orig_key_list):
        for j, a_key in enumerate(add_key_list):
            if o_key == a_key:
                for col in df_add.columns:
                    df_orig.loc[orig_index_list[i], col] = df_add.iloc[j][col]

    return df_orig

if __name__ == "__main__":
    stk_pth = "./stk_data/ship_stock_prices.xlsx"
    df_stk = pd.read_excel(stk_pth, header=0, index_col=0)
    df_stk.index = pd.to_datetime(df_stk.index).date 
    
    
    ship_pth = "./economic_data/new_tanker_ship_price_20250604_20250914.xlsx"
    ecos_pth = "./economic_data/usd_krw_20250704_20251102.xlsx"
    add_dic = [("ecos", "day", ecos_pth), ("ship_price", "week", ship_pth)]

    fname = "ship_stock_prices"
    for add_name, date_type, add_pth in add_dic:
        df_add = pd.read_excel(add_pth, header=0, index_col=0)
        df_stk = add_col(df_stk, df_add, date_type=date_type)
        fname = fname + f"_{add_name}"
    fname = fname + ".xlsx"
    
    df_stk.to_excel(f"./stk_data/{fname}.xlsx")
    print(f"{fname}.xlsx 저장 완료")

