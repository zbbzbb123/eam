# EAM 数据采集层详细文档

> 更新日期: 2025-01-26

---

## 概览

| 分类 | 采集器数量 | 采集方式 |
|------|-----------|---------|
| 结构化 API | 6 | SDK/REST API |
| 爬虫 | 2 | HTML/JSON 解析 |
| **总计** | **8** | |

---

## 一、结构化 API 采集器

### 1. YFinanceCollector (美股行情)

| 属性 | 值 |
|------|-----|
| **名称** | yfinance_collector |
| **数据源** | Yahoo Finance |
| **采集对象** | 美股、ETF 历史行情 |
| **采集频次** | 按需 / 每日收盘后 |
| **采集方式** | yfinance Python SDK |
| **需要认证** | 否 |
| **速率限制** | 无明确限制，建议适度 |

**数据字段:**
- 日期、开盘价、最高价、最低价、收盘价、成交量

**示例标的:** NVDA, VOO, QQQ, GLD, SCHD

---

### 2. AkShareCollector (A股/港股行情)

| 属性 | 值 |
|------|-----|
| **名称** | akshare_collector |
| **数据源** | AkShare (东方财富等) |
| **采集对象** | A股、港股历史行情 |
| **采集频次** | 按需 / 每日收盘后 |
| **采集方式** | AkShare Python SDK |
| **需要认证** | 否 |
| **速率限制** | 无明确限制 |

**数据字段:**
- 日期、开盘价、最高价、最低价、收盘价、成交量

**示例标的:**
- A股: 000001 (平安银行), 600519 (贵州茅台)
- 港股: 00700 (腾讯), 09988 (阿里巴巴)

---

### 3. FREDCollector (美国宏观数据)

| 属性 | 值 |
|------|-----|
| **名称** | fred_collector |
| **数据源** | FRED (美联储经济数据库) |
| **采集对象** | 美国宏观经济指标 |
| **采集频次** | 每日 / 每周 |
| **采集方式** | REST API (httpx async) |
| **需要认证** | 是 (FRED_API_KEY) |
| **速率限制** | 120 requests/minute |
| **API 地址** | https://api.stlouisfed.org/fred/series/observations |

**数据字段:**

| Series ID | 指标名称 | 更新频率 |
|-----------|---------|---------|
| DFII10 | 10年期 TIPS 收益率 | 每日 |
| CPIAUCSL | CPI 消费者物价指数 | 每月 |
| GDP | 国内生产总值 | 每季 |
| UNRATE | 失业率 | 每月 |
| FEDFUNDS | 联邦基金利率 | 每日 |

**使用场景:** 黄金白银分析 (TIPS)、宏观环境判断

---

### 4. NorthboundCollector (北向资金)

| 属性 | 值 |
|------|-----|
| **名称** | northbound_collector |
| **数据源** | AkShare (东方财富) |
| **采集对象** | A股北向资金流向 |
| **采集频次** | 每个交易日 |
| **采集方式** | AkShare Python SDK |
| **需要认证** | 否 |
| **速率限制** | 无明确限制 |

**数据字段:**

1. **每日净流入 (NorthboundFlowData)**
   - trade_date: 交易日期
   - net_flow: 净流入金额 (亿元)
   - quota_remaining: 当日余额 (亿元)

2. **个股持仓变化 (HoldingChangeData)**
   - symbol: 股票代码
   - name: 股票名称
   - holding: 今日持股 (万股)
   - market_value: 参考市值 (亿元)
   - holding_change: 持股变化 (万股)

**使用场景:** 聪明钱追踪、A股情绪指标

---

### 5. SEC13FCollector (机构持仓)

| 属性 | 值 |
|------|-----|
| **名称** | sec13f_collector |
| **数据源** | SEC EDGAR |
| **采集对象** | 美股机构 13F 持仓 |
| **采集频次** | 每季度 (45天内披露) |
| **采集方式** | REST API + XML 解析 (httpx async) |
| **需要认证** | 否 (需要 User-Agent) |
| **速率限制** | 10 requests/second |
| **API 地址** | https://data.sec.gov/submissions/CIK{cik}.json |

**跟踪机构:**

| CIK | 机构名称 |
|-----|---------|
| 0001067983 | Berkshire Hathaway (巴菲特) |
| 0001818482 | ARK Investment (木头姐) |
| 0001350694 | Bridgewater (桥水) |
| 0001037389 | Renaissance Technologies (文艺复兴) |

**数据字段 (InstitutionalHoldingData):**
- institution_cik, institution_name
- report_date: 报告日期
- cusip: 证券标识符
- stock_name: 股票名称
- shares: 持股数量
- value: 持仓市值

**使用场景:** 聪明钱追踪、机构调仓分析

---

### 8. TuShareCollector (A股财务指标)

| 属性 | 值 |
|------|-----|
| **名称** | tushare_collector |
| **数据源** | TuShare Pro |
| **采集对象** | A股估值和财务指标 |
| **采集频次** | 每日 (估值) / 每季 (财务) |
| **采集方式** | TuShare Python SDK |
| **需要认证** | 是 (TUSHARE_TOKEN) |
| **速率限制** | 按积分等级限制 |

**数据字段:**

