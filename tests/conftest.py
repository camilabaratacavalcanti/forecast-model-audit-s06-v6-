"""
Stage 4C — configuração única da referência de baseline para a suíte (DR-4C-8).

Só fixa, em processo, o diretório de baseline do registro (`current`) para os harnesses importados
pelos testes (`baseline_paths.configure`). Não altera coleta, marcação nem asserção. Em B0 o
diretório é None: os caminhos históricos são usados exatamente como antes da 4C.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audit" / "baselines"))

import baseline_registry  # noqa: E402

baseline_registry.configure_current()
