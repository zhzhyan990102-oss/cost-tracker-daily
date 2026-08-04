"""最终的生意社现货价格测试 - 自动找最近交易日"""
import akshare as ak
from datetime import date, timedelta

codes = ["RB", "HC", "WR", "SS", "FB", "BB", "PP", "L", "V", "TA", "PF", "CF", "CY", "SP", "RU", "FG"]

# 自动找最近可用交易日（向前最多找10天）
def find_nearest_trading_day(base_date, max_lookback=10):
    for i in range(max_lookback):
        d = base_date - timedelta(days=i)
        try:
            df = ak.futures_spot_price(date=d.strftime("%Y%m%d"), vars_list=codes)
            if len(df) > 0:
                return d, df
        except:
            pass
    return None, None

# 当前价格
cur_date, df_cur = find_nearest_trading_day(date.today())
if df_cur is not None:
    print(f"=== 最近交易日: {cur_date} ({cur_date.strftime('%A')}) ===")
    print(f"列名: {df_cur.columns.tolist()}")
    print()
    for _, row in df_cur.iterrows():
        print(f"  {row['symbol']:4s} {row.get('name', ''):8s} 现货: {row['spot_price']}  期货: {row['dominant_contract_price']}  基差率: {row['dom_basis_rate']}")

# 月前对比（约30天）
m_date, df_m = find_nearest_trading_day(date.today() - timedelta(days=30))
if df_m is not None:
    print(f"\n=== 月前交易日: {m_date} ===")
    print(f"{'品种':6s} {'上月价':>10s} {'当前价':>10s} {'月变化':>8s}")
    for _, row_cur in df_cur.iterrows():
        sym = row_cur['symbol']
        cur_price = float(row_cur['spot_price'])
        row_m = df_m[df_m['symbol'] == sym]
        if not row_m.empty:
            prev_price = float(row_m.iloc[0]['spot_price'])
            change = (cur_price - prev_price) / prev_price * 100
            name = row_cur.get('name', sym)
            print(f"  {sym:4s} {name:8s} {prev_price:>10.0f} {cur_price:>10.0f} {change:>+7.2f}%")
