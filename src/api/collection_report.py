"""Daily collection report API — summarizes data collected per day."""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models_market_data import (
    CnMacroRecord,
    FundamentalSnapshot,
    FundNavSnapshot,
    IndexValuationSnapshot,
    MacroData,
    MarketBreadthSnapshot,
    MarketIndicatorSnapshot,
    NorthboundFlow,
    SectorFlowSnapshot,
    SectorSnapshot,
    YieldSpreadRecord,
)

router = APIRouter(prefix="/collection-report", tags=["collection-report"])

# Table definitions: (name, model, date_column_or_None_for_created_at)
_TABLES = [
    ("北向资金", NorthboundFlow, "trade_date"),
    ("板块行情", SectorSnapshot, "snapshot_date"),
    ("板块资金流", SectorFlowSnapshot, "snapshot_date"),
    ("市场指标", MarketIndicatorSnapshot, "date"),
    ("A股涨跌家数", MarketBreadthSnapshot, "snapshot_date"),
    ("个股基本面", FundamentalSnapshot, "snapshot_date"),
    ("指数估值", IndexValuationSnapshot, "trade_date"),
    ("ETF净值", FundNavSnapshot, "nav_date"),
    ("FRED宏观", MacroData, None),  # uses created_at
    ("美债利差", YieldSpreadRecord, "date"),
    ("中国宏观", CnMacroRecord, None),  # uses created_at
]


def _count_by_date(db: Session, model, date_col, target_date: date) -> int:
    """Count rows in a table where date_col == target_date."""
    return db.query(func.count(model.id)).filter(date_col == target_date).scalar() or 0


def _count_by_created(db: Session, model, target_date: date) -> int:
    """Count rows created on target_date (using created_at timestamp)."""
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    return db.query(func.count(model.id)).filter(
        model.created_at.between(start, end)
    ).scalar() or 0


