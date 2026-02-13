"""关注列表分析器 — 分析观察列表中标的的基本面、走势和机会信号。"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from src.analyzers.base import ReportAnalyzer, AnalysisReport, AnalyzerResult
from src.db.models import Watchlist, DailyQuote, Market, SignalSeverity
from src.db.models_market_data import FundamentalSnapshot


# AI主题叙事（每只标的的核心逻辑）
AI_NARRATIVE = {
    "NVDA": "AI算力供给核心，GPU垄断地位。token消耗指数增长直接利好",
    "MSFT": "Azure + OpenAI深度绑定，企业AI落地最大受益者",
    "AMZN": "AWS AI服务 + 电商AI应用双轮驱动",
    "TSLA": "自动驾驶FSD + Optimus机器人，AI物理世界落地",
    "AAPL": "Apple Intelligence终端AI入口，生态护城河",
    "META": "AI社交推荐 + Llama开源模型，元宇宙长期布局",
    "688256": "寒武纪 — 国产AI芯片龙头，算力国产替代",
    "688981": "中芯国际 — 晶圆代工龙头，AI芯片制造基础",
    "688041": "海光信息 — 国产GPU/DCU，数据中心AI芯片",
    "603019": "中科曙光 — AI服务器/算力基础设施",
    "002230": "科大讯飞 — AI语音/NLP应用龙头",
    "000977": "浪潮信息 — AI服务器出货量领先",
}

# PE阈值（科技股简单判断）
PE_CHEAP = 25
PE_REASONABLE_MAX = 40
PE_EXPENSIVE = 60

# 增长率阈值
GROWTH_STRONG = Decimal("0.20")
GROWTH_MODERATE = Decimal("0.10")
GROWTH_OUTSTANDING_VALUE = Decimal("0.25")
OUTSTANDING_PE_CAP = 35

# 价格变动阈值
PULLBACK_THRESHOLD = Decimal("-0.10")
MAJOR_PULLBACK_THRESHOLD = Decimal("-0.15")
NEAR_TARGET_THRESHOLD = Decimal("0.05")

# 30天回看
LOOKBACK_DAYS = 30


class WatchlistAnalyzer(ReportAnalyzer):
    """分析观察列表中的标的，评估估值、成长性和机会信号。"""

    def __init__(self, db: Session, user_id: Optional[int] = None):
        super().__init__(db, user_id=user_id)
        self._signals: List[AnalyzerResult] = []

    @property
    def name(self) -> str:
        return "关注列表分析"

    # ------------------------------------------------------------------
    # 主分析入口
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisReport:
        """运行分析并返回结构化报告。"""
        self._signals = []

        query = self.db.query(Watchlist)
        if self.user_id is not None:
            query = query.filter(Watchlist.user_id == self.user_id)
        watchlist_items = query.all()
        if not watchlist_items:
            return AnalysisReport(
                section_name=self.name,
                rating="无数据",
                summary="观察列表为空，暂无可分析标的。",
            )

        stock_analyses: List[dict] = []
        opportunities_count = 0

        for item in watchlist_items:
            analysis = self._analyze_stock(item)
            stock_analyses.append(analysis)
            if analysis.get("opportunity"):
                opportunities_count += 1

        # 汇总评级
        rating = self._compute_overall_rating(stock_analyses)
        summary = (
            f"共跟踪 {len(stock_analyses)} 只标的，"
            f"其中 {opportunities_count} 只出现机会信号。"
        )

        details = self._build_details(stock_analyses)
        recommendations = self._build_recommendations(stock_analyses)

        return AnalysisReport(
            section_name=self.name,
            rating=rating,
            score=self._compute_score(stock_analyses),
            summary=summary,
            details=details,
            data={"stocks": stock_analyses},
            recommendations=recommendations,
        )

    def get_signals(self) -> List[AnalyzerResult]:
        """返回需要告警的信号（30日跌幅超15%的标的）。"""
        return self._signals

    # ------------------------------------------------------------------
    # 单只标的分析
    # ------------------------------------------------------------------

    def _analyze_stock(self, item: Watchlist) -> dict:
        """分析单只观察列表标的。"""
        symbol = item.symbol
        market_value = item.market.value if isinstance(item.market, Market) else item.market

        # 获取最新基本面快照
        fundamental = self._get_latest_fundamental(symbol, market_value)

        # 获取最近30天行情
        quotes = self._get_recent_quotes(symbol, item.market)

        # 当前价格
        price = self._get_current_price(quotes, fundamental)

        # PE 分析
        pe = float(fundamental.pe_ratio) if fundamental and fundamental.pe_ratio else None
        pe_assessment = self._assess_pe(pe)

        # 营收增长
        revenue_growth = (
            float(fundamental.revenue_growth)
            if fundamental and fundamental.revenue_growth is not None
            else None
        )
        growth_assessment = self._assess_growth(revenue_growth)

        # 30日涨跌幅
        change_30d = self._calc_30d_change(quotes)

        # 目标价上行空间
        upside = self._calc_upside(price, fundamental)

        # 名称
        name = fundamental.name if fundamental and fundamental.name else symbol

        # 机会信号
        opportunity = self._detect_opportunity(
            pe, revenue_growth, change_30d, upside
        )

        # AI主题叙事
        ai_narrative = AI_NARRATIVE.get(symbol, "")

        # 如果30日跌幅超15%，产生告警信号
        if change_30d is not None and change_30d < float(MAJOR_PULLBACK_THRESHOLD):
            self._signals.append(
                AnalyzerResult(
                    title=f"关注标的大幅回调: {name}({symbol})",
                    description=(
                        f"{name}（{symbol}）近30日跌幅 {change_30d * 100:.1f}%，"
                        f"超过15%阈值，建议关注是否出现买入机会。"
                    ),
                    severity=SignalSeverity.MEDIUM,
                    data={
                        "symbol": symbol,
                        "market": market_value,
                        "change_30d": round(change_30d, 4) if change_30d is not None else None,
                        "price": price,
                    },
                    related_symbols=[symbol],
                )
            )

        return {
            "symbol": symbol,
            "market": market_value,
            "theme": item.theme,
            "name": name,
            "price": price,
            "pe": pe,
            "pe_assessment": pe_assessment,
            "revenue_growth": revenue_growth,
            "growth_assessment": growth_assessment,
            "change_30d": round(change_30d, 4) if change_30d is not None else None,
            "upside": round(upside, 4) if upside is not None else None,
            "opportunity": opportunity,
            "ai_narrative": ai_narrative,
        }

    # ------------------------------------------------------------------
    # 数据获取
    # ------------------------------------------------------------------

    def _get_latest_fundamental(
        self, symbol: str, market_value: str
    ) -> Optional[FundamentalSnapshot]:
        """获取标的最新基本面快照。"""
        return (
            self.db.query(FundamentalSnapshot)
            .filter(
                FundamentalSnapshot.symbol == symbol,
                FundamentalSnapshot.market == market_value,
            )
            .order_by(FundamentalSnapshot.snapshot_date.desc())
            .first()
        )

    def _get_recent_quotes(
        self, symbol: str, market: Market
    ) -> List[DailyQuote]:
        """获取标的最近30天行情，按日期升序排列。"""
        since = date.today() - timedelta(days=LOOKBACK_DAYS)
        return (
            self.db.query(DailyQuote)
            .filter(
                DailyQuote.symbol == symbol,
                DailyQuote.market == market,
                DailyQuote.trade_date >= since,
            )
            .order_by(DailyQuote.trade_date.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # 指标计算
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_price(
        quotes: List[DailyQuote],
        fundamental: Optional[FundamentalSnapshot],
    ) -> Optional[float]:
        """获取当前价格，优先使用最新日线收盘价。"""
        if quotes and quotes[-1].close is not None:
            return float(quotes[-1].close)
        if fundamental and fundamental.target_price is not None:
            # 没有行情时以目标价做参考（不理想但聊胜于无）
            return None
        return None

    @staticmethod
    def _assess_pe(pe: Optional[float]) -> str:
        """评估PE水平。"""
        if pe is None:
            return "无数据"
        if pe < 0:
            return "亏损"
        if pe < PE_CHEAP:
            return "估值合理"
        if pe < PE_REASONABLE_MAX:
            return "估值适中"
        if pe < PE_EXPENSIVE:
            return "估值偏高"
        return "估值昂贵"

    @staticmethod
    def _assess_growth(revenue_growth: Optional[float]) -> str:
        """评估营收增长。"""
        if revenue_growth is None:
            return "无数据"
        if revenue_growth >= float(GROWTH_STRONG):
            return "高速增长"
        if revenue_growth >= float(GROWTH_MODERATE):
            return "稳健增长"
        if revenue_growth >= 0:
            return "增速放缓"
        return "营收下滑"

    @staticmethod
    def _calc_30d_change(quotes: List[DailyQuote]) -> Optional[float]:
        """计算30日涨跌幅（最老 → 最新）。"""
        if len(quotes) < 2:
            return None
        oldest_close = quotes[0].close
        newest_close = quotes[-1].close
        if oldest_close is None or newest_close is None or oldest_close == 0:
            return None
        return float((newest_close - oldest_close) / oldest_close)

    @staticmethod
    def _calc_upside(
        price: Optional[float],
        fundamental: Optional[FundamentalSnapshot],
    ) -> Optional[float]:
        """计算目标价上行空间。"""
        if (
            price is None
            or price == 0
            or fundamental is None
            or fundamental.target_price is None
        ):
            return None
        target = float(fundamental.target_price)
        return (target - price) / price

    # ------------------------------------------------------------------
    # 机会信号检测
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_opportunity(
        pe: Optional[float],
        revenue_growth: Optional[float],
        change_30d: Optional[float],
        upside: Optional[float],
    ) -> List[str]:
        """检测机会信号，返回信号文字列表。"""
        signals: List[str] = []

        # 价格回调超过10%
        if change_30d is not None and change_30d < float(PULLBACK_THRESHOLD):
            signals.append("回调关注")

        # 科技股PE低于25
        if pe is not None and 0 < pe < PE_CHEAP:
            signals.append("估值合理")

        # 高增长 + 合理估值 = 性价比突出
        if (
            revenue_growth is not None
            and pe is not None
            and revenue_growth > float(GROWTH_OUTSTANDING_VALUE)
            and 0 < pe < OUTSTANDING_PE_CAP
        ):
            signals.append("性价比突出")

        # 接近分析师目标价（差距不超过5%）
        if upside is not None and abs(upside) <= float(NEAR_TARGET_THRESHOLD):
            signals.append("接近目标价")

        return signals

    # ------------------------------------------------------------------
    # 汇总与报告生成
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_overall_rating(stock_analyses: List[dict]) -> str:
        """根据机会数量给出整体评级。"""
        opp_count = sum(1 for s in stock_analyses if s.get("opportunity"))
        total = len(stock_analyses)
        if total == 0:
            return "无数据"
        ratio = opp_count / total
        if ratio >= 0.5:
            return "机会较多"
        if ratio >= 0.2:
            return "部分机会"
        return "暂无明显机会"

    @staticmethod
    def _compute_score(stock_analyses: List[dict]) -> int:
        """计算综合评分（0-100）。

        评分逻辑：
        - 基础分50
        - 每只有机会信号的标的 +10（上限30）
        - 有高增长标的 +5（上限10）
        - 有大幅回调标的 -5（上限-10）
        """
        score = 50
        opp_bonus = min(
            sum(10 for s in stock_analyses if s.get("opportunity")), 30
        )
        growth_bonus = min(
            sum(
                5
                for s in stock_analyses
                if s.get("growth_assessment") == "高速增长"
            ),
            10,
        )
        pullback_penalty = max(
            -sum(
                5
                for s in stock_analyses
                if s.get("change_30d") is not None
                and s["change_30d"] < float(PULLBACK_THRESHOLD)
            ),
            -10,
        )
        score = score + opp_bonus + growth_bonus + pullback_penalty
        return max(0, min(100, score))

    @staticmethod
    def _build_details(stock_analyses: List[dict]) -> List[str]:
        """生成每只标的的详情文字。"""
        details: List[str] = []
        for s in stock_analyses:
            parts: List[str] = [f"【{s['name']}({s['symbol']})】"]

            if s.get("theme"):
                parts.append(f"主题: {s['theme']}")

            if s["price"] is not None:
                parts.append(f"当前价: {s['price']:.2f}")

            if s["pe"] is not None:
                parts.append(f"PE: {s['pe']:.1f} ({s['pe_assessment']})")

            if s["revenue_growth"] is not None:
                parts.append(
                    f"营收增长: {s['revenue_growth'] * 100:.1f}% ({s['growth_assessment']})"
                )

            if s["change_30d"] is not None:
                parts.append(f"30日涨跌: {s['change_30d'] * 100:.1f}%")

            if s.get("upside") is not None:
                parts.append(f"目标价上行空间: {s['upside'] * 100:.1f}%")

            if s.get("opportunity"):
                parts.append(f"机会信号: {', '.join(s['opportunity'])}")

            if s.get("ai_narrative"):
                parts.append(f"AI叙事: {s['ai_narrative']}")

            details.append(" | ".join(parts))

        return details

    @staticmethod
    def _build_recommendations(stock_analyses: List[dict]) -> List[str]:
        """根据分析结果生成建议。"""
        recommendations: List[str] = []

        # 性价比突出的标的
        outstanding = [
            s for s in stock_analyses if "性价比突出" in (s.get("opportunity") or [])
        ]
        if outstanding:
            names = "、".join(f"{s['name']}({s['symbol']})" for s in outstanding)
            recommendations.append(f"高增长低估值标的: {names}，可重点研究。")

        # 回调中的标的
        pullback = [
            s
            for s in stock_analyses
            if "回调关注" in (s.get("opportunity") or [])
        ]
        if pullback:
            names = "、".join(f"{s['name']}({s['symbol']})" for s in pullback)
            recommendations.append(f"近期回调标的: {names}，关注是否出现支撑。")

        # 接近目标价的标的
        near_target = [
            s
            for s in stock_analyses
            if "接近目标价" in (s.get("opportunity") or [])
        ]
        if near_target:
            names = "、".join(f"{s['name']}({s['symbol']})" for s in near_target)
            recommendations.append(f"已接近分析师目标价: {names}，注意止盈或重新评估。")

        if not recommendations:
            recommendations.append("当前观察列表暂无突出机会，继续保持跟踪。")

        return recommendations
