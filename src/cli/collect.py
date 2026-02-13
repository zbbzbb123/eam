#!/usr/bin/env python
"""CLI for running data collectors with database storage.

Usage:
    python -m src.cli.collect --list          # List all collectors
    python -m src.cli.collect --status        # Show status of each collector
    python -m src.cli.collect --collector fred  # Run specific collector (fetch + store)
    python -m src.cli.collect --all           # Run all configured collectors (fetch + store)
    python -m src.cli.collect --all --dry-run # Run all collectors without storing
"""
import argparse
import json
import logging
import sys
from typing import Optional

from src.collectors.registry import get_registry, CollectorRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Mapping from collector name to StorageService method name
_STORAGE_MAP = {
    "northbound": "store_northbound_flow",
    "sector": "store_sectors",
    "market_indicators": "store_market_indicators",
    "fundamentals": "store_fundamentals",
    "sector_flow": "store_sector_flows",
    "market_breadth": "store_market_breadth",
    "tushare": "store_tushare_data",
    "fred": "store_fred_data",
    "cn_macro": "store_cn_macro",
}


def _store_result(storage, name: str, data) -> int:
    """Store collector result using the appropriate StorageService method.

    Returns number of stored records, or -1 if no storage method exists.
    """
    method_name = _STORAGE_MAP.get(name)
    if not method_name:
        return -1
    method = getattr(storage, method_name, None)
    if not method:
        return -1
    return method(data)


def list_collectors(registry: CollectorRegistry) -> None:
    """List all registered collectors."""
    collectors = registry.list_all()
    print("\nRegistered Collectors:")
    print("=" * 60)
    for name in sorted(collectors):
        info = registry.get(name)
        if info:
            type_str = f"[{info.collector_type.value}]"
            has_storage = "DB" if name in _STORAGE_MAP else "--"
            print(f"  {name:<20} {type_str:<8} {has_storage:<4} {info.description}")
    print(f"\nTotal: {len(collectors)} collectors")


def show_status(registry: CollectorRegistry) -> None:
    """Show status of all collectors."""
    status = registry.get_status()
    print("\nCollector Status:")
    print("=" * 80)
    print(f"{'Name':<20} {'Type':<8} {'Source':<12} {'Configured':<12} Description")
    print("-" * 80)
    for name in sorted(status.keys()):
        info = status[name]
        configured = "Yes" if info["configured"] else "No"
        print(
            f"{name:<20} "
            f"{info['type']:<8} "
            f"{info['source']:<12} "
            f"{configured:<12} "
            f"{info['description'][:30]}"
        )
    configured_count = sum(1 for info in status.values() if info["configured"])
    print("-" * 80)
    print(f"Configured: {configured_count}/{len(status)}")


def run_collector(registry: CollectorRegistry, name: str, dry_run: bool = False, output_json: bool = False) -> int:
    """Run a specific collector and store results."""
    info = registry.get(name)
    if not info:
        print(f"Error: Collector '{name}' not found.", file=sys.stderr)
        return 1

    if not info.is_configured():
        print(f"Warning: Collector '{name}' may not be fully configured.", file=sys.stderr)

    print(f"\nRunning collector: {name}")
    print("-" * 40)

    try:
        result = registry.run(name)

        # Print summary
        if isinstance(result, dict):
            count = sum(len(v) if isinstance(v, list) else 1 for v in result.values())
            print(f"  Fetched: {count} items")
        elif isinstance(result, list):
            print(f"  Fetched: {len(result)} records")
        else:
            print(f"  Fetched: {result}")

        # Store to database
        if not dry_run:
            from src.db.database import SessionLocal
            from src.services.storage import StorageService
            db = SessionLocal()
            try:
                storage = StorageService(db)
                stored = _store_result(storage, name, result)
                if stored >= 0:
                    print(f"  Stored:  {stored} records to DB")
                else:
                    print(f"  Storage: no DB mapping for '{name}' (data not persisted)")
            finally:
                db.close()
        else:
            print("  (dry-run: data not stored)")

        if output_json:
            print(json.dumps(result, indent=2, default=str))

        return 0

    except Exception as e:
        print(f"\nError running collector: {e}", file=sys.stderr)
        logger.exception("Collector error")
        return 1


def run_all_collectors(
    registry: CollectorRegistry,
    only_configured: bool = True,
    dry_run: bool = False,
    output_json: bool = False,
) -> int:
    """Run all collectors and store results to DB."""
    print("\nRunning all collectors...")
    print("=" * 60)

    from src.db.database import SessionLocal
    from src.services.storage import StorageService

    db = SessionLocal() if not dry_run else None
    storage = StorageService(db) if db else None

    try:
        results = registry.run_all(only_configured=only_configured, stop_on_error=False)

        success_count = 0
        error_count = 0
        skipped_count = 0
        stored_total = 0

        for name, result in results.items():
            status = result.get("status", "unknown")

            if status == "success":
                success_count += 1
                data = result.get("data")

                # Count fetched items
                if isinstance(data, dict):
                    count = sum(len(v) if isinstance(v, list) else 1 for v in data.values())
                elif isinstance(data, list):
                    count = len(data)
                else:
                    count = 1

                # Store to DB
                stored = 0
                if storage and not dry_run:
                    try:
                        stored = _store_result(storage, name, data)
                        if stored >= 0:
                            stored_total += stored
                        else:
                            stored = 0  # no mapping
                    except Exception as e:
                        logger.error(f"Failed to store {name}: {e}")
                        stored = -1

                if stored < 0:
                    print(f"  [OK]      {name}: {count} fetched, STORE FAILED")
                elif dry_run:
                    print(f"  [OK]      {name}: {count} fetched (dry-run)")
                else:
                    print(f"  [OK]      {name}: {count} fetched, {stored} stored")

            elif status == "skipped":
                skipped_count += 1
                reason = result.get("reason", "unknown")
                print(f"  [SKIPPED] {name}: {reason}")
            else:
                error_count += 1
                error = result.get("error", "unknown error")
                print(f"  [ERROR]   {name}: {error}")

        print("-" * 60)
        print(f"Summary: {success_count} succeeded, {error_count} failed, {skipped_count} skipped")
        if not dry_run:
            print(f"Total stored to DB: {stored_total} records")

        return 0 if error_count == 0 else 1

    finally:
        if db:
            db.close()


def main(args: Optional[list] = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="EAM Data Collector CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.collect --list
  python -m src.cli.collect --status
  python -m src.cli.collect --collector fred
  python -m src.cli.collect --all
  python -m src.cli.collect --all --dry-run
        """,
    )

    parser.add_argument("--list", "-l", action="store_true", help="List all registered collectors")
    parser.add_argument("--status", "-s", action="store_true", help="Show status of each collector")
    parser.add_argument("--collector", "-c", type=str, metavar="NAME", help="Run a specific collector")
    parser.add_argument("--all", "-a", action="store_true", help="Run all configured collectors")
    parser.add_argument("--include-unconfigured", action="store_true", help="Include unconfigured collectors")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data without storing to DB")
    parser.add_argument("--json", "-j", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    parsed_args = parser.parse_args(args)

    if parsed_args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    registry = get_registry()

    if parsed_args.list:
        list_collectors(registry)
        return 0

    if parsed_args.status:
        show_status(registry)
        return 0

    if parsed_args.collector:
        return run_collector(registry, parsed_args.collector, dry_run=parsed_args.dry_run, output_json=parsed_args.json)

    if parsed_args.all:
        return run_all_collectors(
            registry,
            only_configured=not parsed_args.include_unconfigured,
            dry_run=parsed_args.dry_run,
            output_json=parsed_args.json,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
