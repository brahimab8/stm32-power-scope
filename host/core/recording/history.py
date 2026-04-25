from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from host.model.compute import eval_op


def _safe_name(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "channel"


def _to_display(val: float, lsb: float, scale: float) -> float:
    return val * float(lsb) * float(scale)


def load_sensor_stream_csv(
    csv_path: Path,
    sensor_type_id: int,
    sensor_name: str = "",
    channel_specs: Optional[List[Dict[str, Any]]] = None,
    max_rows: int = 10000,
) -> List[Dict[str, Any]]:
    if not csv_path.exists():
        return []
    if not channel_specs:
        raise ValueError("channel_specs must be provided")

    measured_specs = [s for s in channel_specs if s.get("is_measured", True)]
    computed_specs = [s for s in channel_specs if not s.get("is_measured", True)]

    # Build column names cleanly
    col_by_channel_id = {}
    for s in measured_specs:
        cid = int(s["channel_id"])
        name = str(s.get("name", f"ch_{cid}"))
        col_by_channel_id[cid] = f"{cid}_{_safe_name(name)}"

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break

            # Read measured channels directly from CSV columns
            measured: Dict[str, Any] = {}
            for s in measured_specs:
                cid = int(s["channel_id"])
                col = col_by_channel_id[cid]
                sval = row.get(col)
                val = None
                if sval is not None:
                    try:
                        val = float(sval)
                    except Exception:
                        pass
                display_val = _to_display(val, s.get("lsb", 1.0), s.get("scale", 1.0)) if val is not None else None
                measured[str(cid)] = {
                    "channel_id": cid,
                    "name": s.get("name", f"ch_{cid}"),
                    "is_measured": True,
                    "value": display_val,
                    "raw": val,
                    "unit": s.get("unit", ""),
                }

            # Compute derived channels using eval_op directly
            computed: Dict[str, Any] = {}
            for s in computed_specs:
                cid = int(s["channel_id"])
                compute = s.get("compute") or {}
                try:
                    dep_ids = [int(d) for d in compute.get("channels", [])]
                    inputs_mode = compute.get("inputs", "value")
                    factor = float(compute.get("factor", 1.0))
                    vals = []
                    for dep_id in dep_ids:
                        dep = measured.get(str(dep_id))
                        if dep is None:
                            raise ValueError(f"Missing dep {dep_id}")
                        src = dep["value"] if inputs_mode == "value" else dep["raw"]
                        if src is None:
                            raise ValueError(f"Dep {dep_id} has no value")
                        vals.append(float(src))
                    raw_result = eval_op(compute["operation"], vals) * factor
                    display_val = _to_display(raw_result, s.get("lsb", 1.0), s.get("scale", 1.0))
                    computed[str(cid)] = {
                        "channel_id": cid,
                        "name": s.get("name", f"ch_{cid}"),
                        "is_measured": False,
                        "value": display_val,
                        "raw": raw_result,
                        "unit": s.get("unit", ""),
                    }
                except Exception:
                    computed[str(cid)] = {
                        "channel_id": cid,
                        "name": s.get("name", f"ch_{cid}"),
                        "is_measured": False,
                        "value": None,
                        "raw": None,
                        "unit": s.get("unit", ""),
                    }

            source = row.get("source", "stream")
            if source not in ("stream", "read_sensor", "stream_buffered"):
                source = "stream"

            stream_seq_raw = row.get("stream_seq")
            stream_seq = int(stream_seq_raw) if stream_seq_raw and stream_seq_raw.strip() else None

            rows.append({
                "reading": {
                    "sensor_type_id": sensor_type_id,
                    "sensor_name": sensor_name,
                    "measured": measured,
                    "computed": computed,
                },
                "ts_utc": row.get("timestamp"),
                "is_buffered": (source == "stream_buffered"),
            })

    return rows