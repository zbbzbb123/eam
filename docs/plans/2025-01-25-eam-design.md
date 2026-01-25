# EAM 投资决策系统 - 设计文档

> 文档版本: 1.0
> 创建日期: 2025-01-25

---

## 1. 系统概述

### 1.1 系统名称
**EAM (Easy Asset Management)** - 轻松资产管理

### 1.2 系统定位
个人投资决策辅助系统，帮助用户：
- 系统化管理三层仓位配置
- 自动采集和分析投资相关信息
- 发现投资机会并给出建议
- 监控持仓风险并及时预警

### 1.3 设计原则
- **被动优先**: 用户不需要主动去看，系统push关键信息
- **建议而非指令**: 所有输出都是"建议"，附带理由，用户做最终决策
- **可解释**: 每个建议都能追溯到原始数据，不做黑盒

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EAM 投资决策系统                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        数据采集层 (Collectors)                        │   │
│  ├──────────────┬──────────────┬──────────────┬──────────────────────┤   │
│  │   结构化API   │   AI爬虫     │   另类数据    │     宏观数据          │   │
│  │  • AkShare   │  • Firecrawl │  • GitHub API│   • FRED            │   │
│  │  • yfinance  │  • Jina      │  • HuggingFace│  • 中国统计局        │   │
│  │  • TuShare   │  • Crawlee   │  • 集思录     │   • 海关总署          │   │
│  └──────────────┴──────────────┴──────────────┴──────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        数据存储层 (Storage)                           │   │
│  ├──────────────────────┬──────────────────────────────────────────────┤   │
│  │        MySQL         │              Neo4j                           │   │
│  │  • 行情时序数据        │           • 产业链图谱                        │   │
│  │  • 持仓记录           │           • 公司关系网络                       │   │
│  │  • 信号历史           │           • 供应商/客户链                      │   │
│  │  • 宏观指标           │                                              │   │
│  └──────────────────────┴──────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     分析引擎层 (按板块组织)                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ 板块一：硬科技与新要素                                         │   │   │
│  │  ├─────────────────┬─────────────────┬─────────────────────────┤   │   │
│  │  │   AI & 算力      │  AI + 生物医疗   │      新能源              │   │   │
│  │  │ • Mag7 Capex    │ • FDA审批监控    │ • 碳酸锂/多晶硅价格      │   │   │
│  │  │ • GitHub热度    │ • 临床试验状态   │ • 新三样出口数据         │   │   │
│  │  │ • HF下载量      │ • 一级市场融资   │ • 产能出清信号           │   │   │
│  │  │ • arXiv论文     │                 │                         │   │   │
│  │  └─────────────────┴─────────────────┴─────────────────────────┘   │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ 板块二：硬通货与宏观对冲                                        │   │   │
│  │  ├─────────────────────────────────────────────────────────────┤   │   │
│  │  │ • 美国实际利率 (TIPS Yield)    • 金银比自动计算               │   │   │
│  │  │ • 央行购金数据 (WGC)          • GLD/SLV/黄金ETF联动          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ 板块三：地缘政治与宏观环境                                      │   │   │
│  │  ├─────────────────────────────────────────────────────────────┤   │   │
│  │  │ • FOMC声明Diff分析            • 地缘紧张度指数                │   │   │
│  │  │ • 美国宏观数据 (CPI/GDP/失业率) • GDELT全球事件监测            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ 个股分析引擎 (跨板块通用)                                       │   │   │
│  │  ├────────────┬────────────┬────────────┬────────────────────┤   │   │
│  │  │  聪明钱追踪  │  产业链挖掘  │ 硬核指标    │    基本面排雷        │   │   │
│  │  │ • 13F/北向  │ • 供应链提取 │ • GitHub   │   • PEG/FCF        │   │   │
│  │  │ • 内部交易  │ • 铲子股发现 │ • 临床管线  │   • R&D占比         │   │   │
│  │  │ • 回购监控  │ • Neo4j查询 │            │   • 财务打分         │   │   │
│  │  └────────────┴────────────┴────────────┴────────────────────┘   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        决策输出层 (Output)                            │   │
│  ├──────────────────┬──────────────────┬─────────────────────────────┤   │
│  │     周报生成       │     实时告警      │         Web Dashboard        │   │
│  │  • 三层仓位回顾    │  • Telegram Bot  │       • 仓位可视化            │   │
│  │  • 机会发现汇总    │  • 阈值触发       │       • 信号时间线            │   │
│  │  • 风险预警清单    │  • 紧急事件推送   │       • 再平衡建议            │   │
│  └──────────────────┴──────────────────┴─────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据采集层设计

