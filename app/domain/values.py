"""
Tipos de valor da plataforma.

Um valor de cálculo é numérico (o caso geral) ou categórico (texto).
Não existe um terceiro tipo aberto (`Any`): todo ponto que armazena,
lê ou avalia um valor aceita exatamente `ScalarValue`.

    numeric      int | float (bool nunca é aceito)
    categorical  str

O marcador de falha condicional `CONDITIONAL_FAILURE` ("F") é o
resultado de uma rotina condicional (IF) que falhou. Ele é um texto,
mas não é um valor de negócio: pode ser armazenado como resultado de
qualquer variável e repassado sem alteração, porém nunca é convertido
em número (0, NaN ou None). Qualquer operação que o consuma — aritmética,
função, ordenação, condição, agregação — falha explicitamente. A única
leitura permitida é a comparação de igualdade com o próprio marcador
(`VAR == "F"` / `VAR != "F"`), que detecta a falha sem convertê-la.
"""

NumericValue = int | float
CategoricalValue = str
ScalarValue = NumericValue | CategoricalValue

NUMERIC = "numeric"
CATEGORICAL = "categorical"

VALUE_TYPES = frozenset({NUMERIC, CATEGORICAL})

CONDITIONAL_FAILURE = "F"


def is_numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_conditional_failure(value) -> bool:
    return isinstance(value, str) and value == CONDITIONAL_FAILURE
