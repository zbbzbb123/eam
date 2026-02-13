"""资金流向分析器 - 北向资金、板块资金、市场宽度综合分析。"""
from decimal import Decimal
from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.analyzers.base import ReportAnalyzer, AnalysisReport, AnalyzerResult
from src.db.models import SignalSeverity
from src.db.models_market_data import (
    NorthboundFlow,
    SectorFlowSnapshot,
    MarketBreadthSnapshot,
)

# 用户持仓关注的板块关键词
HOLDING_KEYWORDS = ["半导体", "新能源", "AI", "养老"]


class CapitalFlowAnalyzer(ReportAnalyzer):
    """资金流向综合分析器。

    分析维度：
    1. 北向资金（沪深港通）近期流向趋势
    2. 板块主力资金净流入/流出排行
    3. 市场涨跌家数宽度指标
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self._signals: List[AnalyzerResult] = []

    @property
    def name(self) -> str:
        return "capital_flow_analyzer"

    # ------------------------------------------------------------------
    # 主分析入口
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisReport:
        details: List[str] = []
        recommendations: List[str] = []
        data: dict = {}
        self._signals = []

        # 1) 北向资金分析
        nb_details, nb_recs, nb_data = self._analyze_northbound()
        details.extend(nb_details)
        recommendations.extend(nb_recs)
        data["northbound"] = nb_data

        # 2) 板块资金分析
        sf_details, sf_recs, sf_data = self._analyze_sector_flow()
        details.extend(sf_details)
        recommendations.extend(sf_recs)
        data["sector_flow"] = sf_data

        # 3) 市场宽度分析
        mb_details, mb_recs, mb_data = self._analyze_market_breadth()
        details.extend(mb_details)
        recommendations.extend(mb_recs)
        data["market_breadth"] = mb_data

        # 综合评级
        rating, score, summary = self._compute_overall(nb_data, mb_data)

        return AnalysisReport(
            section_name="资金流向分析",
            rating=rating,
            score=score,
            summary=summary,
            details=details,
            data=data,
            recommendations=recommendations,
        )

    def get_signals(self) -> List[AnalyzerResult]:
        # analyze() 必须在 get_signals() 之前调用
        return self._signals

    # ------------------------------------------------------------------
    # 1. 北向资金
    # ------------------------------------------------------------------

    def _analyze_northbound(self) -> tuple:
        """Analyze northbound trading volume trends.

        Note: TuShare moneyflow_hsgt provides daily TRADING VOLUME (成交额),
        not net flow. We analyze volume trends to gauge foreign capital activity.
        """
        rows = (
            self.db.query(NorthboundFlow)
            .order_by(desc(NorthboundFlow.trade_date))
            .limit(10)
            .all()
        )

        details: List[str] = []
        recs: List[str] = []
        data: dict = {}

        if not rows:
            details.append("【北向资金】暂无近期北向资金数据")
            return details, recs, data

        rows_asc = list(reversed(rows))

        # Latest day volume
        today_vol = float(rows_asc[-1].net_flow)
        today_date = rows_asc[-1].trade_date.isoformat()
        data["today_date"] = today_date
        data["today_volume"] = round(today_vol, 2)
        details.append(f"【北向资金】{today_date} 交易额 {today_vol:.1f} 亿元")

        # 5-day average volume
        recent_5 = rows_asc[-5:] if len(rows_asc) >= 5 else rows_asc
        avg_5d = sum(float(r.net_flow) for r in recent_5) / len(recent_5)
        data["avg_5d_volume"] = round(avg_5d, 2)
        data["days"] = len(recent_5)

        # Volume trend: compare today vs 5-day average
        if today_vol > avg_5d * 1.2:
            stance = "外资活跃"
        elif today_vol < avg_5d * 0.8:
            stance = "外资清淡"
        else:
            stance = "外资正常"
        data["stance"] = stance
        details.append(
            f"【北向资金】5日均量 {avg_5d:.1f} 亿元, 今日{'放量' if today_vol > avg_5d else '缩量'} → {stance}"
        )

        # Volume trend direction (increasing or decreasing over 3 days)
        if len(rows_asc) >= 3:
            last3_vols = [float(r.net_flow) for r in rows_asc[-3:]]
            if last3_vols[0] < last3_vols[1] < last3_vols[2]:
                details.append("【北向资金】连续3日交易量递增，外资参与度上升")
                data["vol_trend"] = "递增"
            elif last3_vols[0] > last3_vols[1] > last3_vols[2]:
                details.append("【北向资金】连续3日交易量递减，外资参与度下降")
                data["vol_trend"] = "递减"
            else:
                data["vol_trend"] = "波动"

        # Signal: sharp volume drop (< 60% of average) may indicate risk-off
        if today_vol < avg_5d * 0.6:
            self._signals.append(
                AnalyzerResult(
                    title="北向资金交易量骤降",
                    description=(
                        f"今日北向交易额 {today_vol:.1f} 亿元，"
                        f"仅为5日均量的 {today_vol/avg_5d*100:.0f}%，"
                        "外资参与度显著下降，需关注市场情绪变化。"
                    ),
                    severity=SignalSeverity.HIGH,
                    data={"today_volume": round(today_vol, 2), "avg_5d": round(avg_5d, 2)},
                )
            )

        # Recommendations
        if stance == "外资清淡":
            recs.append("北向交易量萎缩，外资参与度下降，注意市场可能缺乏增量资金")
        elif stance == "外资活跃":
            recs.append("北向交易活跃，外资参与度提升，关注外资偏好的权重蓝筹标的")

        return details, recs, data

    # ------------------------------------------------------------------
    # 2. 板块资金流向
    # ------------------------------------------------------------------

    def _analyze_sector_flow(self) -> tuple:
        # 取最新一天的行业板块数据
        latest_row = (
            self.db.query(SectorFlowSnapshot)
            .filter(SectorFlowSnapshot.sector_type == "industry")
            .order_by(desc(SectorFlowSnapshot.snapshot_date))
            .limit(1)
            .first()
        )

        details: List[str] = []
        recs: List[str] = []
        data: dict = {}

        if not latest_row:
            details.append("【板块资金】暂无板块资金流向数据")
            return details, recs, data

        snapshot_date = latest_row.snapshot_date

        all_sectors = (
            self.db.query(SectorFlowSnapshot)
            .filter(
                SectorFlowSnapshot.sector_type == "industry",
                SectorFlowSnapshot.snapshot_date == snapshot_date,
            )
            .order_by(desc(SectorFlowSnapshot.main_net_inflow))
            .all()
        )

        if not all_sectors:
            details.append("【板块资金】暂无板块资金流向数据")
            return details, recs, data

        data["snapshot_date"] = snapshot_date.isoformat()

        # Top 5 流入
        top5 = all_sectors[:5]
        data["top5_inflow"] = [
            {"name": s.name, "main_net_inflow": float(s.main_net_inflow)}
            for s in top5
        ]
        top5_lines = [
            f"  {s.name}: {float(s.main_net_inflow):+.2f} 亿" for s in top5
        ]
        details.append(
            "【板块资金】主力净流入前5行业:\n" + "\n".join(top5_lines)
        )

        # Bottom 5 流出
        bottom5 = all_sectors[-5:]
        data["bottom5_outflow"] = [
            {"name": s.name, "main_net_inflow": float(s.main_net_inflow)}
            for s in bottom5
        ]
        bottom5_lines = [
            f"  {s.name}: {float(s.main_net_inflow):+.2f} 亿" for s in bottom5
        ]
        details.append(
            "【板块资金】主力净流出前5行业:\n" + "\n".join(bottom5_lines)
        )

        # 用户持仓关注板块匹配
        holding_hits: List[str] = []
        for sector in all_sectors:
            for kw in HOLDING_KEYWORDS:
                if kw in sector.name:
                    direction = "流入" if float(sector.main_net_inflow) > 0 else "流出"
                    holding_hits.append(
                        f"  {sector.name}（关联: {kw}）: "
                        f"主力净{direction} {abs(float(sector.main_net_inflow)):.2f} 亿"
                    )
        if holding_hits:
            data["holding_related"] = holding_hits
            details.append(
                "【板块资金】持仓关联板块动态:\n" + "\n".join(holding_hits)
            )
            recs.append("关注持仓关联板块的资金异动，结合个股走势判断是否调仓")

        return details, recs, data

    # ------------------------------------------------------------------
    # 3. 市场宽度
    # ------------------------------------------------------------------

    def _analyze_market_breadth(self) -> tuple:
        # 取最新一天快照
        latest_row = (
            self.db.query(MarketBreadthSnapshot)
            .order_by(desc(MarketBreadthSnapshot.snapshot_date))
            .limit(1)
            .first()
        )

        details: List[str] = []
        recs: List[str] = []
        data: dict = {}

        if not latest_row:
            details.append("【市场宽度】暂无涨跌家数数据")
            return details, recs, data

        snapshot_date = latest_row.snapshot_date

        breadths = (
            self.db.query(MarketBreadthSnapshot)
            .filter(MarketBreadthSnapshot.snapshot_date == snapshot_date)
            .all()
        )

        data["snapshot_date"] = snapshot_date.isoformat()
        data["indices"] = {}

        bearish_count = 0
        ge_board_ratio: float | None = None
        sh_board_ratio: float | None = None

        for b in breadths:
            adv = b.advancing
            dec = b.declining
            ratio = adv / dec if dec > 0 else float("inf")
            ratio_str = f"{ratio:.2f}"

            if ratio > 2:
                mood = "强势普涨"
            elif ratio < 0.5:
                mood = "弱势普跌"
                bearish_count += 1
            else:
                mood = "涨跌均衡"

            data["indices"][b.index_code] = {
                "index_name": b.index_name,
                "advancing": adv,
                "declining": dec,
                "unchanged": b.unchanged,
                "ratio": round(ratio, 2),
                "mood": mood,
            }
            details.append(
                f"【市场宽度】{b.index_name}({b.index_code}): "
                f"涨 {adv} / 跌 {dec} / 平 {b.unchanged}，"
                f"涨跌比 {ratio_str}:1 → {mood}"
            )

            # 记录创业板和上证的比率用于比较
            if "创业" in b.index_name:
                ge_board_ratio = ratio
            if "上证" in b.index_name:
                sh_board_ratio = ratio

        # 创业板 vs 上证 分化
        if ge_board_ratio is not None and sh_board_ratio is not None:
            diff = ge_board_ratio - sh_board_ratio
            if abs(diff) > 0.5:
                stronger = "创业板" if diff > 0 else "上证"
                weaker = "上证" if diff > 0 else "创业板"
                details.append(
                    f"【市场宽度】风格分化: {stronger}明显强于{weaker}，"
                    f"涨跌比差值 {abs(diff):.2f}"
                )
                data["divergence"] = {
                    "stronger": stronger,
                    "weaker": weaker,
                    "diff": round(abs(diff), 2),
                }
                recs.append(f"市场风格偏向{stronger}，可适当向{stronger}方向倾斜配置")

        # 信号：三大指数全部宽度 < 1:2 → MEDIUM
        if bearish_count >= 3:
            self._signals.append(
                AnalyzerResult(
                    title="市场宽度全面走弱",
                    description=(
                        "上证、深证、创业板三大指数涨跌比均低于1:2，"
                        "市场呈现普跌格局，短期风险偏好下行。"
                    ),
                    severity=SignalSeverity.MEDIUM,
                    data={"bearish_indices_count": bearish_count},
                )
            )
            recs.append("三大指数宽度全面走弱，建议降低仓位或增加防御性配置")

        return details, recs, data

    # ------------------------------------------------------------------
    # 综合评级
    # ------------------------------------------------------------------

    def _compute_overall(
        self, nb_data: dict, mb_data: dict
    ) -> tuple:
        """根据北向资金和市场宽度给出综合评级和分数。"""
        score = 50  # 基准分

        # 北向资金交易量加减分
        stance = nb_data.get("stance")
        if stance == "外资活跃":
            score += 15
        elif stance == "外资清淡":
            score -= 15

        vol_trend = nb_data.get("vol_trend")
        if vol_trend == "递增":
            score += 10
        elif vol_trend == "递减":
            score -= 10

        # 市场宽度加减分
        indices = mb_data.get("indices", {})
        for idx_data in indices.values():
            ratio = idx_data.get("ratio", 1.0)
            if ratio > 2:
                score += 5
            elif ratio < 0.5:
                score -= 5

        # 限制在 0-100
        score = max(0, min(100, score))

        if score >= 70:
            rating = "积极"
        elif score >= 40:
            rating = "中性"
        else:
            rating = "谨慎"

        parts: List[str] = []
        if stance:
            parts.append(f"北向资金{stance}")
        if indices:
            moods = [v.get("mood", "") for v in indices.values()]
            if moods:
                parts.append(f"市场宽度{'、'.join(set(moods))}")
        summary = "；".join(parts) if parts else "数据不足，暂无法综合判断"
        summary = f"综合评级【{rating}】（{score}分）。{summary}。"

        return rating, score, summary