### 3.1 结构化 API 数据源

| 数据源 | 覆盖范围 | 用途 | 调用频率 |
|--------|----------|------|----------|
| **AkShare** | A股/港股/美股/宏观 | 主力数据源，北向资金、ETF持仓、宏观指标 | 每日 |
| **yfinance** | 美股/全球指数 | 美股ETF行情、基本面数据 | 每日 |
| **TuShare Pro** | A股深度数据 | 财务指标、PE/PB分位（免费额度够用） | 每周 |
| **FRED API** | 美国宏观 | TIPS利率、CPI、GDP、失业率 | 每周 |

### 3.2 AI 爬虫目标

| 目标站点 | 内容 | 技术方案 | 频率 |
|----------|------|----------|------|
| **Seeking Alpha** | 财报电话会纪要、研报 | Firecrawl → LLM摘要 | 财报季 |
| **OpenInsider** | 美股内部交易 | Crawlee (反爬严格) | 每日 |
| **集思录** | ETF折溢价、可转债 | requests + BeautifulSoup | 每日 |
| **生意社/SMM** | 碳酸锂、多晶硅价格 | Jina Reader → 结构化 | 每日 |
| **arXiv** | AI论文摘要 | arXiv API (官方) | 每周 |
| **路透/彭博标题** | 地缘风险关键词 | GDELT API 替代 | 每日 |

### 3.3 另类数据

| 数据源 | 用途 | 方案 |
|--------|------|------|
| **GitHub API** | 上市公司开源项目热度 (Star/Fork增速) | 官方API |
| **HuggingFace** | 模型下载量趋势 | 爬取排行榜 |
| **ClinicalTrials.gov** | 药企临床管线状态变化 | 官方API |
| **SEC EDGAR** | 13F机构持仓 | 官方API + LLM解析 |

### 3.4 采集调度策略

```
每日任务 (凌晨运行):
├── 行情数据更新 (AkShare + yfinance)
├── 北向资金/内部交易
├── 大宗商品价格
└── 地缘风险指数计算

每周任务 (周末运行):
├── 宏观数据更新 (FRED)
├── GitHub/HuggingFace 热度
├── 基本面指标刷新
└── 周报生成

事件触发:
├── 财报季 → 抓取 Earnings Call
├── FOMC会议 → 声明 Diff 分析
└── 13F 披露期 → 机构持仓更新
```

---

## 4. 分析引擎层设计

### 4.1 板块一：硬科技与新要素

#### 4.1.1 AI & 算力分析器

```python
class AIComputeAnalyzer:

    def analyze_mag7_capex(self):
        """
        巨头资本开支监测
        - 数据源: 财报电话会纪要 (Seeking Alpha)
        - LLM任务: 提取 Capex 数字，对比上季度
        - 信号: Capex环比增长 → 算力军备竞赛持续 → 利好 SOXX/SMH
        """

    def track_developer_heat(self):
        """
        开发者热度追踪
        - GitHub: 监控 AI 相关 repo 的 Star 周增速
        - HuggingFace: Top 模型下载量变化
        - 信号: 新架构项目 Star 暴涨 → 可能是下一个风口
        """

    def scan_arxiv(self):
        """
        学术前沿监测
        - 抓取 cs.AI 分类最新论文
        - LLM: "这篇论文是否提出了新的模型架构？影响哪些公司？"
        """

# 关联ETF: QQQ, SOXX, SMH, 515070(A股AI ETF)
```

#### 4.1.2 AI + 生物医疗分析器

```python
class AIBioAnalyzer:

    def monitor_clinical_trials(self):
        """
        临床管线监测
        - 数据源: ClinicalTrials.gov API
        - 监控: 关注列表内药企的试验状态变化
        - 信号: Phase 2 → Phase 3 = 重大催化剂
        """

    def track_fda_decisions(self):
        """
        FDA 审批追踪
        - 爬取 FDA 官网审批日历
        - 信号: 获批 → 利好，拒批/延期 → 风险
        """

    def scan_vc_funding(self):
        """
        一级市场热度
        - 数据源: Crunchbase / 36Kr
        - 逻辑: AI制药融资频繁 → 二级市场(XBI)可能跟随
        """

# 关联ETF: XBI, IBB, 恒生医疗ETF
```

