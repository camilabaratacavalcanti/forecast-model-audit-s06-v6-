"""
Builder do bloco `max_ht` a partir do workbook aprovado.

Toda a lógica é a do builder comum (`tools.workbook_seed`): leitura
com cabeçalho localizado e janela derivada do conteúdo, modelo
canônico com definições e instâncias por escopo, resolução de nomes da
plataforma e agregações derivadas do texto da expressão. Este módulo
apenas identifica o workbook aprovado do bloco.

    python -m tools.max_ht_seed_builder        (regrava data/seed/max_ht/)
"""

from tools.workbook_seed.blocks import BLOCKS, BuildResult, build_block, write_seeds

BLOCK = "max_ht"
SPEC = BLOCKS[BLOCK]


def build(workbook_path=None) -> BuildResult:
    return build_block(BLOCK, workbook_path)


def main() -> int:
    result = build()
    write_seeds(result)
    print(
        f"{BLOCK}: {result.workbook.file_name} "
        f"sha256={result.workbook.sha256} "
        + " ".join(
            f"{name}={len(result.seeds[name])}"
            for name in ("variables", "parameters", "equations", "aggregation_rules")
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
