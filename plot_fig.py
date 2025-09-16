import pandas as pd
import os
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, MinMaxScaler

# --- 환율 데이터 ---
fdir = "./economic_data/"
fname = "usd_krw_20160704_20251102.xlsx"
fpth = os.path.join(fdir, fname)
df_ecos = pd.read_excel(fpth)

x_ecos = df_ecos['date']
y_ecos = df_ecos["usd_krw"].values.reshape(-1, 1)

# --- 주가 데이터 ---
fdir = "./stk_data/"
fname = "ship_stock_prices.xlsx"
fpth = os.path.join(fdir, fname)
df_stk = pd.read_excel(fpth)

x_stk = df_stk['date']
y_stk = df_stk['Close'].values.reshape(-1, 1)

# --- 스케일링 ---
scaler = MinMaxScaler()
y_ecos_scaled = scaler.fit_transform(y_ecos).flatten()
y_stk_scaled = scaler.fit_transform(y_stk).flatten()


# --- 시각화 ---
plt.plot(x_ecos, y_ecos_scaled, label="USD/KRW (scaled)")
plt.plot(x_stk, y_stk_scaled, label="Ship Stock (scaled)")

plt.legend()
plt.show()
