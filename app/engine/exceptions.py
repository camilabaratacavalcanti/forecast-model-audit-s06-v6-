"""
Centraliza as exceções específicas do domínio do Engine,
como expressão insegura, erro de avaliação e variável/parâmetro inexistente.
"""


class EquationEngineError(Exception):
    """
    Erro base do Equation Engine.
    """


class InvalidExpressionError(EquationEngineError):
    """
    A expressão possui sintaxe inválida.
    """


class UnsafeExpressionError(EquationEngineError):
    """
    A expressão contém elemento não permitido.
    """


class VariableNotFoundError(EquationEngineError):
    """
    A variável necessária para o cálculo não foi encontrada.
    """


class ParameterNotFoundError(EquationEngineError):
    """
    O parâmetro necessário para o cálculo não foi encontrado.
    """


class CalculationValueError(EquationEngineError):
    """
    O valor fornecido para uma variável ou parâmetro é inválido.
    """


class EvaluationError(EquationEngineError):
    """
    Erro durante a avaliação da expressão.
    """


class DivisionByZeroError(EvaluationError):
    """
    Indica que uma operação de divisão ou módulo tentou
    utilizar zero como denominador.
    """

    def __init__(
        self,
        *,
        operation: str,
        left_value: int | float,
        right_value: int | float,
    ):
        self.operation = operation
        self.left_value = left_value
        self.right_value = right_value

        super().__init__(
            f"Divisão por zero durante a operação "
            f"'{operation}': "
            f"{left_value} {operation} {right_value}."
        )


class ExpressionTypeError(EvaluationError):
    """
    Operação com tipos incompatíveis: aritmética ou função com texto,
    comparação entre número e texto, ordenação de textos, operando de
    and/or que não é booleano, ou resultado final booleano.
    """


class MathDomainError(EvaluationError):
    """
    Argumento fora do domínio de uma função matemática permitida
    (ex.: ln(x) com x <= 0).
    """

    def __init__(self, function_name: str, argument):
        self.function_name = function_name
        self.argument = argument

        super().__init__(
            f"{function_name}({argument!r}) fora do domínio da função."
        )


class ConditionalFailureError(EvaluationError):
    """
    Um operando vale o marcador de falha condicional ("F"): o valor
    de origem é uma rotina condicional que falhou. A falha não é
    convertida em número; ela interrompe o cálculo consumidor.
    """


class EquationEvaluationError(EvaluationError):
    """
    Erro de avaliação de uma Equation, enriquecido com o contexto
    da equação que estava sendo executada.
    """

    def __init__(
        self,
        *,
        equation_id: str,
        target_variable_id: str,
        expression: str,
        original_error: Exception,
    ):
        self.equation_id = equation_id
        self.target_variable_id = target_variable_id
        self.expression = expression
        self.original_error = original_error

        super().__init__(
            f"Erro ao avaliar a equação "
            f"'{equation_id}' para a variável alvo "
            f"'{target_variable_id}' "
            f"com a expressão '{expression}': "
            f"{original_error}"
        )


class EquationNotFoundError(EquationEngineError):
    """
    A equação solicitada não foi encontrada.
    """


class DependencyCycleError(Exception):
    """
    Indica que existe um ciclo de dependências entre equações.
    """

    def __init__(
        self,
        cycle: tuple[str, ...],
    ):
        self.cycle = cycle

        cycle_path = " → ".join(cycle)

        super().__init__(
            f"Ciclo de dependências detectado: "
            f"{cycle_path}"
        )


class DuplicateVariableProducerError(Exception):
    """
    Indica que mais de uma equação produz a mesma variável.
    """


class RegistryIntegrityError(Exception):
    """
    Erro de integridade entre os Registries.
    """
    pass


class VariableReferenceNotFoundError(RegistryIntegrityError):
    """
    Indica que uma equação referencia uma variável
    que não existe no VariableRegistry.
    """
    pass


class ParameterReferenceNotFoundError(RegistryIntegrityError):
    """
    Indica que uma equação referencia um parâmetro
    que não existe no ParameterRegistry.
    """
    pass


class TargetVariableNotFoundError(RegistryIntegrityError):
    """
    Indica que a variável alvo de uma equação
    não existe no VariableRegistry.
    """
    pass


class EquationTargetScopeMismatchError(RegistryIntegrityError):
    """
    Indica que o escopo declarado de uma EquationDefinition
    (scope_type/scope_value) não corresponde ao escopo declarado
    da VariableDefinition que ela produz.
    """
    pass


class TemporalAggregationError(Exception):
    """
    Erro base da camada de Temporal Aggregation (Fase B).
    """


class InvalidAggregationRuleError(TemporalAggregationError):
    """
    A AggregationRule está mal formada: tipo de agregação não
    suportado, WEIGHTED_AVERAGE sem weight_variable_id, ou janela
    explícita inconsistente (apenas um dos dois extremos informado,
    ou start_date posterior a end_date).
    """


class EmptyAggregationWindowError(TemporalAggregationError):
    """
    Nenhum valor de origem foi encontrado dentro da janela temporal
    da agregação (janela vazia de dados, não de erro de leitura).
    """


