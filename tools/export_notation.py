#!/usr/bin/env python3
"""Export canonical display equations for reuse in papers and Beamer sources."""
import argparse
from pathlib import Path


def export(source):
    formulas, current = [], None
    for line in source.splitlines():
        if line.strip() == '$$':
            if current is None:
                current = []
            else:
                formula = '\n'.join(current).strip()
                if not formula:
                    raise ValueError('Empty display equation')
                formulas.append(formula)
                current = None
        elif current is not None:
            current.append(line)
    if current is not None or not formulas:
        raise ValueError('Unclosed display equation or no display equations')
    header = ('% Generated from docs/TERMINOLOGY_AND_NOTATION.md; do not edit.\n'
              '% Regenerate: python3 tools/export_notation.py\n'
              '% Requires amsmath and amssymb. Definitions and scope are in the Markdown source.\n')
    return header + '\n\n'.join('\\begin{equation}\n' + formula + '\n\\end{equation}'
                                for formula in formulas) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if the generated fragment is stale')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / 'docs/TERMINOLOGY_AND_NOTATION.md'
    target = root / 'docs/notation/ump_equations.tex'
    expected = export(source.read_text())
    if args.check:
        if not target.is_file() or target.read_text() != expected:
            parser.exit(1, 'Notation export is stale; run python3 tools/export_notation.py\n')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected)
    print(f'{"Checked" if args.check else "Exported"}: {target.relative_to(root)}')


if __name__ == '__main__':
    main()
