# host/app/transport_index.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from host.core.context import Context
from host.core.errors import PowerScopeError
from host.model.transport import TransportType


@dataclass(frozen=True, slots=True)
class TransportIndex:
    """
    App-facing transport index (metadata-driven, read-only view).

    Notes:
      - Use `from_context()` in daemon to avoid loading metadata twice.
      - `load()` is a convenience for cli/tests.
    """
    _transports: Mapping[int, TransportType]

    @classmethod
    def from_context(cls, context: Context) -> "TransportIndex":
        return cls(_transports=context.transport_factory.transports())

    @classmethod
    def load(cls, *, metadata_dir: str, protocol_dir: str) -> "TransportIndex":
        context = Context.load(metadata_dir, protocol_dir)
        return cls.from_context(context)

    def catalog(self) -> Mapping[int, TransportType]:
        """Return the raw type_id -> TransportType mapping."""
        return self._transports

    def list(self) -> list[TransportType]:
        """Return transports ordered by type_id."""
        return [self._transports[k] for k in sorted(self._transports.keys())]

    def meta_for_type_id(self, type_id: int) -> TransportType:
        meta = self._transports.get(int(type_id))
        if meta is None:
            raise PowerScopeError(
                f"Unknown transport type id '{type_id}'.",
                hint="Run: powerscope transports",
            )
        return meta

    def resolve_type_id_by_label(self, label: str) -> int:
        want = label.strip().lower()

        matches = [
            int(tid)
            for tid, meta in self._transports.items()
            if str(getattr(meta, "label", "")).strip().lower() == want
        ]

        if not matches:
            known = ", ".join(sorted({str(getattr(m, "label", "")) for m in self._transports.values()}))
            raise PowerScopeError(
                f"Unknown transport '{label}'.",
                hint=f"Run: powerscope transports (known: {known})",
            )
        if len(matches) > 1:
            raise PowerScopeError(
                f"Ambiguous transport label '{label}'.",
                hint="Transport labels must be unique.",
            )
        return int(matches[0])

    def schema_for_type_id(self, type_id: int) -> Mapping[str, Mapping[str, Any]]:
        meta = self.meta_for_type_id(type_id)
        params: Mapping[str, Mapping[str, Any]] = getattr(meta, "params", {}) or {}
        return params

    def key_param_for_type_id(self, type_id: int) -> str | None:
        meta = self.meta_for_type_id(type_id)
        return getattr(meta, "key_param", None)
