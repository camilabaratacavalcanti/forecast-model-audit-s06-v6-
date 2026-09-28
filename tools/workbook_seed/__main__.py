import sys

from tools.workbook_seed.blocks import BLOCKS, build_block, write_seeds


def main(argv=None) -> int:
    blocks = (argv if argv is not None else sys.argv[1:]) or list(BLOCKS)

    for block in blocks:
        result = build_block(block)
        write_seeds(result)
        counts = {
            name: len(result.seeds[name])
            for name in ("variables", "parameters", "equations", "aggregation_rules")
        }
        print(f"{block}: {result.workbook.file_name} sha256={result.workbook.sha256} {counts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
