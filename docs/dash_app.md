# Dash Web App (`host.clients.dash`)

The Dash client is the browser UI on top of the daemon API.
It is the main interactive view for multi-board streaming, multi-sensor live plots, and stored session history.

The app is focused on observing and exploring data:
- live readings across multiple connected boards and sensors
- live plots that update as stream data arrives
- session history browsing with stored stream files and plotted results
- basic board and sensor actions needed to run or adjust streams

## Run

```bash
python -m host.clients.dash --daemon-url http://127.0.0.1:8765 --host 127.0.0.1 --port 8050
```

Open `http://127.0.0.1:8050`.

## Prerequisites

1. Daemon is running:

```bash
python -m host.daemon --host 127.0.0.1 --port 8765
```

2. At least one reachable board transport (real board or simulator).

## Main views

- Board connection and transport setup for multiple boards, with connected boards listed on the left side.
- Two plotting areas: one for all streaming sensors together, and one for the selected loaded historical sensor stream.
- Per-sensor controls (start/stop stream, set period).
- Session history menu that loads stored stream files and renders plots.

## Demo flow

1. Launch simulator:

```bash
./scripts/run-sim.ps1
```

2. On Windows, use `./scripts/run-demo.ps1` to start simulator + daemon + Dash.
3. In Dash, choose `tcp` transport and enter:
- `ip=127.0.0.1`
- `port=9000`
4. Click Connect.
5. Start one or more sensor streams and watch the live plot update.
6. Open the history panel to browse stored sessions and stream plots.

> For Linux, start the daemon and Dash separately; see `docs/linux-workflows.md`.