#### 4.1.3 新能源分析器

```python
class NewEnergyAnalyzer:

    def track_upstream_prices(self):
        """
        上游价格监测
        - 碳酸锂价格 (生意社/SMM)
        - 多晶硅价格
        - 信号: 价格止跌企稳 → 周期反转第一信号
        """

    def analyze_export_data(self):
        """
        出口数据分析
        - 数据源: 海关总署 (AkShare可取)
        - 监控: "新三样"(电动车、锂电、光伏)出口金额
        """

    def detect_capacity_clearing(self):
        """
        产能出清信号
        - 监控: 行业龙头产能利用率、小厂倒闭新闻
        - LLM: 扫描行业新闻，识别"减产""破产""整合"关键词
        """

# 关联ETF: 光伏ETF(515790), 新能源车ETF(515030)
```

### 4.2 板块二：硬通货与宏观对冲

```python
class PreciousMetalAnalyzer:

    def track_real_interest_rate(self):
        """
        实际利率监测 (黄金核心驱动)
        - 数据源: FRED API → 10-Year TIPS Constant Maturity Rate
        - 逻辑: 实际利率下行 → 黄金必涨
        - 信号阈值:
            - 实际利率 < 0% → 强烈利好黄金
            - 实际利率拐头向下 → 买入信号
            - 实际利率快速上行 → 风险警告
        """

    def calculate_gold_silver_ratio(self):
        """
        金银比自动计算
        - 计算: GLD价格 / SLV价格 (或现货价)
        - 历史分位判断:
            - > 85 → 白银被严重低估，考虑加仓SLV
            - 70-85 → 正常区间
            - < 65 → 白银相对高估，谨慎
        """

    def track_central_bank_gold(self):
        """
        央行购金追踪
        - 数据源: 世界黄金协会(WGC)季度报告
        - 监控: 中国、俄罗斯、印度等央行购金量
        """

# 关联ETF: GLD, IAU, SLV, 黄金ETF(518880)
```

### 4.3 板块三：地缘政治与宏观环境

```python
class GeopoliticalAnalyzer:

    def analyze_fomc_diff(self):
        """
        FOMC 声明 Diff 分析
        - 触发: 每次FOMC会议后
        - 流程:
            1. 获取本次声明全文
            2. 与上次声明做文本Diff
            3. LLM分析态度变化
        - 输出: 鹰鸽指数 (-5到+5) + 关键变化摘要
        """

    def calculate_geopolitical_tension_index(self):
        """
        地缘紧张度指数
        - 数据源: GDELT Project
        - 关键词监控:
            - 高危: "Sanctions", "Tariff", "Taiwan Strait", "War"
            - 中危: "Trade dispute", "Diplomatic tension"
        - 阈值:
            - 指数 > 80 → 紧急预警
            - 指数 50-80 → 关注
            - 指数 < 50 → 正常
        """

    def us_macro_dashboard(self):
        """
        美国宏观仪表盘
        - 核心指标: CPI, GDP, 失业率, PMI
        - 输出: 经济周期判断 (过热/稳定/衰退/复苏)
        """

    def china_macro_dashboard(self):
        """
        中国宏观仪表盘
        - 核心指标: PMI, 社融, M2, 房地产销售
        - 输出: 政策宽松/收紧判断
        """
```

### 4.4 个股分析引擎

#### 4.4.1 聪明钱追踪

```python
class SmartMoneyTracker:

    # 美股
    def analyze_13f_filings(self):
        """
        13F 机构持仓分析
        - 监控名单: ARK, 桥水, 高瓴, Coatue, Tiger Global
        - 信号: 新建仓/大幅加仓/清仓
        """

    def monitor_insider_trading(self):
        """
        内部交易监控
        - 过滤: CEO/CFO买入 且 金额>$100,000
        - 信号: 高管大额买入 = 强烈看好
        """

    # A股/港股
    def track_northbound_flow(self):
        """北向资金追踪"""

    def monitor_buybacks(self):
        """回购监控 (尤其注销式回购)"""
```

