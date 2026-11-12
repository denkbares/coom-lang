"""The operations of the reference solver.

Every operation grounds the facts of the model and its inputs together with the encoding and solves once. Defaults
are applied greedily by a domain heuristic, so a solved configuration applies defaults by priority but is not
guaranteed to apply a maximal set of them. Solving enumerates cautiously, the first model being the solved
configuration and the last one holding the atoms true in every model, which decides the consequences.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from clingo import Control, Function, Symbol
from clingo import Model as ClingoModel
from coom.clingo import consequences
from coom.clingo.facts import ROOT, Encoding, encoding_file, value_term
from coom.clingo.numeric import Dependencies, Propagator, assemble
from coom.configuration import Configuration
from coom.diagnostics import Diagnostic
from coom.model import Boolean, ConstantValue, Enumeration, FeatureStep, Model, Option, Path, Structure

_ENCODING = (
    "instances.lp", "structure.lp", "values.lp", "paths.lp", "conditions.lp", "behaviors.lp", "defaults.lp",
    "consequences.lp",
)  # fmt: skip


# Consequences are computed over the atoms the encoding decides by itself. Atoms the propagator decides, such as the
# outcome of a numeric comparison, follow from these, and refuting them one total assignment at a time is expensive.
_PROJECTION = "".join(
    f"#project {signature}.\n"
    for signature in ("exists/1", "value/2", "absent/1", "undefined/1", "active/2", "applied/2")
)


class ClingoSolverError(Exception):
    """The model uses something the solver does not support."""

    def __init__(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("\n".join(map(str, self.diagnostics)))


def encoding_text() -> str:
    """The encoding as one program, in the order of its files."""
    return "\n".join(encoding_file(name) for name in _ENCODING)


class ClingoSolver:
    """Solves configurations of one model.

    The constructor raises ClingoSolverError if the model uses something the solver does not support. Warnings, such as
    ignored optimization statements, are kept in diagnostics.
    """

    def __init__(self, model: Model) -> None:
        self.model = model
        self.encoding = Encoding(model)
        if not self.encoding.ok:
            raise ClingoSolverError(self.encoding.diagnostics)
        self.dependencies = Dependencies(self.encoding)
        self._program = encoding_text()

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self.encoding.diagnostics)

    def solve(self, configuration: Configuration | None = None) -> Configuration | None:
        """Completes the inputs to a configuration with defaults applied, None if no completion exists.

        Values the inputs force, those held in every completion regardless of defaults, take the role consequence
        unless they are selected.
        """
        arguments = ["--heuristic=Domain", "--enum-mode=cautious", "--project=project", "0"]
        control, propagator, given, names = self._control(configuration, arguments, True, _PROJECTION)
        first: frozenset[Symbol] | None = None
        cautious: set[Symbol] = set()

        def collect(model: ClingoModel) -> bool:
            # under projection a model holds only projected atoms, the propagator saw the complete first one
            nonlocal first
            if first is None:
                first = propagator.accepted
            cautious.clear()
            cautious.update(model.symbols(atoms=True))
            return True

        control.solve(on_model=collect)
        if first is None:
            return None
        solved = assemble(self.encoding, self.dependencies, first.__contains__, given, names).configuration
        consequences.apply(solved, self.encoding, self.dependencies, first, cautious)
        return solved

    def satisfiable(self, configuration: Configuration | None = None) -> bool:
        """Whether the inputs have a completion, ignoring defaults."""
        found: list[bool] = []
        self._run(configuration, ["1"], False, lambda _, __: found.append(True))
        return bool(found)

    def enumerate(self, configuration: Configuration | None = None) -> list[Configuration]:
        """Every completion of the inputs, ignoring defaults."""
        found: list[Configuration] = []
        self._run(configuration, ["0"], False, lambda _, build: found.append(build()))
        return found

    def feasible(self, configuration: Configuration | None, slot: Path | str) -> frozenset[Option | bool]:
        """The options or truth values that some completion of the inputs holds in a slot of an enumeration or bool.

        The slot is given by a path from the product, such as kidsBike.wheelSize or bike.bags[1].size. Defaults are
        ignored, since they never restrict what is available.
        """
        term, values = self._slot(slot)
        atoms = {Function("value", [term, value_term(value)]): value for value in values}
        brave: set[Symbol] = set()

        def collect(model: ClingoModel, _: object) -> None:
            # in brave mode every model holds the consequences found so far
            brave.clear()
            brave.update(symbol for symbol in model.symbols(atoms=True) if symbol in atoms)

        self._run(configuration, ["--enum-mode=brave", "0"], False, collect)
        return frozenset(atoms[symbol] for symbol in brave)

    def _slot(self, slot: Path | str) -> tuple[Symbol, tuple[Option | bool, ...]]:
        steps = _steps(slot) if isinstance(slot, str) else _path_steps(self.model, slot)
        term = ROOT
        structure = self.model.root
        feature = None
        for name, index in steps:
            if feature is not None:
                if not isinstance(feature.type, Structure):
                    raise KeyError(f"{slot} does not lead through instances")
                structure = feature.type
            feature = structure.feature(name)
            found = self.encoding.universe.slot(term, feature, index)
            if found is None:
                raise KeyError(f"{slot} addresses no slot")
            term = found
        if feature is None:
            raise KeyError(f"{slot} addresses no slot")
        if isinstance(feature.type, Enumeration):
            return term, feature.type.options
        if isinstance(feature.type, Boolean):
            return term, (True, False)
        raise KeyError(f"{slot} is neither an enumeration nor a bool")

    def _run(
        self,
        configuration: Configuration | None,
        arguments: list[str],
        defaults: bool,
        on_model: Callable[[ClingoModel, Callable[[], Configuration]], None],
    ) -> None:
        """Solves once, calling on_model with each model and a function that builds its configuration."""
        control, _, given, names = self._control(configuration, arguments, defaults)

        def handle(model: ClingoModel) -> bool:
            atoms = set(model.symbols(atoms=True))

            def build() -> Configuration:
                return assemble(self.encoding, self.dependencies, atoms.__contains__, given, names).configuration

            on_model(model, build)
            return True

        control.solve(on_model=handle)

    def _control(
        self, configuration: Configuration | None, arguments: list[str], defaults: bool, extra: str = ""
    ) -> tuple[Control, Propagator, dict[Symbol, ConstantValue], dict[Symbol, str]]:
        """A grounded control for the inputs with the propagator registered."""
        given: dict[Symbol, ConstantValue] = {}
        names: dict[Symbol, str] = {}
        inputs: list[Symbol] = []
        if configuration is not None:
            inputs, given, names = self.encoding.inputs(configuration)
        control = Control(arguments, logger=_quiet)
        propagator = Propagator(self.encoding, self.dependencies, given, names)
        control.register_propagator(propagator)
        facts = [*self.encoding.facts, *inputs]
        if defaults:
            facts.append(Function("defaults"))
        program = "".join(f"{fact}.\n" for fact in facts)
        control.add("base", [], program + self._program + extra)
        control.ground([("base", [])])
        return control, propagator, given, names


def _quiet(code: object, message: str) -> None:
    # the encoding leaves fact predicates of unused language features empty, which clingo reports as info
    pass


def _steps(path: str) -> list[tuple[str, int]]:
    result = []
    for step in path.split("."):
        name, _, rest = step.partition("[")
        result.append((name, int(rest.rstrip("]")) if rest else 0))
    return result


def _path_steps(model: Model, path: Path) -> list[tuple[str, int]]:
    if path.origin is not model.root:
        raise KeyError(f"{path} does not start at the product")
    result = []
    for step in path.steps:
        if not isinstance(step, FeatureStep):
            raise KeyError(f"{path} addresses an attribute")
        if step.index is not None and step.index.first < 0:
            raise KeyError(f"{path} counts from the end")
        result.append((step.feature.name, 0 if step.index is None else step.index.first))
    return result
