from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class StageResult:
    outcome: str
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

