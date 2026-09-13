from app.engine.dependency_graph import DependencyGraph
from app.engine.exceptions import DependencyCycleError


class DependencyResolver:
    """
    Determina a ordem de execução das equações a partir
    de suas dependências.
    """

    def resolve(
        self,
        graph: DependencyGraph,
    ) -> tuple[str, ...]:
        """
        Retorna as equações em ordem topológica.

        Raises:
            DependencyCycleError:
                Quando existe um ciclo de dependências.
        """

        dependencies = graph.as_dict()

        resolved: list[str] = []

        remaining = {
            equation_id: set(dependency_ids)
            for equation_id, dependency_ids
            in dependencies.items()
        }

        while remaining:
            ready = sorted(
                equation_id
                for equation_id, dependency_ids
                in remaining.items()
                if not dependency_ids
            )

            if not ready:
                cycle = self._find_cycle(remaining)

                raise DependencyCycleError(
                    cycle,
                )

            for equation_id in ready:
                resolved.append(equation_id)
                del remaining[equation_id]

            for dependency_ids in remaining.values():
                dependency_ids.difference_update(ready)

        return tuple(resolved)

    def _find_cycle(
        self,
        dependencies: dict[str, set[str]],
    ) -> tuple[str, ...]:
        """
        Identifica um ciclo presente no conjunto de dependências.

        Retorna o caminho completo do ciclo, incluindo o primeiro
        elemento novamente no final.
        """

        visited: set[str] = set()
        visiting: set[str] = set()
        path: list[str] = []

        def visit(
            equation_id: str,
        ) -> tuple[str, ...] | None:
            if equation_id in visiting:
                cycle_start = path.index(
                    equation_id,
                )

                return tuple(
                    path[cycle_start:]
                    + [equation_id]
                )

            if equation_id in visited:
                return None

            visiting.add(equation_id)
            path.append(equation_id)

            for dependency_id in sorted(
                dependencies.get(
                    equation_id,
                    set(),
                ),
            ):
                cycle = visit(
                    dependency_id,
                )

                if cycle is not None:
                    return cycle

            path.pop()
            visiting.remove(equation_id)
            visited.add(equation_id)

            return None

        for equation_id in sorted(
            dependencies,
        ):
            cycle = visit(
                equation_id,
            )

            if cycle is not None:
                return cycle

        raise DependencyCycleError(
            tuple(),
        ).cycle
