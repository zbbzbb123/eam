"""大宗商品分析器 - 黄金、白银、铜、原油综合分析。"""
import logging
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.analyzers.base import ReportAnalyzer, AnalysisReport, AnalyzerResult
from src.db.models import SignalSeverity
from src.db.models_market_data import MarketIndicatorSnapshot, MacroData, CnMacroRecord

logger = logging.getLogger(__name__)

# 大宗商品配置
COMMODITIES = {
    "GC=F": {"name": "黄金", "unit": "美元/盎司"},
    "SI=F": {"name": "白银", "unit": "美元/盎司"},
    "HG=F": {"name": "铜", "unit": "美元/磅"},
    "CL=F": {"name": "原油", "unit": "美元/桶"},
}

# 分析阈值
GOLD_SILVER_RATIO_WARN = 90       # 金银比极端高位 -> 产生信号
GOLD_SILVER_RATIO_HIGH = 85       # 白银相对低估
GOLD_SILVER_RATIO_FAIR = 70       # 白银合理估值
VIX_SAFE_HAVEN_THRESHOLD = 25     # VIX 高于此值 -> 避险需求
OIL_CHEAP = 60                    # 原油低位
OIL_NORMAL_HIGH = 80              # 原油正常区间上限
LOOKBACK_DAYS = 60                # 回溯天数
MA_SHORT = 20                     # 短期均线
MA_LONG = 60                      # 长期均线
DAILY_DROP_SIGNAL_PCT = -5.0      # 单日跌幅信号阈值


