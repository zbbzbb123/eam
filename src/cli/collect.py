#!/usr/bin/env python
"""CLI for running data collectors.

Usage:
    python -m src.cli.collect --list          # List all collectors
    python -m src.cli.collect --status        # Show status of each collector
    python -m src.cli.collect --collector fred  # Run specific collector
    python -m src.cli.collect --all           # Run all configured collectors
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


def list_collectors(registry: CollectorRegistry) -> None:
    """List all registered collectors.

    Args:
        registry: CollectorRegistry instance.
    """
    collectors = registry.list_all()

    print("\nRegistered Collectors:")
    print("=" * 60)

    for name in sorted(collectors):
        info = registry.get(name)
        if info:
            type_str = f"[{info.collector_type.value}]"
            print(f"  {name:<20} {type_str:<8} - {info.description}")

    print(f"\nTotal: {len(collectors)} collectors")


def show_status(registry: CollectorRegistry) -> None:
    """Show status of all collectors.

    Args:
        registry: CollectorRegistry instance.
    """
    status = registry.get_status()

    print("\nCollector Status:")
    print("=" * 80)
    print(f"{'Name':<20} {'Type':<8} {'Source':<12} {'Configured':<12} Description")
    print("-" * 80)

    for name in sorted(status.keys()):
        info = status[name]
        configured = "Yes" if info["configured"] else "No"
        configured_color = configured
        print(
            f"{name:<20} "
            f"{info['type']:<8} "
            f"{info['source']:<12} "
            f"{configured_color:<12} "
            f"{info['description'][:30]}"
        )

    # Summary
    configured_count = sum(1 for info in status.values() if info["configured"])
    print("-" * 80)
    print(f"Configured: {configured_count}/{len(status)}")


def run_collector(registry: CollectorRegistry, name: str, output_json: bool = False) -> int:
    """Run a specific collector.

    Args:
        registry: CollectorRegistry instance.
        name: Name of the collector to run.
        output_json: If True, output results as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    info = registry.get(name)
    if not info:
        print(f"Error: Collector '{name}' not found.", file=sys.stderr)
        print(f"Available collectors: {', '.join(registry.list_all())}", file=sys.stderr)
        return 1

    if not info.is_configured():
        print(f"Warning: Collector '{name}' may not be fully configured.", file=sys.stderr)

    print(f"\nRunning collector: {name}")
    print(f"Type: {info.collector_type.value}")
    print(f"Source: {info.source}")
    print("-" * 40)

    try:
        result = registry.run(name)

        if output_json:
            # Try to serialize result to JSON
            try:
                if hasattr(result, "__iter__") and not isinstance(result, (str, dict)):
                    # Convert list of dataclass objects
                    if result and hasattr(result[0], "to_dict"):
                        json_data = [item.to_dict() for item in result]
                    else:
                        json_data = list(result)
                elif isinstance(result, dict):
                    # Handle dict results (possibly with dataclass values)
                    json_data = {}
                    for k, v in result.items():
                        if hasattr(v, "to_dict"):
                            json_data[k] = v.to_dict()
                        elif isinstance(v, list) and v and hasattr(v[0], "to_dict"):
                            json_data[k] = [item.to_dict() for item in v]
                        else:
                            json_data[k] = v
                else:
                    json_data = result

                print(json.dumps(json_data, indent=2, default=str))
            except Exception as e:
                print(f"Could not serialize to JSON: {e}", file=sys.stderr)
                print(f"Raw result: {result}")
        else:
            # Print summary
            if isinstance(result, dict):
                print(f"Result: {len(result)} items")
                for key, value in list(result.items())[:5]:
                    if isinstance(value, list):
                        print(f"  {key}: {len(value)} records")
                    else:
                        print(f"  {key}: {value}")
                if len(result) > 5:
                    print(f"  ... and {len(result) - 5} more")
            elif isinstance(result, list):
                print(f"Result: {len(result)} records")
                for item in result[:3]:
                    if hasattr(item, "to_dict"):
                        print(f"  {item.to_dict()}")
                    else:
                        print(f"  {item}")
                if len(result) > 3:
                    print(f"  ... and {len(result) - 3} more")
            else:
                print(f"Result: {result}")

        print("\nCollector completed successfully.")
        return 0

    except Exception as e:
        print(f"\nError running collector: {e}", file=sys.stderr)
        logger.exception("Collector error")
        return 1


def run_all_collectors(
    registry: CollectorRegistry,
    only_configured: bool = True,
    output_json: bool = False,
) -> int:
    """Run all collectors.

    Args:
        registry: CollectorRegistry instance.
        only_configured: If True, only run configured collectors.
        output_json: If True, output results as JSON.

    Returns:
        Exit code (0 for success, 1 if any errors).
    """
    print("\nRunning all collectors...")
    print("=" * 60)

    results = registry.run_all(only_configured=only_configured, stop_on_error=False)

    success_count = 0
    error_count = 0
    skipped_count = 0

    for name, result in results.items():
        status = result.get("status", "unknown")

        if status == "success":
            success_count += 1
            data = result.get("data")
            if isinstance(data, dict):
                count = len(data)
            elif isinstance(data, list):
                count = len(data)
            else:
                count = 1
            print(f"  [OK]      {name}: {count} items")
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

    if output_json:
        # Output full results as JSON
        print("\nJSON Output:")
        print(json.dumps(results, indent=2, default=str))

    return 0 if error_count == 0 else 1


def main(args: Optional[list] = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command line arguments (defaults to sys.argv).

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="EAM Data Collector CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.collect --list
  python -m src.cli.collect --status
  python -m src.cli.collect --collector fred
  python -m src.cli.collect --collector openinsider --json
  python -m src.cli.collect --all
        """,
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all registered collectors",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show status of each collector (configured/not configured)",
    )
    parser.add_argument(
        "--collector", "-c",
        type=str,
        metavar="NAME",
        help="Run a specific collector by name",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all configured collectors",
    )
    parser.add_argument(
        "--include-unconfigured",
        action="store_true",
        help="Include unconfigured collectors when running --all",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parsed_args = parser.parse_args(args)

    # Set logging level
    if parsed_args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get registry
    registry = get_registry()

    # Execute command
    if parsed_args.list:
        list_collectors(registry)
        return 0

    if parsed_args.status:
        show_status(registry)
        return 0

    if parsed_args.collector:
        return run_collector(registry, parsed_args.collector, output_json=parsed_args.json)

    if parsed_args.all:
        return run_all_collectors(
            registry,
            only_configured=not parsed_args.include_unconfigured,
            output_json=parsed_args.json,
        )

    # No command specified, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
