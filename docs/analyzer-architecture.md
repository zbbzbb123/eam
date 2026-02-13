# 分析器架构设计 — 数据驱动的投资决策系统

## 你的需求总结

1. **宏观环境** — 结合FRED利率/CPI/GDP + 中国PMI/CPI/M2/Shibor + 美债利差 → 判断大环境
2. **资金面** — 北向资金趋势 + 板块资金流向 + A股涨跌家数 → 判断市场情绪
3. **个股层面** — 除持仓外，跟踪 MSFT/AMZN/NVDA/TSLA 等超级头部 → 发现买入机会
4. **资源类** — 黄金/白银/铜/原油 → 持续观察入场时机
5. **核心判断** — AI长期绝对利好，token消耗指数级上升
6. **平台角色** — 操作指引 + 风控预警

---

## 数据层现状（已具备）

| 数据维度 | 数据源 | 表 | 更新频率 |
|----------|--------|------|---------|
| VIX/黄金/白银/铜/原油/汇率 | YFinance | market_indicator_snapshots | 每日17:00 |
| 美债 10Y/2Y/利差 | FRED | yield_spreads | 每日18:00 |
| 美国CPI/GDP/失业率/联邦基金利率 | FRED | macro_data | 每日18:00 |
| 中国PMI/CPI/M2/Shibor/新增贷款 | EastMoney/Chinamoney | cn_macro_data | 每日18:00 |
| 北向资金净流入 | EastMoney | northbound_flow | 每日17:00 |
| A股涨跌家数 | EastMoney | market_breadth_snapshots | 每日17:00 |
| 板块资金流 | EastMoney | sector_flow_snapshots | 每日17:00 |
| 板块行情 | Sina | sector_snapshots | 每日17:00 |
| 指数估值 PE/PB | TuShare | index_valuation_snapshots | 每日17:00 |
| ETF净值 | TuShare | fund_nav_snapshots | 每日17:00 |
| 个股基本面 | yfinance/TuShare | fundamental_snapshots | 每日17:00 |
| 机构持仓(13F) | SEC EDGAR | (未落表) | 季度 |

**缺口**：
- 头部美股(MSFT/AMZN/NVDA/TSLA)的行情和基本面 → 需扩展 fundamentals 采集范围
- 持仓个股的每日收盘价未系统性入库 → 需加每日quote同步任务

---

## 分析器架构设计

### 总体思路

```
采集层(已有) → 分析层(新增) → 周报层(增强)
                   │
                   ├─ MarketEnvironmentAnalyzer  宏观+情绪 → 大环境评分
                   ├─ CapitalFlowAnalyzer        北向+板块资金 → 资金面信号
                   ├─ PortfolioHealthAnalyzer     持仓集中度/盈亏/偏离 → 风控
                   ├─ CommodityAnalyzer           金银铜油 → 入场时机判断
                   └─ WatchlistAnalyzer           MSFT/NVDA等 → 机会发现
                                                     │
                                               WeeklyReport (增强版)
                                                     │
                                    ┌────────────────┼────────────────┐
                                    │                │                │
                              宏观环境摘要      持仓分析+建议     关注标的机会
```

---

### Analyzer 1: MarketEnvironmentAnalyzer（宏观环境分析器）

**输入数据**：
- `yield_spreads` → 10Y-2Y利差（衰退预警）
- `macro_data` → CPI趋势、联邦基金利率、失业率
- `cn_macro_data` → PMI（荣枯线50）、CPI、M2增速、Shibor
- `market_indicator_snapshots` → VIX（恐慌指标）、USD/CNY汇率
- `index_valuation_snapshots` → 沪深300/中证500 PE百分位

**分析逻辑**：
```
1. 美国宏观评分 (0-100):
   - 利差 > 0 且扩大 → 加分  |  利差倒挂 → 减分
   - CPI趋势下行 → 加分(降息预期)  |  CPI反弹 → 减分
   - 失业率稳定低位 → 加分  |  急升 → 减分
   - VIX < 20 → 正常  |  20-30 → 警惕  |  > 30 → 恐慌

2. 中国宏观评分 (0-100):
   - PMI > 50 → 扩张加分  |  < 50 → 收缩减分
   - M2增速 vs CPI → 判断流动性宽松程度
   - Shibor趋势下行 → 流动性宽松  |  上行 → 收紧
   - 新增贷款超预期 → 实体需求回暖

3. A股估值水位:
   - 沪深300 PE < 历史30%分位 → 低估
   - 沪深300 PE > 历史70%分位 → 偏贵

4. 综合环境评级: 乐观/中性/谨慎/防御
```