#### 4.4.2 产业链挖掘

```python
class SupplyChainMiner:

    def __init__(self):
        self.graph_db = Neo4jConnection()

    def extract_supply_chain(self, company: str):
        """
        供应链提取
        - 输入: 龙头公司年报/研报
        - LLM: 提取供应商关系
        - 存储: 写入 Neo4j
        """

    def find_pick_and_shovel(self, trigger_stock: str):
        """
        铲子股发现
        - 触发: 当龙头股大涨
        - 查询: 图谱中找上游供应商
        - 筛选: 估值未起飞 (PE分位 < 50%)
        """

    def supply_chain_risk_alert(self, risk_stock: str):
        """
        供应链风险传导
        - 触发: 某供应商出问题
        - 反向查询: 谁依赖这家供应商
        """
```

#### 4.4.3 硬核指标 (另类数据)

```python
class AlternativeDataAnalyzer:

    def track_github_activity(self):
        """GitHub 热度追踪"""

    def track_huggingface_trends(self):
        """HuggingFace 模型热度"""

    def track_pipeline_value(self):
        """临床管线估值变化"""
```

#### 4.4.4 基本面排雷

```python
class FundamentalScreener:

    def score_stock(self, stock_code: str) -> dict:
        """
        基本面打分 (满分100)

        评分项:
        - R&D占比: 20分
        - PEG: 25分
        - 自由现金流: 25分
        - 资产负债率: 15分
        - ROE稳定性: 15分

        输出:
        - score: 分数
        - grade: A/B/C
        - flags: 风险标记
        - recommendation: 可入池/建议回避
        """
```

---

## 5. 持仓管理模块设计

### 5.1 持仓跟踪引擎

```python
class HoldingsTracker:

    def setup_holding_monitors(self, holding: Holding):
        """
        为每只持仓配置专属监控:
        - 价格告警 (止损/止盈/波动)
        - 基本面 (财报日期/估值分位)
        - 新闻关键词
        - 产业链联动
        """

    def generate_holding_signals(self, holding: Holding) -> List[Signal]:
        """
        生成持仓相关信号:
        - 价格信号
        - 基本面变化
        - 相关新闻
        - 聪明钱动向
        - 产业链传导
        """

    def generate_holding_recommendation(self, holding: Holding) -> dict:
        """
        AI决策建议:
        - 买入理由是否仍成立
        - 建议操作 (持有/加仓/减仓/清仓)
        - 关键关注点
        - 下一个催化剂
        """
```

### 5.2 持仓详情页功能

- 持仓概况 (数量/成本/盈亏/止损止盈线)
- AI 决策建议
- 相关信号 (近7天)
- 产业链动态 (上下游/竞争对手)
- 操作入口 (记录想法/新增交易/修改止盈止损)

---

## 6. 决策输出层设计

### 6.1 周报结构

```python
WeeklyReport = {
    # 第一部分：仓位全景
    "portfolio_overview": {
        "total_value": float,
        "weekly_return": str,
        "allocation": {
            "稳健层": {"target": 40, "actual": float, "drift": float},
            "中等风险": {"target": 30, "actual": float, "drift": float},
            "Gamble": {"target": 30, "actual": float, "drift": float}
        },
        "rebalance_suggestion": str
    },

    # 第二部分：板块信号汇总
    "sector_signals": {
        "硬科技": {...},
        "硬通货": {...},
        "宏观环境": {...}
    },

    # 第三部分：机会发现
    "opportunities": [
        {"type": str, "stock": str, "signal": str, "score": int, "action": str}
    ],

    # 第四部分：风险预警
    "risk_alerts": [
        {"level": str, "content": str, "suggestion": str}
    ],

    # 第五部分：本周待办
    "action_items": [str]
}
```

### 6.2 实时告警

**告警级别:**
- 🔴 紧急: 需要立即行动
- 🟠 重要: 今日内需关注
- 🟡 提示: 知晓即可

**告警类型:**
- 价格类: 涨跌幅>5%、触及止损/止盈、创新高/新低
- 事件类: 财报、FDA审批、高管交易、机构持仓变化
- 宏观类: FOMC、经济数据、地缘风险
- 系统类: 爬虫失败、数据异常

