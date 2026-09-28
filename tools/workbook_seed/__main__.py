import sys

from tools.workbook_seed.blocks import (
    BLOCKS,
    build_all,
    write_id_ledger,
    write_interblock_seed,
    write_seeds,
)


def main(argv=None) -> int:
    blocks = (argv if argv is not None else sys.argv[1:]) or list(BLOCKS)
    result = build_all()

    for block in blocks:
        built = result.blocks[block]
        write_seeds(built)
        write_id_ledger(built)
        counts = {
            name: len(built.seeds[name])
            for name in ("variables", "parameters", "equations", "aggregation_rules")
        }
        print(f"{block}: {built.workbook.file_name} sha256={built.workbook.sha256} {counts}")

    write_interblock_seed(result)
    interblock = result.interblock
    print(
        f"interblock: {len(interblock.links)} vínculos declarados em fonte, "
        f"{len(interblock.valid)} válidos, {len(interblock.pending)} pendentes de "
        f"carregamento, {len(interblock.rejected)} rejeitados"
    )

    for _link, finding in interblock.findings:
        print(f"[{finding.severity}] {finding.message}", file=sys.stderr)

    if interblock.rejected:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
