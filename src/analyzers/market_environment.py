"""Market environment analyzer — combines US macro, China macro, and A-share valuation."""
import logging
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.analyzers.base import AnalysisReport, AnalyzerResult, ReportAnalyzer
from src.db.models import SignalSeverity
from src.db.models_market_data import (
    CnMacroRecord,
    IndexValuationSnapshot,
    MacroData,
    MarketIndicatorSnapshot,
    YieldSpreadRecord,
)

logger = logging.getLogger(__name__)


def _to_float(val: Optional[Decimal]) -> Optional[float]:
    """Safely convert a Decimal (or None) to float."""
    if val is None:
        return None
    return float(val)


class MarketEnvironmentAnalyzer(ReportAnalyzer):
    """Produces a comprehensive market-environment report with sub-scores."""

    def __init__(self, db: Session):
        super().__init__(db)

    @property
    def name(self) -> str:
        return "market_environment"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisReport:
        us_score, us_details, us_data = self._score_us_macro()
        cn_score, cn_details, cn_data = self._score_china_macro()
        val_rating, val_details, val_data = self._assess_ashare_valuation()

        combined_data: dict = {
            "us_macro": us_data,
            "china_macro": cn_data,
            "ashare_valuation": val_data,
        }

        all_details = us_details + cn_details + val_details

        # Overall rating ------------------------------------------------
        overall_rating, recommendations = self._derive_overall_rating(
            us_score, cn_score, val_rating, combined_data
        )

        # Build summary text
        us_label = f"{us_score}" if us_score is not None else "N/A"
        cn_label = f"{cn_score}" if cn_score is not None else "N/A"
        val_label = val_rating if val_rating else "N/A"
        summary = (
            f"US宏观评分: {us_label}/100 | "
            f"中国宏观评分: {cn_label}/100 | "
            f"A股估值: {val_label} | "
            f"综合判断: {overall_rating}"
        )

        # Composite score: average of available scores, clamped 0-100
        scores = [s for s in (us_score, cn_score) if s is not None]
        composite_score = round(sum(scores) / len(scores)) if scores else None

        return AnalysisReport(
            section_name="宏观市场环境",
            rating=overall_rating,
            score=composite_score,
            summary=summary,
            details=all_details,
            data=combined_data,
            recommendations=recommendations,
        )

    def get_signals(self) -> List[AnalyzerResult]:
        signals: List[AnalyzerResult] = []

        # VIX > 25 signal
        vix = self._latest_indicator("^VIX")
        if vix is not None and vix > 25:
            severity = SignalSeverity.CRITICAL if vix > 35 else SignalSeverity.HIGH
            signals.append(
                AnalyzerResult(
                    title=f"VIX 恐慌指数升高 ({vix:.1f})",
                    description=(
                        f"VIX 当前为 {vix:.1f}，超过 25 的警戒阈值，"
                        "市场恐慌情绪上升，建议关注风险敞口。"
                    ),
                    severity=severity,
                    data={"vix": vix},
                    related_symbols=["^VIX"],
                )
            )

        # Yield curve inversion signal
        spread_row = self._latest_yield_spread()
        if spread_row is not None:
            spread_val = _to_float(spread_row.spread)
            if spread_val is not None and spread_val < 0:
                signals.append(
                    AnalyzerResult(
                        title=f"美债收益率曲线倒挂 (10Y-2Y={spread_val:+.2f}%)",
                        description=(
                            f"10年期与2年期美债利差为 {spread_val:+.2f}%，"
                            "收益率曲线倒挂通常预示经济衰退风险上升。"
                        ),
                        severity=SignalSeverity.HIGH,
                        data={
                            "spread": spread_val,
                            "dgs2": _to_float(spread_row.dgs2),
                            "dgs10": _to_float(spread_row.dgs10),
                        },
                        related_symbols=["^TNX"],
                    )
                )

        # PMI below 49 signal
        pmi_val = self._latest_cn_indicator("PMI")
        if pmi_val is not None and pmi_val < 49:
            signals.append(
                AnalyzerResult(
                    title=f"中国制造业PMI低迷 ({pmi_val:.1f})",
                    description=(
                        f"PMI 当前为 {pmi_val:.1f}，低于 49 的收缩警戒线，"
                        "制造业景气度明显下行，需关注基本面风险。"
                    ),
                    severity=SignalSeverity.MEDIUM,
                    data={"pmi": pmi_val},
                    related_symbols=["000300.SH"],
                )
            )

        return signals

    # ------------------------------------------------------------------
    # US Macro scoring
    # ------------------------------------------------------------------

    def _score_us_macro(self) -> tuple:
        """Return (score: int | None, details: list[str], data: dict)."""
        details: List[str] = []
        data: dict = {}
        score = 0
        has_any = False

        # --- Yield spread ---
        spread_pts, spread_detail, spread_data = self._score_yield_spread()
        if spread_pts is not None:
            score += spread_pts
            has_any = True
        if spread_detail:
            details.append(spread_detail)
        data["yield_spread"] = spread_data

        # --- CPI trend ---
        cpi_pts, cpi_detail, cpi_data = self._score_cpi_trend()
        if cpi_pts is not None:
            score += cpi_pts
            has_any = True
        if cpi_detail:
            details.append(cpi_detail)
        data["cpi"] = cpi_data

        # --- Unemployment ---
        unemp_pts, unemp_detail, unemp_data = self._score_unemployment()
        if unemp_pts is not None:
            score += unemp_pts
            has_any = True
        if unemp_detail:
            details.append(unemp_detail)
        data["unemployment"] = unemp_data

        # --- VIX ---
        vix_pts, vix_detail, vix_data = self._score_vix()
        if vix_pts is not None:
            score += vix_pts
            has_any = True
        if vix_detail:
            details.append(vix_detail)
        data["vix"] = vix_data

        if not has_any:
            details.insert(0, "[US宏观] 数据不足，无法评分")
            return None, details, data

        score = max(0, min(100, score))
        details.insert(0, f"[US宏观] 综合评分: {score}/100")
        return score, details, data

    def _score_yield_spread(self) -> tuple:
        """Score yield spread component (0-25 pts)."""
        rows = (
            self.db.query(YieldSpreadRecord)
            .order_by(YieldSpreadRecord.date.desc())
            .limit(2)
            .all()
        )
        if not rows:
            return None, "[利差] 数据不足", {}

        latest = rows[0]
        spread = _to_float(latest.spread)
        if spread is None:
            return None, "[利差] 数据不足", {}

        detail_parts = [f"10Y-2Y利差: {spread:+.2f}%"]
        data = {
            "spread": spread,
            "dgs2": _to_float(latest.dgs2),
            "dgs10": _to_float(latest.dgs10),
            "date": latest.date.isoformat(),
        }

        if spread < 0:
            pts = 0
            detail_parts.append("曲线倒挂，衰退风险")
        elif len(rows) >= 2:
            prev_spread = _to_float(rows[1].spread)
            if prev_spread is not None and spread > prev_spread:
                pts = 25
                detail_parts.append("利差扩大，经济预期改善")
            elif prev_spread is not None and spread < prev_spread:
                pts = 15
                detail_parts.append("利差收窄，需关注")
            else:
                pts = 20
                detail_parts.append("利差持平")
        else:
            pts = 20 if spread > 0 else 0
            detail_parts.append("正利差")

        return pts, "[利差] " + "；".join(detail_parts), data

    def _score_cpi_trend(self) -> tuple:
        """Score CPI trend component (0-25 pts)."""
        rows = (
            self.db.query(MacroData)
            .filter(MacroData.series_id == "CPIAUCSL")
            .order_by(MacroData.date.desc())
            .limit(3)
            .all()
        )
        if len(rows) < 2:
            return None, "[CPI] 数据不足", {}

        values = [_to_float(r.value) for r in rows]
        data = {
            "latest": values[0],
            "readings": values,
            "date": rows[0].date.isoformat(),
        }

        if None in values:
            return None, "[CPI] 数据不足", data

        # Check trend: declining CPI is positive for rate-cut expectations
        if len(values) >= 3 and values[0] < values[1] < values[2]:
            pts = 25
            trend = "连续下降，降息预期升温"
        elif values[0] < values[1]:
            pts = 20
            trend = "最近一期下降"
        elif values[0] > values[1]:
            pts = 5
            trend = "CPI回升，通胀压力增加"
        else:
            pts = 15
            trend = "CPI持平"

        return pts, f"[CPI] 最新值 {values[0]:.2f}；{trend}", data

    def _score_unemployment(self) -> tuple:
        """Score unemployment component (0-25 pts)."""
        rows = (
            self.db.query(MacroData)
            .filter(MacroData.series_id == "UNRATE")
            .order_by(MacroData.date.desc())
            .limit(3)
            .all()
        )
        if not rows:
            return None, "[失业率] 数据不足", {}

        latest = _to_float(rows[0].value)
        if latest is None:
            return None, "[失业率] 数据不足", {}

        data = {
            "latest": latest,
            "date": rows[0].date.isoformat(),
        }

        if latest < 4.0:
            pts = 25
            desc = "极低水平，就业强劲"
        elif latest < 5.0:
            pts = 20
            desc = "低位稳定"
        elif latest < 6.0:
            pts = 10
            desc = "温和偏高"
        else:
            pts = 0
            desc = "失业率偏高，经济承压"

        # Check for sharp rise
        if len(rows) >= 2:
            prev = _to_float(rows[1].value)
            if prev is not None and latest - prev >= 0.5:
                pts = max(0, pts - 10)
                desc += "；失业率快速攀升"

        return pts, f"[失业率] {latest:.1f}%，{desc}", data

    def _score_vix(self) -> tuple:
        """Score VIX component (0-25 pts)."""
        vix_val = self._latest_indicator("^VIX")
        if vix_val is None:
            return None, "[VIX] 数据不足", {}

        data = {"value": vix_val}

        if vix_val < 20:
            pts = 25
            desc = "低波动，市场平稳"
        elif vix_val <= 30:
            pts = 10
            desc = "波动偏高，谨慎为宜"
        else:
            pts = 0
            desc = "高波动，市场恐慌"

        return pts, f"[VIX] {vix_val:.1f}，{desc}", data

    # ------------------------------------------------------------------
    # China Macro scoring
    # ------------------------------------------------------------------

    def _score_china_macro(self) -> tuple:
        """Return (score: int | None, details: list[str], data: dict)."""
        details: List[str] = []
        data: dict = {}
        score = 0
        has_any = False

        # --- PMI ---
        pmi_pts, pmi_detail, pmi_data = self._score_pmi()
        if pmi_pts is not None:
            score += pmi_pts
            has_any = True
        if pmi_detail:
            details.append(pmi_detail)
        data["pmi"] = pmi_data

        # --- M2 vs CPI liquidity gauge ---
        liq_pts, liq_detail, liq_data = self._score_liquidity()
        if liq_pts is not None:
            score += liq_pts
            has_any = True
        if liq_detail:
            details.append(liq_detail)
        data["liquidity"] = liq_data

        # --- Shibor ON trend ---
        shibor_pts, shibor_detail, shibor_data = self._score_shibor()
        if shibor_pts is not None:
            score += shibor_pts
            has_any = True
        if shibor_detail:
            details.append(shibor_detail)
        data["shibor"] = shibor_data

        # --- New RMB loan ---
        loan_pts, loan_detail, loan_data = self._score_rmb_loan()
        if loan_pts is not None:
            score += loan_pts
            has_any = True
        if loan_detail:
            details.append(loan_detail)
        data["rmb_loan"] = loan_data

        if not has_any:
            details.insert(0, "[中国宏观] 数据不足，无法评分")
            return None, details, data

        score = max(0, min(100, score))
        details.insert(0, f"[中国宏观] 综合评分: {score}/100")
        return score, details, data

    def _score_pmi(self) -> tuple:
        """Score PMI component (0-25 pts)."""
        pmi_val = self._latest_cn_indicator("PMI")
        if pmi_val is None:
            return None, "[PMI] 数据不足", {}

        data = {"value": pmi_val}

        if pmi_val >= 52:
            pts = 25
            desc = "强劲扩张"
        elif pmi_val >= 50:
            pts = 20
            desc = "温和扩张"
        elif pmi_val >= 49:
            pts = 10
            desc = "荣枯线附近，景气边际走弱"
        else:
            pts = 0
            desc = "收缩区间，经济下行压力大"

        return pts, f"[PMI] {pmi_val:.1f}，{desc}", data

    def _score_liquidity(self) -> tuple:
        """Score M2 growth vs CPI as liquidity gauge (0-25 pts)."""
        m2_row = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == "M2")
            .order_by(CnMacroRecord.date.desc())
            .first()
        )
        cpi_row = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == "CPI")
            .order_by(CnMacroRecord.date.desc())
            .first()
        )

        if m2_row is None or cpi_row is None:
            return None, "[流动性] M2/CPI数据不足", {}

        m2_yoy = _to_float(m2_row.yoy_change)
        cpi_yoy = _to_float(cpi_row.yoy_change)

        if m2_yoy is None or cpi_yoy is None:
            return None, "[流动性] M2/CPI同比数据不足", {}

        excess = m2_yoy - cpi_yoy  # excess liquidity proxy
        data = {
            "m2_yoy": m2_yoy,
            "cpi_yoy": cpi_yoy,
            "excess_liquidity": excess,
        }

        if excess > 8:
            pts = 25
            desc = "流动性非常充裕"
        elif excess > 5:
            pts = 20
            desc = "流动性充裕"
        elif excess > 2:
            pts = 15
            desc = "流动性适中"
        else:
            pts = 5
            desc = "流动性偏紧"

        return pts, f"[流动性] M2同比 {m2_yoy:.1f}% - CPI同比 {cpi_yoy:.1f}% = 超额 {excess:.1f}%，{desc}", data

    def _score_shibor(self) -> tuple:
        """Score Shibor ON trend (0-25 pts)."""
        rows = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == "Shibor_ON")
            .order_by(CnMacroRecord.date.desc())
            .limit(5)
            .all()
        )
        if len(rows) < 2:
            return None, "[Shibor] 数据不足", {}

        latest = _to_float(rows[0].value)
        prev = _to_float(rows[1].value)
        if latest is None or prev is None:
            return None, "[Shibor] 数据不足", {}

        # Compute average of available readings for context
        valid_vals = [_to_float(r.value) for r in rows if _to_float(r.value) is not None]
        avg_val = sum(valid_vals) / len(valid_vals) if valid_vals else latest

        data = {
            "latest": latest,
            "previous": prev,
            "avg_recent": round(avg_val, 4),
            "date": rows[0].date.isoformat(),
        }

        # Declining Shibor → loose monetary conditions → positive
        if latest < prev and latest < avg_val:
            pts = 25
            desc = "资金面宽松，利率下行"
        elif latest < prev:
            pts = 20
            desc = "利率小幅下行"
        elif latest > prev and latest > avg_val:
            pts = 5
            desc = "资金面收紧，利率上行"
        elif latest > prev:
            pts = 10
            desc = "利率小幅上行"
        else:
            pts = 15
            desc = "利率持平"

        return pts, f"[Shibor ON] {latest:.4f}%，{desc}", data

    def _score_rmb_loan(self) -> tuple:
        """Score new RMB loan vs its average (0-25 pts)."""
        rows = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == "RMB_LOAN")
            .order_by(CnMacroRecord.date.desc())
            .limit(12)
            .all()
        )
        if not rows:
            return None, "[新增贷款] 数据不足", {}

        latest_val = _to_float(rows[0].value)
        if latest_val is None:
            return None, "[新增贷款] 数据不足", {}

        valid_vals = [_to_float(r.value) for r in rows if _to_float(r.value) is not None]
        avg_val = sum(valid_vals) / len(valid_vals) if valid_vals else latest_val

        data = {
            "latest": latest_val,
            "avg_12m": round(avg_val, 2),
            "date": rows[0].date.isoformat(),
        }

        ratio = latest_val / avg_val if avg_val != 0 else 1.0

        if ratio >= 1.2:
            pts = 25
            desc = "信贷投放力度显著超均值"
        elif ratio >= 1.0:
            pts = 20
            desc = "信贷投放高于均值"
        elif ratio >= 0.8:
            pts = 10
            desc = "信贷略低于均值"
        else:
            pts = 5
            desc = "信贷投放明显偏弱"

        return pts, f"[新增贷款] 最新 {latest_val:.0f}，12月均值 {avg_val:.0f}，{desc}", data

    # ------------------------------------------------------------------
    # A-share valuation
    # ------------------------------------------------------------------

    def _assess_ashare_valuation(self) -> tuple:
        """Return (rating: str | None, details: list[str], data: dict)."""
        csi300 = (
            self.db.query(IndexValuationSnapshot)
            .filter(IndexValuationSnapshot.ts_code == "000300.SH")
            .order_by(IndexValuationSnapshot.trade_date.desc())
            .first()
        )
        if csi300 is None or csi300.pe is None:
            return None, ["[A股估值] CSI300估值数据不足"], {}

        pe = _to_float(csi300.pe)
        pb = _to_float(csi300.pb)
        data = {
            "csi300_pe": pe,
            "csi300_pb": pb,
            "date": csi300.trade_date.isoformat(),
        }

        if pe < 12:
            rating = "低估"
            desc = f"CSI300 PE={pe:.1f}，处于历史低位区间，安全边际较高"
        elif pe <= 15:
            rating = "合理"
            desc = f"CSI300 PE={pe:.1f}，估值处于合理区间"
        else:
            rating = "偏高"
            desc = f"CSI300 PE={pe:.1f}，估值偏高，注意回调风险"

        details = [f"[A股估值] {desc}"]

        # Supplement with other indices if available
        for ts_code, label in [
            ("000001.SH", "上证指数"),
            ("399001.SZ", "深证成指"),
            ("399006.SZ", "创业板指"),
        ]:
            snap = (
                self.db.query(IndexValuationSnapshot)
                .filter(IndexValuationSnapshot.ts_code == ts_code)
                .order_by(IndexValuationSnapshot.trade_date.desc())
                .first()
            )
            if snap and snap.pe is not None:
                idx_pe = _to_float(snap.pe)
                data[f"{ts_code}_pe"] = idx_pe
                details.append(f"  {label} PE={idx_pe:.1f}")

        return rating, details, data

    # ------------------------------------------------------------------
    # Overall rating
    # ------------------------------------------------------------------

    def _derive_overall_rating(
        self,
        us_score: Optional[int],
        cn_score: Optional[int],
        val_rating: Optional[str],
        data: dict,
    ) -> tuple:
        """Return (rating_str, recommendations_list)."""
        scores = [s for s in (us_score, cn_score) if s is not None]
        avg = sum(scores) / len(scores) if scores else None

        recommendations: List[str] = []

        # Determine base rating from average score
        if avg is None:
            rating = "数据不足"
            recommendations.append("关键宏观数据缺失，建议检查数据采集是否正常")
            return rating, recommendations

        if avg >= 70:
            rating = "乐观"
        elif avg >= 50:
            rating = "中性"
        elif avg >= 30:
            rating = "谨慎"
        else:
            rating = "防御"

        # Adjust for valuation
        if val_rating == "低估" and rating in ("中性", "谨慎"):
            recommendations.append("A股估值偏低，可适度增配A股权益类资产")
        elif val_rating == "偏高" and rating in ("乐观", "中性"):
            recommendations.append("A股估值偏高，注意控制仓位，可考虑逐步减仓")

        # Specific recommendations based on sub-scores
        if us_score is not None and us_score < 40:
            recommendations.append("美国宏观环境偏弱，关注美元资产风险敞口")
        if cn_score is not None and cn_score < 40:
            recommendations.append("中国宏观环境偏弱，偏防御配置，关注政策刺激信号")

        if us_score is not None and us_score >= 70:
            recommendations.append("美国宏观环境良好，可适度配置美股及美元资产")
        if cn_score is not None and cn_score >= 70:
            recommendations.append("中国宏观环境积极，可增配A股及港股")

        # VIX-based recommendation
        vix_data = data.get("us_macro", {}).get("vix", {})
        vix_val = vix_data.get("value")
        if vix_val is not None and vix_val > 30:
            recommendations.append("VIX处于高位，建议降低风险敞口或使用对冲工具")

        if not recommendations:
            recommendations.append("维持当前配置，持续跟踪宏观数据变化")

        return rating, recommendations

    # ------------------------------------------------------------------
    # DB helper methods
    # ------------------------------------------------------------------

    def _latest_indicator(self, symbol: str) -> Optional[float]:
        """Get the latest value of a MarketIndicatorSnapshot by symbol."""
        row = (
            self.db.query(MarketIndicatorSnapshot)
            .filter(MarketIndicatorSnapshot.symbol == symbol)
            .order_by(MarketIndicatorSnapshot.date.desc())
            .first()
        )
        if row is None:
            return None
        return _to_float(row.value)

    def _latest_yield_spread(self) -> Optional[YieldSpreadRecord]:
        """Get the most recent yield spread record."""
        return (
            self.db.query(YieldSpreadRecord)
            .order_by(YieldSpreadRecord.date.desc())
            .first()
        )

    def _latest_cn_indicator(self, indicator: str) -> Optional[float]:
        """Get the latest value of a CnMacroRecord by indicator name."""
        row = (
            self.db.query(CnMacroRecord)
            .filter(CnMacroRecord.indicator == indicator)
            .order_by(CnMacroRecord.date.desc())
            .first()
        )
        if row is None:
            return None
        return _to_float(row.value)