**输出**：
- 环境评级 + 评分
- 关键变化摘要（如：VIX突破20、利差转正）
- 对持仓的影响判断

---

### Analyzer 2: CapitalFlowAnalyzer（资金流向分析器）

**输入数据**：
- `northbound_flow` → 近N日北向资金净流入趋势
- `sector_flow_snapshots` → 板块主力资金流向
- `market_breadth_snapshots` → 涨跌家数比

**分析逻辑**：
```
1. 北向资金:
   - 5日累计净流入 > 100亿 → 外资积极  |  净流出 > 100亿 → 外资撤退
   - 连续3日同向 → 趋势确认

2. 板块资金:
   - 半导体/AI/新能源 板块主力净流入排名 → 与持仓关联
   - 资金从哪个板块流出 → 规避方向

3. 市场宽度:
   - 涨跌比 > 2:1 → 普涨行情  |  < 1:2 → 普跌
   - 创业板 vs 主板分化程度
```

**输出**：
- 北向资金趋势判断
- 与持仓相关的板块资金流向
- 市场宽度信号

---

### Analyzer 3: PortfolioHealthAnalyzer（持仓健康度分析器）

**输入数据**：
- `holdings` → 当前持仓
- `daily_quotes` / `fund_nav_snapshots` → 最新价格
- `fundamental_snapshots` → PE/PB/营收增长
- `market_indicator_snapshots` → 汇率(换算)

**分析逻辑**：
```
1. 仓位结构:
   - 市场分布 (CN/US/HK/现金)
   - 主题分布 (半导体/美股科技/新能源/养老/港股)
   - 单一持仓集中度 (> 25% 预警)

2. 盈亏状况:
   - 各持仓浮盈浮亏
   - 整体组合回报率
   - 亏损标的是否需要止损

3. 风险指标:
   - 现金比例 (< 5% → 加仓空间不足)
   - 波动率暴露 (半导体+新能源 > 40% → 过度集中成长赛道)
   - 汇率风险 (美元资产占比)

4. 再平衡建议:
   - 根据tier目标对比实际偏离
   - 具体调仓方向
```

**输出**：
- 持仓明细表（包含占比、盈亏）
- 风险预警
- 调仓建议

---

### Analyzer 4: CommodityAnalyzer（大宗商品分析器）

**输入数据**：
- `market_indicator_snapshots` → GC=F/SI=F/HG=F/CL=F 每日价格和涨跌
- `macro_data` → DFII10 (实际利率，影响黄金)
- `yield_spreads` → 美债收益率

**分析逻辑**：
```
1. 黄金:
   - 实际利率(TIPS)下行 → 利好黄金
   - VIX飙升 → 避险需求
   - 金银比 > 85 → 白银相对低估

2. 白银:
   - 金银比判断相对价值
   - 工业需求(与铜联动)
   - 光伏需求预期

3. 铜:
   - 铜价趋势 → 经济晴雨表
   - 与PMI对比验证

4. 原油:
   - 价格区间判断
   - 与CPI关联(通胀传导)

5. 入场时机评估:
   - 各品种是否处于近期低位(20日/60日)
   - 是否出现技术性超卖
```

**输出**：
- 各品种现价 + 近期趋势
- 入场时机建议（等待/可关注/机会出现）
- 关联影响分析

---

### Analyzer 5: WatchlistAnalyzer（关注标的分析器）

**需新增**: watchlist 概念（不在持仓中但需要跟踪的标的）

**关注标的**（已在持仓的 BABA/GOOG/QQQ 不重复进watchlist）：

**美股七巨头 (Magnificent 7)**：
| 标的 | 市场 | 主题 |
|------|------|------|
| MSFT | US | AI/云/Office |
| AMZN | US | AI/云/电商 |
| NVDA | US | AI芯片(算力供给) |
| TSLA | US | AI自动驾驶/能源 |
| AAPL | US | 消费科技/AI终端 |
| META | US | AI社交/元宇宙 |

