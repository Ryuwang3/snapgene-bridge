"""Primer3-backed primer design with an explicit thermodynamic standard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import DependencyMissingError, InputError, OperationUnavailableError
from .models import MoleculeRecord, Primer


@dataclass(frozen=True)
class PrimerDesignConfig:
    """Conservative defaults for a first PCR primer pass."""

    min_size: int = 18
    opt_size: int = 20
    max_size: int = 25
    min_tm: float = 58.0
    opt_tm: float = 60.0
    max_tm: float = 62.0
    min_product_size: int = 100
    max_product_size: int = 3000
    num_return: int = 5
    tm_standard: str = "primer3"


@dataclass(frozen=True)
class PrimerPair:
    index: int
    forward: Primer
    reverse: Primer
    product_start: int
    product_end: int
    product_size: int
    penalty: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "forward": self.forward.to_dict(),
            "reverse": self.reverse.to_dict(),
            "product_start": self.product_start,
            "product_end": self.product_end,
            "product_size": self.product_size,
            "penalty": self.penalty,
        }


@dataclass(frozen=True)
class PrimerDesignResult:
    target_start: int
    target_end: int
    tm_standard: str
    pairs: tuple[PrimerPair, ...]

    @property
    def primers(self) -> tuple[Primer, ...]:
        return tuple(primer for pair in self.pairs for primer in (pair.forward, pair.reverse))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_start": self.target_start,
            "target_end": self.target_end,
            "tm_standard": self.tm_standard,
            "pairs": [pair.to_dict() for pair in self.pairs],
        }


def design_primers(
    record: MoleculeRecord,
    target_start: int,
    target_end: int,
    *,
    config: PrimerDesignConfig | None = None,
) -> PrimerDesignResult:
    """Design primer pairs for a target interval using primer3-py.

    The result records ``tm_standard=primer3`` so downstream users never
    mistake these values for SnapGene or NEB calculator values.
    """

    config = config or PrimerDesignConfig()
    record.validate()
    if target_start < 0 or target_end <= target_start or target_end > record.length:
        raise InputError(
            f"Target interval [{target_start}, {target_end}) is outside the molecule.",
            hint=f"Use coordinates between 0 and {record.length}, with start < end.",
        )
    if config.tm_standard != "primer3":
        raise OperationUnavailableError(
            f"Thermodynamic standard {config.tm_standard!r} is not implemented.",
            hint="Use --tm-standard primer3 until another backend is validated.",
        )
    try:
        import primer3.bindings as primer3
    except ImportError as error:  # pragma: no cover - exercised by environment
        raise DependencyMissingError(
            "Primer design requires optional dependency 'primer3-py'.",
            hint="Install it with: uv sync --extra design",
        ) from error

    sequence_args = {
        "SEQUENCE_ID": record.name,
        "SEQUENCE_TEMPLATE": record.sequence,
        "SEQUENCE_TARGET": [target_start, target_end - target_start],
    }
    global_args = {
        "PRIMER_TASK": "generic",
        "PRIMER_PICK_LEFT_PRIMER": 1,
        "PRIMER_PICK_INTERNAL_OLIGO": 0,
        "PRIMER_PICK_RIGHT_PRIMER": 1,
        "PRIMER_NUM_RETURN": config.num_return,
        "PRIMER_MIN_SIZE": config.min_size,
        "PRIMER_OPT_SIZE": config.opt_size,
        "PRIMER_MAX_SIZE": config.max_size,
        "PRIMER_MIN_TM": config.min_tm,
        "PRIMER_OPT_TM": config.opt_tm,
        "PRIMER_MAX_TM": config.max_tm,
        "PRIMER_PRODUCT_SIZE_RANGE": [[config.min_product_size, config.max_product_size]],
    }
    raw = primer3.design_primers(sequence_args, global_args)
    pair_count = int(raw.get("PRIMER_PAIR_NUM_RETURNED", 0))
    if pair_count == 0:
        explanation = raw.get("PRIMER_PAIR_EXPLAIN", "Primer3 returned no pairs.")
        raise OperationUnavailableError(
            f"Primer3 could not find a valid pair: {explanation}",
            hint="Adjust the target, product-size range, or thermodynamic constraints.",
        )

    pairs: list[PrimerPair] = []
    for index in range(pair_count):
        left_start, left_length = raw[f"PRIMER_LEFT_{index}"]
        right_start, right_length = raw[f"PRIMER_RIGHT_{index}"]
        forward = Primer(
            name=f"{record.name}_F{index + 1}",
            sequence=raw[f"PRIMER_LEFT_{index}_SEQUENCE"],
            strand="+",
            binding_start=int(left_start),
            binding_end=int(left_start + left_length),
            tm_celsius=float(raw[f"PRIMER_LEFT_{index}_TM"]),
            tm_standard=config.tm_standard,
            metadata={"position": "forward"},
        )
        reverse = Primer(
            name=f"{record.name}_R{index + 1}",
            sequence=raw[f"PRIMER_RIGHT_{index}_SEQUENCE"],
            strand="-",
            binding_start=int(right_start),
            binding_end=int(right_start + right_length),
            tm_celsius=float(raw[f"PRIMER_RIGHT_{index}_TM"]),
            tm_standard=config.tm_standard,
            metadata={"position": "reverse"},
        )
        product_start = int(left_start)
        product_end = int(right_start + right_length)
        pairs.append(
            PrimerPair(
                index=index,
                forward=forward,
                reverse=reverse,
                product_start=product_start,
                product_end=product_end,
                product_size=product_end - product_start,
                penalty=float(raw[f"PRIMER_PAIR_{index}_PENALTY"]),
            )
        )
    return PrimerDesignResult(target_start, target_end, config.tm_standard, tuple(pairs))
