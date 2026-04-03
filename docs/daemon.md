# Daemon

PowerScope daemon is the host control plane for multi-board operation.

## Run

```bash
python -m host.daemon --host 127.0.0.1 --port 8765
```

## Architecture

- One daemon process
- Internal `BoardManager` manages multiple connected boards
- One `PowerScopeController` + transport session per board
- Shared metadata/protocol context loaded once on daemon startup

## Control API (JSON over HTTP)

- `GET /health`
- `GET /transports`
- `GET /boards`
- `POST /boards/connect`
- `GET /boards/{board_id}/status`
- `POST /boards/{board_id}/disconnect`
- `POST /boards/{board_id}/refresh_sensors`
- `POST /boards/{board_id}/set_period`
- `POST /boards/{board_id}/start_stream`
- `POST /boards/{board_id}/stop_stream`
- `POST /boards/{board_id}/read_sensor`
- `POST /boards/{board_id}/uptime`

## Example connect request

`POST /boards/connect`

```json
{
  "board_id": "board-com4",
  "transport": "uart",
  "overrides": {
    "port": "COM4"
  }
}
```

## Platform support

- Linux: run directly or wrap with `systemd`
- Windows: run directly, then wrap with a service wrapper later
- Core daemon code path is shared for both platforms

## Linux service notes

- Service template: `deploy/systemd/powerscope-daemon.service`
- Installer helper: `scripts/linux/install-daemon.sh`
- Run helper: `scripts/linux/run-daemon.sh`

## Related docs

- `docs/ctl_cli.md`
- `docs/testing.md`