### 6.3 Dashboard 布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EAM Dashboard                                        [周报] [设置] 👤  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 仓位总览                                          总资产: $xxx    │   │
│  │   稳健层 40%    ████████████████░░░░ xx.x%                       │   │
│  │   中等风险 30%  ████████████████████░ xx.x%                      │   │
│  │   Gamble 30%   ███████████████░░░░░ xx.x%                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐   │
│  │ 持仓明细                  │  │ 信号时间线                        │   │
│  │ (按层级显示每只持仓)       │  │ (所有分析引擎产生的信号流)         │   │
│  └──────────────────────────┘  └──────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 宏观仪表盘                                                       │   │
│  │  实际利率 | 金银比 | 地缘指数 | 美国经济 | 中国经济 | 下次FOMC    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 数据库设计

### 7.1 MySQL 表结构

#### 持仓与交易

```sql
-- 持仓表
CREATE TABLE holdings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    market ENUM('US', 'HK', 'CN') NOT NULL,
    tier ENUM('stable', 'medium', 'gamble') NOT NULL,
    quantity DECIMAL(18,4) NOT NULL,
    avg_cost DECIMAL(18,4) NOT NULL,
    first_buy_date DATE NOT NULL,
    buy_reason TEXT NOT NULL,
    stop_loss_price DECIMAL(18,4),
    take_profit_price DECIMAL(18,4),
    custom_keywords JSON,
    status ENUM('active', 'closed') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 交易记录表
CREATE TABLE transactions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    holding_id INT NOT NULL,
    action ENUM('buy', 'sell') NOT NULL,
    quantity DECIMAL(18,4) NOT NULL,
    price DECIMAL(18,4) NOT NULL,
    reason TEXT NOT NULL,
    transaction_date DATETIME NOT NULL,
    FOREIGN KEY (holding_id) REFERENCES holdings(id)
);
```

#### 行情与宏观数据

```sql
-- 日线行情
CREATE TABLE daily_quotes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    market ENUM('US', 'HK', 'CN') NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(18,4),
    high DECIMAL(18,4),
    low DECIMAL(18,4),
    close DECIMAL(18,4),
    volume BIGINT,
    UNIQUE KEY (symbol, market, trade_date)
);

-- 宏观指标
CREATE TABLE macro_indicators (
    id INT PRIMARY KEY AUTO_INCREMENT,
    indicator_code VARCHAR(50) NOT NULL,
    indicator_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    region VARCHAR(20) NOT NULL,
    value DECIMAL(18,4) NOT NULL,
    report_date DATE NOT NULL,
    UNIQUE KEY (indicator_code, report_date)
);

-- 金银比
CREATE TABLE gold_silver_ratio (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date DATE NOT NULL UNIQUE,
    gold_price DECIMAL(18,4),
    silver_price DECIMAL(18,4),
    ratio DECIMAL(10,4),
    percentile DECIMAL(5,2)
);
```

#### 信号与聪明钱

```sql
-- 信号表
CREATE TABLE signals (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    signal_source VARCHAR(50) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    level ENUM('info', 'warning', 'alert') NOT NULL,
    symbol VARCHAR(20),
    holding_id INT,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    raw_data JSON,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13F 机构持仓
CREATE TABLE institutional_holdings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    institution_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    shares BIGINT NOT NULL,
    value DECIMAL(18,2) NOT NULL,
    change_shares BIGINT,
    action VARCHAR(20)
);

-- 北向资金
CREATE TABLE northbound_flow (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    holding_shares BIGINT,
    holding_ratio DECIMAL(10,4),
    net_buy DECIMAL(18,2)
);

-- 内部交易
CREATE TABLE insider_trades (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    insider_name VARCHAR(100) NOT NULL,
    insider_title VARCHAR(50),
    trade_date DATE NOT NULL,
    trade_type ENUM('buy', 'sell') NOT NULL,
    shares BIGINT NOT NULL,
    price DECIMAL(18,4),
    value DECIMAL(18,2)
);
```

#### 另类数据

