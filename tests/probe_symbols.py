"""探测 AkShare 99qh.com 可用品种"""
import akshare as ak

df = ak.spot_price_table_qh()
print(f"=== 共 {len(df)} 个品种 ===")
print(f"列名: {df.columns.tolist()}")
print()

# 列出所有品种
print("--- 全部品种 ---")
for _, row in df.iterrows():
    name = row["品种名称"]
    print(f"  {name}")

print()
# 筛选家居相关
print("--- 家居相关品种 ---")
keywords = ["钢", "板", "管", "木", "TDI", "MDI", "聚醚", "PP", "PE", "PVC", "涤纶", "无纺", "丙纶", "塑料", "海绵"]
found = set()
for kw in keywords:
    matches = df[df["品种名称"].str.contains(kw, na=False)]
    for _, row in matches.iterrows():
        name = row["品种名称"]
        if name not in found:
            found.add(name)
            print(f"  ✅ {name}")

# 没匹配到的
print()
print("--- 未匹配到的关注品种 ---")
wanted = ["冷轧", "热轧", "中纤板", "刨花板", "TDI", "MDI", "聚醚", "PP", "PE", "PVC", "涤纶", "无纺布", "丙纶", "管材", "无缝管"]
matched = set()
for kw in wanted:
    m = df[df["品种名称"].str.contains(kw, na=False)]
    if m.empty:
        print(f"  ❌ {kw}")
    else:
        matched.add(kw)
for kw in matched:
    print(f"  ✅ {kw} 已匹配")