注：GOOG 已在持仓中，不重复

**A股AI龙头**：
| 标的 | 市场 | 主题 |
|------|------|------|
| 688256 | CN | 寒武纪 — AI芯片 |
| 688981 | CN | 中芯国际 — 晶圆代工 |
| 688041 | CN | 海光信息 — AI/服务器芯片 |
| 603019 | CN | 中科曙光 — AI算力/服务器 |
| 002230 | CN | 科大讯飞 — AI应用/NLP |
| 000977 | CN | 浪潮信息 — AI服务器 |

**输入数据**：
- yfinance 实时行情（需新增采集）
- `fundamental_snapshots`（需扩展采集范围到watchlist）

**分析逻辑**：
```
1. 基本面跟踪:
   - PE/营收增长 是否在合理区间
   - 对比上次采集是否有重大变化

2. 估值判断:
   - 历史PE百分位 (TuShare对美股不适用，用yfinance)
   - PEG (PE / 增长率)

3. 与AI主题关联:
   - 用户核心信仰: token消耗指数增长
   - NVDA → 算力供给端
   - MSFT/AMZN → 云infra + 应用端
   - TSLA → AI落地(自动驾驶)
   - META → AI社交应用

4. 机会信号:
   - 跌幅超过10% → 关注
   - PE低于行业均值 → 关注
   - 财报日临近 → 提醒
```

**输出**：
- 各标的现状概览
- 机会/风险提示
- 是否建议加入持仓

---

## 数据层补充（需要新增/修改）

### 1. Watchlist 模型
**新表 `watchlist`**:
```
id, symbol, market, theme, reason, added_at
```
- 存放非持仓但需跟踪的标的
- WatchlistAnalyzer 和 fundamentals 采集器读取此表

### 2. 扩展基本面采集
- `_collect_market_data()` 中 fundamentals 采集范围扩大：从 active holdings + watchlist 中的 symbol 一起采集
- 这样 MSFT/NVDA 等也有每日基本面数据

### 3. 每日行情同步
- 新增调度任务：每日为所有 holdings + watchlist 的 symbol 同步 daily_quotes
- 使用 YFinanceCollector(US) + AkShareCollector(CN/HK)

---

## 周报增强设计

现有周报结构：
```
1. 仓位全景 (tier allocation)
2. 板块信号汇总
3. 风险预警
4. 本周待办
```

增强后周报结构：
```
1. 宏观环境总览              ← MarketEnvironmentAnalyzer
   - 环境评级(乐观/中性/谨慎/防御)
   - 美国: 利率/CPI/就业 关键变化
   - 中国: PMI/流动性/信贷 关键变化
   - A股估值水位

2. 资金面信号                ← CapitalFlowAnalyzer
   - 北向资金周度总结
   - 与持仓相关板块资金动向
   - 市场宽度变化

3. 持仓分析                  ← PortfolioHealthAnalyzer
   - 持仓明细 (symbol/市值/占比/盈亏)
   - 市场分布 / 主题分布
   - 集中度风险
   - 具体调仓建议

4. 大宗商品追踪              ← CommodityAnalyzer
   - 金/银/铜/油 周度表现
   - 入场时机评估

5. 关注标的机会              ← WatchlistAnalyzer
   - NVDA/MSFT/AMZN/TSLA 概览
   - 是否出现买入窗口

6. 风险预警 + 行动建议        ← 汇总
   - 综合以上分析的具体操作指引
```

---

## 技术实现方案

### 分析器基类改造

现有 `BaseAnalyzer` 接受 db session，输出 `AnalyzerResult` → `Signal`。

但新分析器需要更丰富的输出（不仅仅是信号，还有报告段落）。方案：

**新增 `ReportAnalyzer` 基类**：
```python
class ReportAnalyzer(ABC):
    """分析器基类，输出结构化报告段落 + 可选信号"""

    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def analyze(self) -> AnalysisReport:
        """返回结构化分析报告"""
        pass

    def get_signals(self) -> List[AnalyzerResult]:
        """返回需要告警的信号（可选）"""
        return []
```