def _to_float(val: Any) -> Optional[float]:
    """安全地将 Decimal 或其他数值转换为 float。"""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class CommodityAnalyzer(ReportAnalyzer):
    """
    大宗商品综合分析器。

    覆盖品种：黄金、白银、铜、原油
    分析维度：趋势、均线位置、区间百分位、金银比、实际利率、VIX 避险、铜经济信号、原油价格区间
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self._signals: List[AnalyzerResult] = []

    @property
    def name(self) -> str:
        return "commodity_analyzer"

    # ------------------------------------------------------------------
    # 数据查询
    # ------------------------------------------------------------------

    def _query_prices(self, symbol: str, days: int = LOOKBACK_DAYS) -> List[MarketIndicatorSnapshot]:
        """查询指定品种最近 N 天的价格数据，按日期升序返回。"""
        cutoff = date.today() - timedelta(days=days)
        rows = (
            self.db.query(MarketIndicatorSnapshot)
            .filter(
                MarketIndicatorSnapshot.symbol == symbol,
                MarketIndicatorSnapshot.date >= cutoff,
                MarketIndicatorSnapshot.value.isnot(None),
            )
            .order_by(MarketIndicatorSnapshot.date.asc())
            .all()
        )
        return rows

    def _query_latest_price(self, symbol: str) -> Optional[MarketIndicatorSnapshot]:
        """查询指定品种最新一条价格记录。"""
        return (
            self.db.query(MarketIndicatorSnapshot)
            .filter(
                MarketIndicatorSnapshot.symbol == symbol,
                MarketIndicatorSnapshot.value.isnot(None),
            )
            .order_by(desc(MarketIndicatorSnapshot.date))
            .first()
        )

    def _query_vix(self) -> Optional[float]:
        """获取最新 VIX 值。"""
        row = self._query_latest_price("^VIX")
        return _to_float(row.value) if row else None

    def _query_real_rate(self) -> Optional[float]:
        """查询最新 DFII10（10年期 TIPS 实际利率）。"""
        row = (
            self.db.query(MacroData)
            .filter(MacroData.series_id == "DFII10")
            .order_by(desc(MacroData.date))
            .first()
        )
        return _to_float(row.value) if row else None

    def _query_real_rate_trend(self) -> Optional[str]:
        """判断实际利率近期趋势：上升 / 下降 / 持平。"""
        cutoff = date.today() - timedelta(days=30)
        rows = (
            self.db.query(MacroData)
            .filter(MacroData.series_id == "DFII10", MacroData.date >= cutoff)
            .order_by(MacroData.date.asc())
            .all()
        )
        if len(rows) < 2:
            return None
        first_val = _to_float(rows[0].value)
        last_val = _to_float(rows[-1].value)
        if first_val is None or last_val is None:
            return None
        diff = last_val - first_val
        if diff > 0.1:
            return "上升"
        elif diff < -0.1:
            return "下降"
        return "持平"

    def _query_latest_pmi(self) -> Optional[float]:
        """获取最新中国 PMI 数据。"""
        row = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == "PMI")
            .order_by(desc(CnMacroRecord.date))
            .first()
        )
        return _to_float(row.value) if row else None

    # ------------------------------------------------------------------
    # 技术指标计算
    # ------------------------------------------------------------------

    def _compute_stats(self, rows: List[MarketIndicatorSnapshot]) -> Optional[Dict[str, Any]]:
        """
        从价格序列计算技术统计数据。

        返回: {price, change_pct, ma20, ma60, high_60d, low_60d, percentile, entry_signal}
        """
        if not rows:
            return None

        prices = [_to_float(r.value) for r in rows if _to_float(r.value) is not None]
        if not prices:
            return None

        current_price = prices[-1]
        latest_row = rows[-1]
        change_pct = _to_float(latest_row.change_pct)

        # 均线
        ma20 = sum(prices[-MA_SHORT:]) / min(len(prices), MA_SHORT) if prices else None
        ma60 = sum(prices[-MA_LONG:]) / min(len(prices), MA_LONG) if prices else None

        # 60日高低点
        high_60d = max(prices)
        low_60d = min(prices)

        # 当前价格在 60 日区间内的百分位
        price_range = high_60d - low_60d
        percentile = ((current_price - low_60d) / price_range * 100) if price_range > 0 else 50.0

        # 入场时机判断
        entry_signal = self._calc_entry_signal(current_price, ma20, low_60d)

        return {
            "price": round(current_price, 2),
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "ma20": round(ma20, 2) if ma20 else None,
            "ma60": round(ma60, 2) if ma60 else None,
            "high_60d": round(high_60d, 2),
            "low_60d": round(low_60d, 2),
            "percentile": round(percentile, 1),
            "entry_signal": entry_signal,
        }

    @staticmethod
    def _calc_entry_signal(price: float, ma20: Optional[float], low_60d: float) -> str:
        """
        入场时机判断：
        - 价格 < 20日均线 且 < 60日低点 + 10% → 机会出现
        - 价格 < 20日均线 → 可关注
        - 其他 → 等待
        """
        threshold_low = low_60d * 1.10
        if ma20 is not None and price < ma20 and price < threshold_low:
            return "机会出现"
        if ma20 is not None and price < ma20:
            return "可关注"
        return "等待"

    # ------------------------------------------------------------------
    # 专项分析
    # ------------------------------------------------------------------

    def _analyze_gold(
        self, stats: Dict[str, Any], real_rate: Optional[float], real_rate_trend: Optional[str], vix: Optional[float]
    ) -> List[str]:
        """黄金专项分析，返回分析要点列表。"""
        details: List[str] = []

        # 实际利率分析
        if real_rate is not None:
            details.append(f"美国10年期实际利率(DFII10): {real_rate:.2f}%")
            if real_rate_trend == "下降":
                details.append("实际利率近期呈下降趋势，对黄金构成利好")
            elif real_rate_trend == "上升":
                details.append("实际利率近期呈上升趋势，对黄金形成压制")

        # VIX 避险需求
        if vix is not None:
            if vix > VIX_SAFE_HAVEN_THRESHOLD:
                details.append(f"VIX 指数 {vix:.1f} 高于 {VIX_SAFE_HAVEN_THRESHOLD}，市场恐慌情绪升温，避险需求支撑金价")
            else:
                details.append(f"VIX 指数 {vix:.1f}，市场情绪相对平稳")

        # 高位 + 实际利率上升 → 谨慎
        if stats.get("percentile", 0) > 80 and real_rate_trend == "上升":
            details.append("警告：黄金接近60日高点且实际利率上升，追高风险较大，建议谨慎")

        return details

    def _analyze_gold_silver_ratio(
        self, gold_price: float, silver_price: float
    ) -> tuple[Optional[float], List[str]]:
        """计算金银比并分析，返回 (ratio, details)。"""
        if silver_price <= 0:
            return None, []

        ratio = gold_price / silver_price
        details: List[str] = [f"金银比: {ratio:.1f}"]

        if ratio > GOLD_SILVER_RATIO_HIGH:
            details.append(f"金银比 > {GOLD_SILVER_RATIO_HIGH}，白银相对黄金被低估，可关注白银补涨机会")
        elif ratio < GOLD_SILVER_RATIO_FAIR:
            details.append(f"金银比 < {GOLD_SILVER_RATIO_FAIR}，白银估值合理偏高")
        else:
            details.append("金银比处于正常区间")

        return ratio, details

    def _analyze_copper(self, stats: Dict[str, Any], pmi: Optional[float]) -> List[str]:
        """铜的经济信号分析。"""
        details: List[str] = []
        change = stats.get("change_pct")

        if pmi is not None:
            details.append(f"中国制造业PMI: {pmi:.1f}")
            # 铜价趋势：比较当前价格与 MA20
            price = stats.get("price", 0)
            ma20 = stats.get("ma20")
            if ma20 and price > ma20 and pmi > 50:
                details.append("铜价上行 + PMI扩张区间，经济复苏信号得到确认")
            elif ma20 and price < ma20:
                details.append("铜价走弱，可能暗示经济放缓")
        else:
            # 没有 PMI 数据时仅看铜价趋势
            ma20 = stats.get("ma20")
            price = stats.get("price", 0)
            if ma20 and price < ma20:
                details.append("铜价低于20日均线，经济放缓信号")

        return details

    def _analyze_crude_oil(self, stats: Dict[str, Any]) -> List[str]:
        """原油价格区间评估。"""
        details: List[str] = []
        price = stats.get("price", 0)

        if price < OIL_CHEAP:
            details.append(f"原油价格 ${price:.2f}，处于低位区间（<${OIL_CHEAP}），有利于降低通胀压力")
        elif price <= OIL_NORMAL_HIGH:
            details.append(f"原油价格 ${price:.2f}，处于正常区间（${OIL_CHEAP}-${OIL_NORMAL_HIGH}）")
        else:
            details.append(f"原油价格 ${price:.2f}，处于偏高区间（>${OIL_NORMAL_HIGH}），可能推升CPI通胀预期")

        return details

    # ------------------------------------------------------------------
    # 信号生成
    # ------------------------------------------------------------------

    def _check_signals(
        self,
        commodity_data: Dict[str, Dict[str, Any]],
        gold_silver_ratio: Optional[float],
    ) -> None:
        """检查是否需要产生告警信号。"""
        # 金银比极端高位信号
        if gold_silver_ratio is not None and gold_silver_ratio > GOLD_SILVER_RATIO_WARN:
            self._signals.append(AnalyzerResult(
                title="金银比极端高位警告",
                description=(
                    f"金银比达到 {gold_silver_ratio:.1f}，超过 {GOLD_SILVER_RATIO_WARN} 的极端阈值。"
                    f"历史上金银比极端值往往预示白银存在均值回归的补涨机会，建议关注白银配置。"
                ),
                severity=SignalSeverity.HIGH,
                data={
                    "gold_silver_ratio": round(gold_silver_ratio, 2),
                    "signal": "极端金银比",
                },
                related_symbols=["SI=F", "GC=F", "SLV"],
            ))

        # 单日大跌信号
        for symbol, info in COMMODITIES.items():
            stats = commodity_data.get(symbol)
            if not stats:
                continue
            change_pct = stats.get("change_pct")
            if change_pct is not None and change_pct <= DAILY_DROP_SIGNAL_PCT:
                self._signals.append(AnalyzerResult(
                    title=f"{info['name']}单日大幅下跌",
                    description=(
                        f"{info['name']}今日下跌 {change_pct:.2f}%，跌幅超过 {abs(DAILY_DROP_SIGNAL_PCT):.0f}%。"
                        f"当前价格 {stats.get('price', 'N/A')} {info['unit']}。"
                        f"大幅波动可能带来短线交易机会，需结合基本面判断是否为趋势性下跌。"
                    ),
                    severity=SignalSeverity.MEDIUM,
                    data={
                        "symbol": symbol,
                        "name": info["name"],
                        "change_pct": change_pct,
                        "price": stats.get("price"),
                    },
                    related_symbols=[symbol],
                ))

    # ------------------------------------------------------------------
    # 主分析入口
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisReport:
        """执行大宗商品综合分析，返回结构化报告。"""
        self._signals = []
        details: List[str] = []
        recommendations: List[str] = []
        commodity_data: Dict[str, Dict[str, Any]] = {}

        # 获取辅助数据
        real_rate = self._query_real_rate()
        real_rate_trend = self._query_real_rate_trend()
        vix = self._query_vix()
        pmi = self._query_latest_pmi()

        # ------ 逐品种分析 ------
        for symbol, info in COMMODITIES.items():
            rows = self._query_prices(symbol)
            stats = self._compute_stats(rows)
            if not stats:
                details.append(f"【{info['name']}】数据不足，无法分析")
                continue

            commodity_data[symbol] = stats

            # 基础行情
            ma20_pos = "上方" if (stats["ma20"] and stats["price"] > stats["ma20"]) else "下方"
            ma60_pos = "上方" if (stats["ma60"] and stats["price"] > stats["ma60"]) else "下方"

            details.append(f"【{info['name']}（{symbol}）】")
            details.append(
                f"  当前价格: {stats['price']} {info['unit']}"
                + (f"，日涨跌: {stats['change_pct']}%" if stats['change_pct'] is not None else "")
            )
            if stats["ma20"]:
                details.append(f"  20日均线: {stats['ma20']}（价格在均线{ma20_pos}）")
            if stats["ma60"]:
                details.append(f"  60日均线: {stats['ma60']}（价格在均线{ma60_pos}）")
            details.append(
                f"  60日区间: {stats['low_60d']} - {stats['high_60d']}，"
                f"当前百分位: {stats['percentile']}%"
            )
            details.append(f"  入场时机: {stats['entry_signal']}")

            # 品种专项分析
            if symbol == "GC=F":
                gold_details = self._analyze_gold(stats, real_rate, real_rate_trend, vix)
                for d in gold_details:
                    details.append(f"  {d}")

            if symbol == "HG=F":
                copper_details = self._analyze_copper(stats, pmi)
                for d in copper_details:
                    details.append(f"  {d}")

            if symbol == "CL=F":
                oil_details = self._analyze_crude_oil(stats)
                for d in oil_details:
                    details.append(f"  {d}")

            details.append("")  # 空行分隔

        # ------ 金银比分析 ------
        gold_stats = commodity_data.get("GC=F")
        silver_stats = commodity_data.get("SI=F")
        gold_silver_ratio: Optional[float] = None

        if gold_stats and silver_stats:
            gold_silver_ratio, ratio_details = self._analyze_gold_silver_ratio(
                gold_stats["price"], silver_stats["price"]
            )
            details.append("【金银比分析】")
            for d in ratio_details:
                details.append(f"  {d}")
            details.append("")

        # ------ 生成建议 ------
        for symbol, info in COMMODITIES.items():
            stats = commodity_data.get(symbol)
            if not stats:
                continue
            signal = stats["entry_signal"]
            if signal == "机会出现":
                recommendations.append(f"{info['name']}价格接近低位区间，可考虑分批建仓或加仓")
            elif signal == "可关注":
                recommendations.append(f"{info['name']}价格低于短期均线，可纳入观察名单")
            else:
                recommendations.append(f"{info['name']}当前价格偏强，建议等待回调再介入")

        if gold_silver_ratio and gold_silver_ratio > GOLD_SILVER_RATIO_HIGH:
            recommendations.append("金银比偏高，可考虑配置白银以捕捉均值回归机会")

        if real_rate_trend == "下降":
            recommendations.append("实际利率下行，贵金属中长期前景偏多")
        elif real_rate_trend == "上升":
            recommendations.append("实际利率上行，黄金面临压力，注意控制仓位")

        # ------ 评分与评级 ------
        score = self._compute_score(commodity_data, gold_silver_ratio, real_rate_trend, vix)
        rating = self._score_to_rating(score)

        # ------ 信号检查 ------
        self._check_signals(commodity_data, gold_silver_ratio)

        # ------ 摘要 ------
        active_commodities = [
            f"{COMMODITIES[s]['name']}" for s in commodity_data
        ]
        summary = f"大宗商品综合分析（{'/'.join(active_commodities)}），综合评分 {score}/100，评级「{rating}」"

        return AnalysisReport(
            section_name="大宗商品分析",
            rating=rating,
            score=score,
            summary=summary,
            details=details,
            data=commodity_data,
            recommendations=recommendations,
        )

    def get_signals(self) -> List[AnalyzerResult]:
        """返回分析中产生的告警信号。"""
        return self._signals

    # ------------------------------------------------------------------
    # 评分体系
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        commodity_data: Dict[str, Dict[str, Any]],
        gold_silver_ratio: Optional[float],
        real_rate_trend: Optional[str],
        vix: Optional[float],
    ) -> int:
        """
        综合评分（0-100），衡量大宗商品整体投资机会。

        评分维度：
        - 各品种入场信号（每个最多 15 分，共 60 分）
        - 金银比偏离度（10 分）
        - 实际利率趋势（15 分）
        - 市场情绪/VIX（15 分）
        """
        score = 50  # 基准分

        # 各品种入场信号
        for symbol in COMMODITIES:
            stats = commodity_data.get(symbol)
            if not stats:
                continue
            signal = stats["entry_signal"]
            if signal == "机会出现":
                score += 8
            elif signal == "可关注":
                score += 3
            else:
                score -= 2

        # 金银比
        if gold_silver_ratio is not None:
            if gold_silver_ratio > GOLD_SILVER_RATIO_WARN:
                score += 5  # 白银极端低估，整体存在机会
            elif gold_silver_ratio > GOLD_SILVER_RATIO_HIGH:
                score += 3

        # 实际利率趋势
        if real_rate_trend == "下降":
            score += 8
        elif real_rate_trend == "上升":
            score -= 5

        # VIX 避险
        if vix is not None:
            if vix > VIX_SAFE_HAVEN_THRESHOLD:
                score += 5  # 避险情绪利好贵金属
            elif vix < 15:
                score -= 3  # 极低波动率，商品机会偏少

        return max(0, min(100, score))

    @staticmethod
    def _score_to_rating(score: int) -> str:
        """将评分转换为文字评级。"""
        if score >= 80:
            return "积极看多"
        elif score >= 65:
            return "偏多"
        elif score >= 50:
            return "中性"
        elif score >= 35:
            return "偏空"
        else:
            return "谨慎回避"
