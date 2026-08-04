# 🏠 家居类目成本跟盘日报系统

跨境电商家居类目原材料成本自动化跟踪与钉钉播报系统。

## 功能概述

- **每日 8:00（北京时间）** 自动采集原材料现货价格
- **钉钉群聊机器人** 推送精要播报（仅重点波动 + 宏观情报）
- **完整明细链接** 可点击查看全部材料变动明细
- 覆盖 **国内7省 + 海外6国** 供应链成本追踪

## 供应链覆盖

| 产地 | 品类 | 核心原材料 |
|------|------|-----------|
| 🇨🇳 广东 | 置物架、衣橱架、落地衣架 | 冷轧板卷、热轧板卷、管材 |
| 🇨🇳 广西 | 落地衣架 | 冷轧板卷、管材 |
| 🇨🇳 福建 | 板式家具、床架 | 刨花板、中纤板MDF |
| 🇨🇳 江苏 | 钢木类家具 | 冷轧板卷、热轧板卷、刨花板 |
| 🇨🇳 浙江 | 塑料制品、软体床垫、地毯 | PP/PE/PVC、TDI/MDI、涤纶 |
| 🇨🇳 山东 | 置物架 | 冷轧板卷、热轧板卷 |
| 🇨🇳 天津 | 海绵床垫、地毯 | TDI/MDI、涤纶、丙纶BCF |
| 🇻🇳 越南 | 钢木类、布抽类、钢木床 | 钢材、涤纶、人造板 |
| 🇰🇭 柬埔寨 | 置物架 | 钢材、刨花板 |
| 🇲🇾 马来西亚 | 床架 | 刨花板、MDF |
| 🇲🇦 摩洛哥 | 床垫 | TDI/MDI、聚醚多元醇、涤纶 |
| 🇯🇴 约旦 | 床垫 | TDI/MDI、聚醚多元醇、涤纶 |
| 🇵🇰 巴基斯坦 | 床垫 | TDI/MDI、聚醚多元醇、涤纶 |

## 技术架构

```
数据采集层 → 数据处理层 → 报告生成层 → 钉钉推送层
   (AkShare)   (标准化/趋势/映射)   (Markdown)   (Webhook)
```

- **数据源**：AkShare（生意社现货价格）+ 国家统计局 PPI + Mysteel/鱼珠木材（备选）
- **调度**：GitHub Actions（公开仓库无限免费分钟）
- **推送**：钉钉群聊机器人 Markdown + FeedCard

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/cost-tracker-daily.git
cd cost-tracker-daily
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置钉钉 Webhook

在 GitHub 仓库 `Settings → Secrets and variables → Actions` 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook 完整 URL |
| `DINGTALK_SECRET` | 钉钉机器人加签密钥（SEC开头） |

### 4. 本地测试

```bash
# Windows PowerShell
$env:DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
$env:DINGTALK_SECRET = "SEC_YOUR_SECRET"
python -m src.main
```

### 5. 启用定时运行

Push 到 GitHub 后，系统将每天自动运行。也可在 Actions 页面手动触发 `Daily Cost Tracking Report` workflow。

## 项目结构

```
cost-tracker-daily/
├── .github/workflows/
│   ├── daily-report.yml      # 日报调度 workflow
│   └── keep-alive.yml        # 防60天过期
├── src/
│   ├── main.py               # 总入口
│   ├── collectors/           # 数据采集器
│   ├── processors/           # 数据处理（标准化/趋势/映射/情报）
│   ├── reporters/            # 报告生成（Markdown/FeedCard）
│   ├── pushers/dingtalk.py   # 钉钉推送
│   ├── config/               # YAML 配置文件
│   └── utils/                # 工具（重试/缓存/日志）
├── reports/                  # 每日完整明细（自动生成）
├── cache/                    # 历史价格缓存
└── requirements.txt
```

## 日报示例

钉钉群收到的精要播报：

```markdown
🏠 家居类目成本跟盘日报
2026-07-31（周五）

📊 宏观大盘
PPI -1.2% | CPI +0.9% | USDCNH 7.2510

⚡ 重点原材料波动
- 🔴 TDI ↑5.20% | 17,680 元/吨 | 影响：天津·海绵床垫
- 🟡 冷轧板卷 ↑2.15% | 4,520 元/吨 | 影响：广东·置物架

🚢 跨境情报
- ℹ️ USD/CNH 7.2510（贬值0.15%）

📎 完整明细
> 点击查看完整材料变动明细
```

## 维护说明

- **价格锚点**：每月更新 `src/config/price_anchors.yaml` 中的基准价格
- **法定节假日**：每年初更新 `src/config/holidays.yaml`
- **成本权重**：按季度review `src/config/materials_mapping.yaml` 中的成本权重系数

## 许可证

MIT