class AggregationScopeMismatchError(TemporalAggregationError):
    """
    Uma AggregationRule não tem nenhuma instância espacial aplicável:
    a origem (ou o peso) não existe em nenhum escopo concreto do alvo.
    O serviço de agregação lê a origem exatamente no escopo do alvo,
    então a regra não teria onde ser executada.
    """


class AggregationFailureError(TemporalAggregationError):
    """
    A série de origem contém o marcador de falha condicional ("F").
    A agregação não produz um número a partir de uma falha: a falha
    é preservada e reportada com os períodos afetados.
    """

    def __init__(self, rule_id: str, failed_period_ids: list[str]):
        self.rule_id = rule_id
        self.failed_period_ids = list(failed_period_ids)

        super().__init__(
            f"Regra {rule_id}: a série de origem contém falha "
            f"condicional ('F') nos períodos {self.failed_period_ids}; "
            "a agregação não pode produzir um valor numérico."
        )


class NonNumericAggregationError(TemporalAggregationError):
    """
    A série de origem contém valores categóricos (texto), que não
    podem ser somados nem ponderados.
    """


class ZeroWeightSumError(TemporalAggregationError):
    """
    A soma dos pesos de uma WEIGHTED_AVERAGE é zero.

    O resultado não pode ser determinado por divisão (e não deve
    ser mascarado silenciosamente com um valor arbitrário como 0),
    então este erro é propagado explicitamente ao chamador.
    """


class AmbiguousSpatialPrecedenceError(Exception):
    """
    Indica que dois ou mais candidatos espaciais (linha_grupo) que
    contêm o mesmo scope consumidor não são comparáveis entre si por
    inclusão de conjuntos (nem G1 ⊂ G2, nem G2 ⊂ G1).

    A precedência espacial não pode ser determinada silenciosamente
    nesse caso: este erro é propagado explicitamente em vez de
    escolher arbitrariamente um dos candidatos.
    """

    def __init__(
        self,
        *,
        scope_type: str,
        scope_value: str,
        candidate_a: str,
        candidate_b: str,
    ):
        self.scope_type = scope_type
        self.scope_value = scope_value
        self.candidate_a = candidate_a
        self.candidate_b = candidate_b

        super().__init__(
            f"Precedência espacial ambígua para "
            f"{scope_type}/{scope_value}: os candidatos "
            f"'{candidate_a}' e '{candidate_b}' não são "
            f"comparáveis por inclusão de conjuntos."
        )


# ============================================================
# Vínculos interbloco em runtime (Etapa 3.1)
# ============================================================


class InterblockRuntimeError(Exception):
    """
    Erro base da resolução interbloco em runtime.

    Todo erro carrega `code` (estável, no padrão INTERBLOCK_* dos
    contratos da Etapa 2.6) e os dados necessários para identificar o
    vínculo: bloco consumidor, variável, instância, bloco produtor,
    frequência e período, quando aplicáveis.
    """

    code = "INTERBLOCK_RUNTIME_ERROR"

    def __init__(self, message: str, **details):
        self.details = details
        super().__init__(f"{self.code}: {message}")


class InterblockSeedError(InterblockRuntimeError):
    """
    O artefato canônico `interblock_links.json` (ou um registro dele)
    não satisfaz o contrato: o vínculo não é aceito como válido.
    """

    code = "INTERBLOCK_SEED_INVALID"


class InterblockCycleError(InterblockSeedError):
    """
    Os vínculos canônicos formam um ciclo: rejeitado antes da execução.
    """

    code = "INTERBLOCK_CYCLE"


class InterblockLinkNotFoundError(InterblockRuntimeError):
    """
    A variável não é consumidora de nenhum vínculo interbloco canônico.
    """

    code = "INTERBLOCK_LINK_NOT_FOUND"


class InterblockSourceNotLoadedError(InterblockRuntimeError):
    """
    O vínculo aponta um bloco oficial cujo workbook ainda não está
    carregado (estado pendente D26-01): não há produtor, não há valor.
    """

    code = "INTERBLOCK_SOURCE_NOT_LOADED"


class InterblockLinkRejectedError(InterblockRuntimeError):
    """
    O vínculo foi rejeitado pela validação de build: nunca é consumido.
    """

    code = "INTERBLOCK_LINK_REJECTED"


class InterblockInstanceNotDeclaredError(InterblockRuntimeError):
    """
    A instância pedida não pertence às instâncias validadas do vínculo.
    """

    code = "INTERBLOCK_INSTANCE_NOT_DECLARED"


class InterblockPeriodFrequencyMismatchError(InterblockRuntimeError):
    """
    O period_id pedido não tem a granularidade da frequência do vínculo
    (sem conversão diário/mensal/anual entre blocos).
    """

    code = "INTERBLOCK_PERIOD_FREQUENCY_MISMATCH"


class InterblockSourceValueNotFoundError(InterblockRuntimeError):
    """
    O produtor não tem valor para exatamente a instância e o período
    pedidos (sem fallback temporal ou espacial entre blocos).
    """

    code = "INTERBLOCK_SOURCE_VALUE_NOT_FOUND"


class InterblockConsumerValueConflictError(InterblockRuntimeError):
    """
    O consumidor já tem, na mesma chave, um valor diferente do valor do
    produtor: um valor local nunca substitui nem é substituído em
    silêncio pelo valor do vínculo.
    """

    code = "INTERBLOCK_CONSUMER_VALUE_CONFLICT"
