"""Analyzers API endpoints."""
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.analyzers.precious_metals import PreciousMetalsAnalyzer
from src.analyzers.macro import MacroAnalyzer
from src.analyzers.price_alerts import PriceAlertAnalyzer
from src.services.analyzer_runner import AnalyzerRunner

router = APIRouter(prefix="/analyzers", tags=["analyzers"])

# Registry of available analyzers
ANALYZER_REGISTRY = {
    "precious_metals": {
        "name": "Precious Metals Analyzer",
        "description": "Monitors gold/silver ratio and TIPS yields",
        "class": PreciousMetalsAnalyzer,
        "requires_db": False,
    },
    "macro": {
        "name": "Macro Analyzer",
        "description": "Monitors FOMC schedule and interest rate environment",
        "class": MacroAnalyzer,
        "requires_db": False,
    },
    "price_alerts": {
        "name": "Price Alert Analyzer",
        "description": "Monitors stop loss and take profit levels for holdings",
        "class": PriceAlertAnalyzer,
        "requires_db": True,
    },
}


@router.get("")
def list_analyzers() -> Dict[str, Any]:
    """List all available analyzers."""
    analyzers = []
    for key, info in ANALYZER_REGISTRY.items():
        analyzers.append({
            "id": key,
            "name": info["name"],
            "description": info["description"],
        })
    return {"analyzers": analyzers}


@router.post("/{analyzer_id}/run")
def run_analyzer(analyzer_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run a specific analyzer and create signals."""
    if analyzer_id not in ANALYZER_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analyzer '{analyzer_id}' not found"
        )

    info = ANALYZER_REGISTRY[analyzer_id]

    # Create analyzer instance
    if info["requires_db"]:
        analyzer = info["class"](db)
    else:
        analyzer = info["class"]()

    # Run analyzer
    runner = AnalyzerRunner(db)
    signals = runner.run_analyzer(analyzer)

    return {
        "analyzer": analyzer_id,
        "signals_created": len(signals),
        "signal_ids": [s.id for s in signals],
    }


@router.post("/run-all")
def run_all_analyzers(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Run all analyzers and create signals."""
    runner = AnalyzerRunner(db)

    # Register all analyzers
    for key, info in ANALYZER_REGISTRY.items():
        if info["requires_db"]:
            analyzer = info["class"](db)
        else:
            analyzer = info["class"]()
        runner.register_analyzer(analyzer)

    # Run all
    signals = runner.run_all()

    return {
        "total_signals": len(signals),
        "signal_ids": [s.id for s in signals],
        "analyzers_run": list(ANALYZER_REGISTRY.keys()),
    }