```sql
-- GitHub 项目热度
CREATE TABLE github_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    repo_name VARCHAR(200) NOT NULL,
    related_company VARCHAR(50),
    record_date DATE NOT NULL,
    stars INT,
    forks INT,
    stars_weekly_change INT
);

-- 临床试验
CREATE TABLE clinical_trials (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trial_id VARCHAR(50) NOT NULL UNIQUE,
    company VARCHAR(100) NOT NULL,
    drug_name VARCHAR(100),
    phase VARCHAR(20),
    status VARCHAR(50),
    indication VARCHAR(200),
    last_updated DATE,
    status_changed BOOLEAN DEFAULT FALSE
);
```

### 7.2 Neo4j 图模型

```cypher
// 公司节点
CREATE (c:Company {
    symbol: "NVDA",
    name: "Nvidia",
    market: "US",
    sector: "Semiconductor"
})

// 供应关系
(supplier)-[:SUPPLIES {
    component: "CoWoS封装",
    dependency: "critical"
}]->(customer)

// 竞争关系
(company1)-[:COMPETES_WITH]->(company2)

// 常用查询：找低估值供应商
MATCH (supplier)-[:SUPPLIES]->(c:Company {symbol: "NVDA"})
WHERE supplier.pe_percentile < 50
RETURN supplier
```

---

## 8. 项目结构

```
eam/
├── docker-compose.yml
├── .env.example
├── requirements.txt
│
├── src/
│   ├── config.py
│   ├── main.py                     # FastAPI 入口
│   │
│   ├── collectors/                 # 数据采集层
│   │   ├── structured/             # AkShare, yfinance, TuShare, FRED
│   │   ├── crawlers/               # Seeking Alpha, OpenInsider, 集思录
│   │   ├── alternative/            # GitHub, HuggingFace, ClinicalTrials
│   │   └── scheduler.py
│   │
│   ├── analyzers/                  # 分析引擎层
│   │   ├── sectors/                # 三大板块分析器
│   │   │   ├── tech/               # AI算力, AI生物, 新能源
│   │   │   ├── precious_metals.py
│   │   │   └── geopolitical.py
│   │   ├── stock/                  # 个股分析引擎
│   │   │   ├── smart_money.py
│   │   │   ├── supply_chain.py
│   │   │   ├── alternative_data.py
│   │   │   └── fundamental.py
│   │   └── holdings/               # 持仓分析
│   │
│   ├── llm/                        # LLM 相关
│   │   ├── client.py
│   │   └── prompts/
│   │
│   ├── output/                     # 决策输出层
│   │   ├── weekly_report.py
│   │   ├── telegram_bot.py
│   │   └── alert_manager.py
│   │
│   ├── api/                        # FastAPI 路由
│   ├── db/                         # 数据库连接
│   └── utils/
│
├── web/                            # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Holdings.vue
│   │   │   ├── HoldingDetail.vue
│   │   │   ├── Signals.vue
│   │   │   └── WeeklyReport.vue
│   │   └── components/
│   └── dist/
│
├── scripts/                        # 运维脚本
└── tests/
```

---

## 9. 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 异步、自动文档 |
| 任务调度 | APScheduler | Python原生 |
| 数据库 | MySQL 8.0 | 主存储 |
| 图数据库 | Neo4j | 产业链关系 |
| 缓存 | Redis | API限流/缓存 |
| LLM | OpenAI / DeepSeek | 可切换 |
| AI爬虫 | Firecrawl + Crawlee | 网页转Markdown |
| 前端 | Vue 3 + Vite + ECharts | 轻量快速 |
| 推送 | Telegram Bot API | 免费即时 |
| 部署 | Docker Compose | 一键部署 |

---

## 10. 开发阶段

```
阶段一：基础框架 (MVP)
├── 项目骨架搭建
├── MySQL + Neo4j 初始化
├── 持仓管理 CRUD
├── 基础行情采集
└── 简单 Dashboard

阶段二：分析引擎
├── 三大板块分析器
├── 信号生成与存储
└── Telegram 告警接入

阶段三：个股能力
├── 聪明钱追踪
├── 基本面排雷
├── 持仓专属跟踪
├── AI 决策建议
└── 周报生成

阶段四：高级功能
├── 产业链图谱 (Neo4j)
├── 铲子股发现
├── AI 爬虫接入
├── 另类数据
└── 完整 Dashboard

阶段五：优化与运维
├── 性能优化
├── 监控告警
├── 数据备份
└── 使用文档
```
