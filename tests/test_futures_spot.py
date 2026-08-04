"""测试 ak.futures_spot_price 接口 - 生意社每日现货价格"""
import akshare as ak
from datetime import date

# 家居相关品种代码
# RB=螺纹钢 HC=热轧卷板 WR=线材 SS=不锈钢
# FB=纤维板 BB=胶合板
# PP=聚丙烯 L=聚乙烯 V=聚氯乙烯
# TA=PTA PF=短纤 CF=棉花 CY=棉纱
# SP=纸浆 RU=天然橡胶 FG=玻璃
# C=玉米 CS=玉米淀粉

codes = ["RB", "HC", "WR", "SS", "FB", "BB", "PP", "L", "V", "TA", "PF", "CF", "CY", "SP", "RU", "FG"]

today = date.today().strftime("%Y%m%d")
print(f"日期: {today}")
print(f"测试品种: {codes}")
print()

try:
    df = ak.futures_spot_price(date=today, vars_list=codes)
    print(f"列名: {df.columns.tolist()}")
    print(f"行数: {len(df)}")
    print()

    if not df.empty:
        # 检查各品种
        for code in codes:
            row = df[df["var"] == code]
            if not row.empty:
                r = row.iloc[0]
                print(f"  OK: {code:4s} | 商品: {r.get('name', 'N/A'):10s} | 现货价: {r.get('spot_price', 'N/A')} | 日期: {r.get('date', 'N/A')}")
            else:
                print(f"  MISS: {code:4s} | 无数据")
    else:
        print("返回空 DataFrame，尝试前一天日期...")
        from datetime import timedelta
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
        df = ak.futures_spot_price(date=yesterday, vars_list=codes)
        print(f"用昨日日期 {yesterday}: {len(df)} 行")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
