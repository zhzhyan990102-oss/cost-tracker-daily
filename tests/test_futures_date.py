"""查看生意社现货价格数据和日期"""
import akshare as ak
from datetime import date, timedelta

codes = ["RB", "HC", "WR", "SS", "FB", "BB", "PP", "L", "V", "TA", "PF", "CF", "CY", "SP", "RU", "FG"]

# 今天
today = date.today()
print(f"=== 今天: {today} ===")
try:
    df = ak.futures_spot_price(date=today.strftime("%Y%m%d"), vars_list=codes)
    print(f"返回 {len(df)} 行")
    print(df[["date", "symbol", "spot_price"]].to_string())
except Exception as e:
    print(f"错误: {e}")

# 30天前对比
d30 = today - timedelta(days=30)
print(f"\n=== 30天前: {d30} ===")
try:
    df30 = ak.futures_spot_price(date=d30.strftime("%Y%m%d"), vars_list=codes)
    print(f"返回 {len(df30)} 行")
    print(df30[["date", "symbol", "spot_price"]].to_string())
except Exception as e:
    print(f"错误: {e}")