1. **估值数据 (StockValuationData)**
   - ts_code, trade_date
   - pe, pe_ttm: 市盈率
   - pb: 市净率
   - ps, ps_ttm: 市销率
   - total_mv: 总市值
   - circ_mv: 流通市值
   - turnover_rate: 换手率

2. **财务指标 (StockFinancialsData)**
   - ts_code, ann_date, end_date
   - roe, roe_waa: 净资产收益率
   - roa, roa2: 总资产收益率
   - q_sales_yoy: 营收同比增长
   - q_profit_yoy: 净利润同比增长
   - fcff: 企业自由现金流

3. **历史分位计算**
   - PE/PB 历史百分位 (默认 1 年)

**使用场景:** A股选股、估值分析、财务排雷

---

## 二、爬虫采集器

### 10. JisiluCrawler (A股ETF溢价)

| 属性 | 值 |
|------|-----|
| **名称** | jisilu_crawler |
| **数据源** | 集思录 (jisilu.cn) |
| **采集对象** | A股 ETF 溢价率 |
| **采集频次** | 每日盘中/收盘 |
| **采集方式** | JSON API (httpx) |
| **需要认证** | 否 |
| **速率限制** | 建议间隔 1-2 秒 |
| **目标 URL** | https://www.jisilu.cn/data/etf/etf_list/ |

**数据字段 (ETFPremiumData):**
- fund_id: ETF 代码
- fund_name: ETF 名称
- price: 现价
- net_value: 净值
- estimate_value: 估算值
- premium_rate: 溢价率 (%)
- volume: 成交量
- turnover: 成交额
- nav_date: 净值日期
- index_id, index_name: 跟踪指数

**采集方法:**
- `fetch_etf_premium_data()`: 所有 ETF
- `filter_high_premium(threshold=5)`: 高溢价 (>5%)
- `filter_high_discount(threshold=-5)`: 高折价 (<-5%)

**使用场景:** ETF 套利机会、市场情绪指标

---

### 11. CommodityCrawler (大宗商品价格)

| 属性 | 值 |
|------|-----|
| **名称** | commodity_crawler |
| **数据源** | AkShare + 生意社 (100ppi.com) |
| **采集对象** | 碳酸锂、多晶硅价格 |
| **采集频次** | 每日 |
| **采集方式** | SDK + HTML 爬虫 |
| **需要认证** | 否 |
| **速率限制** | 建议间隔 1-2 秒 |

**数据字段 (CommodityPriceData):**
- commodity_name: 品种名称 (中文)
- commodity_name_en: 品种名称 (英文)
- price: 最新价格
- price_unit: 单位 (元/吨, 元/千克)
- price_change: 价格变动
- price_change_pct: 涨跌幅 (%)
- price_date: 日期
- source: 数据源

**跟踪品种:**

| 品种 | 数据源 | 单位 |
|------|--------|------|
| 碳酸锂 | AkShare (期货现货) | 元/吨 |
| 电池级碳酸锂 | 100ppi.com | 元/吨 |
| 多晶硅 | 100ppi.com | 元/千克 |

**使用场景:** 新能源产业链追踪、上游价格监控

---

## 三、统一接口 (CollectorRegistry)

### CLI 命令

```bash
# 列出所有采集器
python -m src.cli.collect --list

# 查看配置状态
python -m src.cli.collect --status

# 运行单个采集器
python -m src.cli.collect --collector fred

# 运行所有采集器
python -m src.cli.collect --all

# JSON 格式输出
python -m src.cli.collect --collector fred --json
```

### Python API

```python
from src.collectors.registry import get_registry

registry = get_registry()

# 列出所有采集器
for name, info in registry.list_all().items():
    print(f"{name}: {info.description}")

# 运行单个采集器
result = await registry.run("fred")

# 运行所有采集器
results = await registry.run_all()
```

---

## 四、建议采集频次汇总

| 采集器 | 建议频次 | 说明 |
|--------|---------|------|
| YFinance / AkShare | 每日收盘后 | 行情数据 |
| FRED | 每日 | 宏观数据更新较慢 |
| Northbound | 每日 16:00 后 | A股收盘后 |
| SEC 13F | 每季度 | 季度披露 |
| TuShare | 每日 (估值) / 每季 (财务) | |
| Jisilu | 每日盘中 | ETF 溢价 |
| Commodity | 每日 | 大宗商品 |

---

## 五、环境变量配置

```bash
# .env 文件
FRED_API_KEY=your_fred_api_key
TUSHARE_TOKEN=your_tushare_token
```

---

## 六、数据库模型

| 模型 | 对应采集器 | 存储内容 |
|------|-----------|---------|
| MacroData | FREDCollector | 美国宏观指标 |
| NorthboundFlow | NorthboundCollector | 北向资金每日流向 |
| NorthboundHolding | NorthboundCollector | 北向持股明细 |
| InstitutionalHolding | SEC13FCollector | 机构持仓 |

---

## 七、测试覆盖

| 采集器 | 测试数 | 覆盖率 |
|--------|--------|--------|
| FREDCollector | 16 | 完整 |
| NorthboundCollector | 26 | 完整 |
| SEC13FCollector | 27 | 完整 |
| TuShareCollector | 34 | 完整 |
| JisiluCrawler | 30 | 完整 |
| CommodityCrawler | 48 | 完整 |
| Registry | 41 | 完整 |
| **总计** | **222+** | |
