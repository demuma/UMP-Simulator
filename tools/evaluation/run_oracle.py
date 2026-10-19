#!/usr/bin/env python3
"""Independently validate JSON replay/config/result files without simulation or MongoDB.

The new output is a private diagnostic report. --feasibility additionally compares
actual windows with bounded tiny-case best cuts; it is deliberately off by default.
Exit codes: 0 valid; 1 violations recorded; 2 bad input, budget or file error.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from oracle import analyze_windows, validate_result


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON key: {name}")
        result[name] = value
    return result


def _read(path):
    if not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Inputs must be regular JSON files of at most 256 MiB")
    def reject(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    return json.loads(path.read_text(), object_pairs_hook=_unique, parse_constant=reject)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Frozen observations JSON")
    parser.add_argument("--config", type=Path, required=True, help="Policy JSON (YAML not accepted by this independent adapter)")
    parser.add_argument("--result", type=Path, required=True, help="AggregationReplay private result JSON")
    parser.add_argument("--output", type=Path, required=True, help="New private report JSON; existing files are never replaced")
    parser.add_argument("--analyze-small", "--feasibility", dest="feasibility", action="store_true", help="Also enumerate bounded alternatives on actual retired windows")
    parser.add_argument("--max-nodes", type=int, default=1024)
    parser.add_argument("--max-cells", type=int, default=20000)
    args = parser.parse_args(argv)
    temporary = None
    try:
        if args.output.exists():
            raise ValueError("Output already exists")
        replay, config, result = _read(args.input), _read(args.config), _read(args.result)
        report = validate_result(replay, config, result, max_cells=args.max_cells)
        if args.feasibility and report["valid"]:
            report["feasibility"] = analyze_windows(replay, config, result,
                max_nodes=args.max_nodes, max_cells=args.max_cells)
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        # A private same-directory temporary is fully flushed before exclusive
        # hard-link publication; an existing/racing destination is never replaced.
        with tempfile.NamedTemporaryFile(mode="w", prefix=".ump-oracle-", dir=args.output.parent,
                                         delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, args.output)
        temporary.unlink()
        temporary = None
        print(f"Oracle report: {args.output}; valid={report['valid']}; released_cells={report['released_cell_count']}")
        return 0 if report["valid"] else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(f"Independent oracle: {error}", file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
