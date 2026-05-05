from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from host.clients.sdk import DaemonApiClient


pytestmark = pytest.mark.integration


# --- utility helpers ---------------------------------------------------------

def _repo_root() -> Path:
    """Return repository root directory."""
    return Path(__file__).resolve().parents[2]


def _find_sim_exe(root: Path) -> Path | None:
    """Try to locate the simulator executable in known build paths."""
    candidates = [
        root / "build-sim" / "firmware" / "sim" / "Debug" / "powerscope-fw-sim.exe",
        root / "build-sim" / "firmware" / "sim" / "Release" / "powerscope-fw-sim.exe",
        root / "build-sim" / "firmware" / "sim" / "powerscope-fw-sim",
        root / "build-sim" / "firmware" / "sim" / "Debug" / "powerscope-fw-sim",
        root / "build-sim" / "firmware" / "sim" / "Release" / "powerscope-fw-sim",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _pick_free_port() -> int:
    """Ask OS for an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_tcp_open(host: str, port: int, timeout_s: float = 8.0) -> None:
    """Wait until a TCP port becomes reachable."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=0.3):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for TCP {host}:{port}")


def _wait_daemon_health(client: DaemonApiClient, timeout_s: float = 10.0) -> None:
    """Poll daemon health endpoint until it responds successfully."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = client.health()
            if out.get("ok") is True:
                return
        except Exception:
            pass
        time.sleep(0.15)
    raise RuntimeError("Timed out waiting for daemon health endpoint")


def _terminate(proc: subprocess.Popen) -> None:
    """Gracefully terminate a subprocess, then force kill if needed."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _wait_for_stream_csv(session_dir: Path, timeout_s: float = 6.0) -> Path:
    """Wait until a non-empty CSV stream file appears in session directory."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        csv_files = list((session_dir / "streams").rglob("*.csv"))
        if csv_files:
            for p in csv_files:
                if p.exists() and p.stat().st_size > 0:
                    return p
        time.sleep(0.2)
    raise RuntimeError("No non-empty stream CSV found in session directory")


# --- integration test --------------------------------------------------------

def test_daemon_with_sim_writes_session_and_stream_artifacts(tmp_path: Path):
    """
    End-to-end test:
    simulator -> daemon -> API client -> session + stream artifacts.
    """

    root = _repo_root()
    sim_exe = _find_sim_exe(root)
    if sim_exe is None:
        pytest.skip("Simulator executable not found. Build `powerscope-fw-sim` first.")

    # start simulator on random port
    sim_port = _pick_free_port()

    sim_proc = subprocess.Popen(
        [str(sim_exe), "--port", str(sim_port)],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    daemon_proc: subprocess.Popen | None = None

    try:
        # wait for simulator to be ready
        _wait_tcp_open("127.0.0.1", sim_port)

        # start daemon connected to temp session directory
        daemon_port = _pick_free_port()
        sessions_dir = tmp_path / "sessions"

        daemon_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "host.daemon",
                "--host",
                "127.0.0.1",
                "--port",
                str(daemon_port),
                "--sessions-dir",
                str(sessions_dir),
            ],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        client = DaemonApiClient(
            base_url=f"http://127.0.0.1:{daemon_port}",
            timeout_s=2.0,
        )

        # wait until API is ready
        _wait_daemon_health(client)

        # connect simulated board
        connected = client.connect_board(
            board_id="sim1",
            transport="tcp",
            overrides={"ip": "127.0.0.1", "port": sim_port},
        )
        assert connected["board_id"] == "sim1"

        session_dir = Path(connected["session_dir"])
        assert session_dir.exists()

        # get sensors from device
        sensors = client.refresh_sensors(board_id="sim1").get("sensors", [])
        assert sensors, "Expected at least one sensor from simulator"
        sensor_id = int(sensors[0]["runtime_id"])

        # verify single sensor read works
        reading = client.read_sensor(board_id="sim1", sensor_runtime_id=sensor_id)
        assert reading["sensor_runtime_id"] == sensor_id

        # configure sampling period
        client.set_period(board_id="sim1", sensor_runtime_id=sensor_id, period_ms=100)
        period_out = client.get_period(board_id="sim1", sensor_runtime_id=sensor_id)
        assert int(period_out["period_ms"]) == 100

        # start streaming and wait for live data
        client.start_stream(board_id="sim1", sensor_runtime_id=sensor_id)

        got_items = False
        deadline = time.time() + 5.0
        while time.time() < deadline:
            out = client.drain_readings(
                board_id="sim1",
                sensor_runtime_id=sensor_id,
                limit=50,
            )
            if out.get("items"):
                got_items = True
                break
            time.sleep(0.2)

        assert got_items, "Expected streamed readings from simulator"

        # stop and disconnect cleanly
        client.stop_stream(board_id="sim1", sensor_runtime_id=sensor_id)
        client.disconnect_board(board_id="sim1")

        # verify session artifacts were written
        assert (session_dir / "session.json").exists()
        assert (session_dir / "commands.jsonl").exists()

        csv_path = _wait_for_stream_csv(session_dir)
        assert csv_path.suffix == ".csv"

    finally:
        # cleanup both processes
        if daemon_proc is not None:
            _terminate(daemon_proc)
        _terminate(sim_proc)