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
