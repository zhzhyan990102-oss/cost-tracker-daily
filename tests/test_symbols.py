"""测试所有候选 symbol 在 AkShare 中的可用性"""
import akshare as ak

symbols = [
    "螺纹钢", "热轧卷板", "纤维板", "胶合板", "聚丙烯",
    "聚乙烯", "聚氯乙烯", "短纤", "PTA", "纸浆", "不锈钢", "线材",
    "铜", "铝", "棉花", "棉纱", "玻璃", "天然橡胶", "原木"
]

ok_symbols = []
fail_symbols = []

for s in symbols:
    try:
        df = ak.spot_price_qh(s)
        last = df.iloc[-1]
        date_val = last["日期"]
        price_val = last["现货价格"]
        print(f"  OK: {s:8s} | {date_val} | 现货: {price_val}")
        ok_symbols.append(s)
    except Exception as e:
        msg = str(e)[:100]
        print(f"  FAIL: {s:8s} | {msg}")
        fail_symbols.append(s)

print(f"\n=== 结果: {len(ok_symbols)} OK / {len(fail_symbols)} FAIL ===")
print(f"可用: {ok_symbols}")
print(f"不可用: {fail_symbols}")
