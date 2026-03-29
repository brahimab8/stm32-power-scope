from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from host.core.errors import PowerScopeError


class DaemonApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = float(timeout_s)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def transports(self) -> dict[str, Any]:
        return self._request("GET", "/transports")

    def list_boards(self) -> dict[str, Any]:
        return self._request("GET", "/boards")

    def connect_board(self, *, board_id: str, transport: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/boards/connect",
            {
                "board_id": str(board_id),
                "transport": str(transport),
                "overrides": dict(overrides or {}),
            },
        )

    def describe_board(self, *, board_id: str) -> dict[str, Any]:
        return self._request("GET", f"/boards/{board_id}/status")

    def disconnect_board(self, *, board_id: str) -> dict[str, Any]:
        return self._request("POST", f"/boards/{board_id}/disconnect", {})

    def rename_board(self, *, board_id: str, new_board_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/rename",
            {"new_board_id": str(new_board_id)},
        )

    def refresh_sensors(self, *, board_id: str) -> dict[str, Any]:
        return self._request("POST", f"/boards/{board_id}/refresh_sensors", {})

    def set_period(self, *, board_id: str, sensor_runtime_id: int, period_ms: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/set_period",
            {"sensor_runtime_id": int(sensor_runtime_id), "period_ms": int(period_ms)},
        )

    def get_period(self, *, board_id: str, sensor_runtime_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/get_period",
            {"sensor_runtime_id": int(sensor_runtime_id)},
        )

    def start_stream(self, *, board_id: str, sensor_runtime_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/start_stream",
            {"sensor_runtime_id": int(sensor_runtime_id)},
        )

    def stop_stream(self, *, board_id: str, sensor_runtime_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/stop_stream",
            {"sensor_runtime_id": int(sensor_runtime_id)},
        )

    def read_sensor(self, *, board_id: str, sensor_runtime_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/boards/{board_id}/read_sensor",
            {"sensor_runtime_id": int(sensor_runtime_id)},
        )

    def uptime(self, *, board_id: str) -> dict[str, Any]:
        return self._request("POST", f"/boards/{board_id}/uptime", {})

    def drain_readings(
        self,
        *,
        board_id: str,
        sensor_runtime_id: int | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"limit": int(limit)}
        if sensor_runtime_id is not None:
            body["sensor_runtime_id"] = int(sensor_runtime_id)
        return self._request("POST", f"/boards/{board_id}/drain_readings", body)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/json; charset=utf-8"}

        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            error_payload: dict[str, Any] | None = None
            try:
                raw = e.read().decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    error_payload = parsed
            except Exception:
                error_payload = None

            if error_payload and error_payload.get("ok") is False:
                err = error_payload.get("error", {})
                message = str(err.get("message") or f"HTTP {e.code}")
                hint = err.get("hint")
                details = {
                    "http_status": e.code,
                    "code": err.get("code"),
                    "details": err.get("details"),
                }
                raise PowerScopeError(message, hint=hint, details=details)

            raise PowerScopeError(f"Daemon request failed: HTTP {e.code}")
        except URLError as e:
            raise PowerScopeError(
                f"Daemon connection failed: {e.reason}",
                hint=f"Start daemon first: python -m host.daemon --host 127.0.0.1 --port 8765",
            )
        except json.JSONDecodeError:
            raise PowerScopeError("Daemon returned invalid JSON response.")

        if not isinstance(payload, dict):
            raise PowerScopeError("Daemon returned a non-object JSON response.")

        if payload.get("ok") is False:
            err = payload.get("error", {})
            message = str(err.get("message") or "Daemon returned an error.")
            hint = err.get("hint")
            details = {
                "code": err.get("code"),
                "details": err.get("details"),
            }
            raise PowerScopeError(message, hint=hint, details=details)

        data_out = payload.get("data", {})
        if not isinstance(data_out, dict):
            raise PowerScopeError("Daemon returned invalid 'data' payload.")
        return data_out