**`AnalysisReport` 数据类**：
```python
@dataclass
class AnalysisReport:
    section_name: str           # 报告段落标题
    rating: Optional[str]       # 评级（如 乐观/中性/谨慎）
    score: Optional[int]        # 评分 0-100
    summary: str                # 一句话摘要
    details: List[str]          # 详细要点列表
    data: Optional[dict]        # 结构化数据（前端可用）
    recommendations: List[str]  # 建议列表
```

### 周报服务改造

`WeeklyReportService.generate_report()` 中：
1. 实例化各 ReportAnalyzer
2. 调用 `analyze()` 收集各段落
3. 调用 `get_signals()` 收集需要告警的信号
4. 组装为增强版 WeeklyReport

### LLM 建议生成

已有 `src/services/llm_client.py` (OpenAI-compatible 网关)。新增流程：

```
分析器输出 AnalysisReport (结构化)
    → 组装为 prompt context
    → LLM 生成:
       1. 一段话的市场环境总结
       2. 针对每个持仓的操作建议(加仓/持有/减仓/观望)
       3. watchlist 中是否有值得入场的标的
       4. 风控提醒
    → 嵌入周报的"AI投资建议"段落
```

日报用简短 prompt（宏观+资金面摘要），周报用完整 prompt（全量分析数据）。

### 日报 vs 周报

**日报（每日 18:30 自动生成）**：
```
1. 宏观环境快照 (MarketEnvironmentAnalyzer)
2. 今日资金面 (CapitalFlowAnalyzer)
3. 大宗商品行情 (CommodityAnalyzer)
4. AI一句话点评 (LLM简短总结)
```

**周报（每周日 20:00 自动生成）**：
```
1-3. 同日报但汇总为周度
4. 持仓分析 (PortfolioHealthAnalyzer)
5. 关注标的机会 (WatchlistAnalyzer)
6. AI投资建议 (LLM完整分析)
7. 风险预警 + 行动计划
```

### 调度器集成

- `_run_analyzers()` (18:30 每日) → 跑所有分析器 + 生成日报
- 新增 `_generate_weekly_report()` (周日 20:00) → 生成周报

---

## 实施步骤

### Phase 1: 基础设施
1. `src/analyzers/base.py` — 新增 ReportAnalyzer 基类 + AnalysisReport 数据类
2. `src/db/models.py` — 新增 Watchlist 模型
3. 初始化 watchlist 数据（12个标的）

### Phase 2: 5个分析器（可并行开发）
4. `src/analyzers/market_environment.py` — 宏观环境分析器
5. `src/analyzers/capital_flow.py` — 资金流向分析器
6. `src/analyzers/portfolio_health.py` — 持仓健康度分析器
7. `src/analyzers/commodity.py` — 大宗商品分析器
8. `src/analyzers/watchlist.py` — 关注标的分析器

### Phase 3: 报告层
9. `src/services/weekly_report.py` — 大改：接入5个分析器 + LLM建议 + 日报/周报双模式
10. `src/api/schemas.py` — 新增增强版报告 schema
11. `src/api/reports.py` — 新增日报端点

### Phase 4: 数据层补充
12. `src/scheduler/scheduler.py` — 注册分析器 + 每日行情同步 + 周报调度
13. 扩展 fundamentals 采集范围（holdings + watchlist）

### Phase 5: 验证
14. 每个分析器单独 Docker 内测试
15. 日报/周报端到端验证
16. 前端渲染验证

---

## 验证方案

1. 每个分析器单独可测：`docker compose exec api python -c "from src.analyzers.market_environment import ...; ..."`
2. 周报端到端：`curl localhost:8000/api/reports/weekly/markdown` 输出完整增强版周报
3. 前端周报页面能正确渲染新增段落

---

## 设计决策（已确认）

1. **Watchlist**: 先DB直接维护，代码初始化写入，后续手动SQL调整
2. **AI辅助**: LLM生成建议 — 分析器产出结构化数据，最终由LLM生成自然语言投资建议
3. **报告频率**: 两者都要 — 日报简版(宏观+资金面) + 周报完整版(含持仓分析和建议)
4. **Watchlist范围**: 美股7巨头 + A股AI龙头（见下表）