@router.get("")
def get_collection_report(
    report_date: Optional[date] = Query(None, description="日期，默认今天"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """获取指定日期的数据采集日报。

    返回每张采集表在该日期的入库行数和关键摘要。
    """
    target = report_date or date.today()

    sections: List[Dict[str, Any]] = []

    # 1. 北向资金
    nb_count = _count_by_date(db, NorthboundFlow, NorthboundFlow.trade_date, target)
    nb_detail = None
    if nb_count:
        row = db.query(NorthboundFlow).filter(NorthboundFlow.trade_date == target).first()
        if row:
            nb_detail = f"净流入 {row.net_flow} 亿"
    sections.append({
        "name": "北向资金",
        "table": "northbound_flow",
        "count": nb_count,
        "detail": nb_detail,
    })

    # 2. 板块行情
    sec_count = _count_by_date(db, SectorSnapshot, SectorSnapshot.snapshot_date, target)
    sec_detail = None
    if sec_count:
        industry = db.query(func.count(SectorSnapshot.id)).filter(
            SectorSnapshot.snapshot_date == target,
            SectorSnapshot.sector_type == "industry",
        ).scalar() or 0
        concept = sec_count - industry
        sec_detail = f"行业 {industry} / 概念 {concept}"
    sections.append({
        "name": "板块行情",
        "table": "sector_snapshots",
        "count": sec_count,
        "detail": sec_detail,
    })

    # 3. 板块资金流
    sf_count = _count_by_date(db, SectorFlowSnapshot, SectorFlowSnapshot.snapshot_date, target)
    sf_detail = None
    if sf_count:
        top = db.query(SectorFlowSnapshot).filter(
            SectorFlowSnapshot.snapshot_date == target,
            SectorFlowSnapshot.sector_type == "industry",
        ).order_by(SectorFlowSnapshot.main_net_inflow.desc()).first()
        if top:
            sf_detail = f"主力净流入最多: {top.name} ({top.main_net_inflow})"
    sections.append({
        "name": "板块资金流",
        "table": "sector_flow_snapshots",
        "count": sf_count,
        "detail": sf_detail,
    })

    # 4. 市场指标 (VIX/黄金/原油/汇率)
    mi_count = _count_by_date(db, MarketIndicatorSnapshot, MarketIndicatorSnapshot.date, target)
    mi_detail = None
    if mi_count:
        rows = db.query(MarketIndicatorSnapshot).filter(
            MarketIndicatorSnapshot.date == target,
        ).all()
        mi_detail = ", ".join(f"{r.name} {r.value}" for r in rows)
    sections.append({
        "name": "市场指标",
        "table": "market_indicator_snapshots",
        "count": mi_count,
        "detail": mi_detail,
    })

    # 5. A股涨跌家数
    mb_count = _count_by_date(db, MarketBreadthSnapshot, MarketBreadthSnapshot.snapshot_date, target)
    mb_detail = None
    if mb_count:
        rows = db.query(MarketBreadthSnapshot).filter(
            MarketBreadthSnapshot.snapshot_date == target,
        ).all()
        mb_detail = " | ".join(
            f"{r.index_name} 涨{r.advancing}/跌{r.declining}" for r in rows
        )
    sections.append({
        "name": "A股涨跌家数",
        "table": "market_breadth_snapshots",
        "count": mb_count,
        "detail": mb_detail,
    })

    # 6. 个股基本面
    fs_count = _count_by_date(db, FundamentalSnapshot, FundamentalSnapshot.snapshot_date, target)
    fs_detail = None
    if fs_count:
        symbols = db.query(FundamentalSnapshot.symbol).filter(
            FundamentalSnapshot.snapshot_date == target,
        ).all()
        fs_detail = ", ".join(s[0] for s in symbols)
    sections.append({
        "name": "个股基本面",
        "table": "fundamental_snapshots",
        "count": fs_count,
        "detail": fs_detail,
    })

    # 7. FRED 宏观
    macro_count = _count_by_created(db, MacroData, target)
    macro_detail = None
    if macro_count:
        series = db.query(MacroData.series_id, func.count(MacroData.id)).filter(
            MacroData.created_at.between(
                datetime(target.year, target.month, target.day),
                datetime(target.year, target.month, target.day, 23, 59, 59),
            )
        ).group_by(MacroData.series_id).all()
        macro_detail = ", ".join(f"{s[0]}({s[1]})" for s in series)
    sections.append({
        "name": "FRED宏观",
        "table": "macro_data",
        "count": macro_count,
        "detail": macro_detail,
    })

    # 8. 美债利差
    ys_count = _count_by_date(db, YieldSpreadRecord, YieldSpreadRecord.date, target)
    ys_detail = None
    if ys_count:
        row = db.query(YieldSpreadRecord).filter(YieldSpreadRecord.date == target).first()
        if row:
            ys_detail = f"10Y={row.dgs10} 2Y={row.dgs2} 利差={row.spread}"
    sections.append({
        "name": "美债利差",
        "table": "yield_spreads",
        "count": ys_count,
        "detail": ys_detail,
    })

    # 9. 中国宏观 (PMI/CPI/M2/Shibor/贷款)
    cn_count = _count_by_created(db, CnMacroRecord, target)
    cn_detail = None
    if cn_count:
        indicators = db.query(CnMacroRecord.indicator, func.count(CnMacroRecord.id)).filter(
            CnMacroRecord.created_at.between(
                datetime(target.year, target.month, target.day),
                datetime(target.year, target.month, target.day, 23, 59, 59),
            )
        ).group_by(CnMacroRecord.indicator).all()
        cn_detail = ", ".join(f"{i[0]}({i[1]})" for i in indicators)
    sections.append({
        "name": "中国宏观",
        "table": "cn_macro_data",
        "count": cn_count,
        "detail": cn_detail,
    })

    # Summary
    total = sum(s["count"] for s in sections)
    collected = sum(1 for s in sections if s["count"] > 0)

    return {
        "date": target.isoformat(),
        "total_records": total,
        "sources_collected": f"{collected}/{len(sections)}",
        "sections": sections,
    }


def _daily_counts(db: Session, target: date) -> Dict[str, int]:
    """Return {table_name: count} for a single date."""
    result = {}
    for name, model, date_attr in _TABLES:
        if date_attr:
            col = getattr(model, date_attr)
            count = db.query(func.count(model.id)).filter(col == target).scalar() or 0
        else:
            count = _count_by_created(db, model, target)
        result[name] = count
    return result


@router.get("/range")
def get_collection_report_range(
    start: Optional[date] = Query(None, description="起始日期，默认7天前"),
    end: Optional[date] = Query(None, description="结束日期，默认今天"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """获取日期范围内每天的采集记录数。

    用于前端看板展示，默认返回过去7天。
    """
    end_date = end or date.today()
    start_date = start or (end_date - timedelta(days=6))

    source_names = [t[0] for t in _TABLES]
    days: List[Dict[str, Any]] = []
    current = start_date
    while current <= end_date:
        counts = _daily_counts(db, current)
        total = sum(counts.values())
        collected = sum(1 for v in counts.values() if v > 0)
        days.append({
            "date": current.isoformat(),
            "total": total,
            "sources_collected": collected,
            "sources_total": len(source_names),
            "counts": counts,
        })
        current += timedelta(days=1)

    return {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "source_names": source_names,
        "days": days,
    }
