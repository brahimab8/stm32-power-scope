# host/cli/shell.py
"""
CLI for STM32 Power Scope (CDC streaming).

- Streams frames from the device and prints a compact line per frame.
- Optionally logs to CSV (raw integers) with --log"""

import argparse, time
from host.common.serial_link import open_port
from host.common.protocol import (
    read_frame, send_start, send_stop,
    PROTO_TYPE_STREAM, PROTO_TYPE_ACK, PROTO_TYPE_NACK,
)
from host.common.telemetry import decode_data_frame
from host.common.control import parse_control_frame, format_control_event
from host.common.logging import LogController, make_log_path, DEFAULTS

DEFAULT_LOG_SECONDS = int(DEFAULTS.max_seconds or 60)


def main() -> None:
    ap = argparse.ArgumentParser(description="STM32 Power Scope shell (CDC streaming)")
    ap.add_argument('-p', '--port', help='Serial port (auto-detect if omitted)')
    ap.add_argument('--start', action='store_true',
                    help='send START on open (once). If --log is set, START is sent automatically.')
    ap.add_argument('--stop',  action='store_true',
                    help='send STOP on open (once)')

    # Logging controls (centralized in host.common.logging)
    ap.add_argument('--log', action='store_true',
                    help='log frames to CSV (path + name centralized under <repo>/host/logs)')
    ap.add_argument('--max-seconds', type=float, default=DEFAULT_LOG_SECONDS,
                    help=f'auto-stop logging after N seconds (device time; default: {DEFAULT_LOG_SECONDS}s; 0=disabled)')
    ap.add_argument('--max-frames', type=int, default=0,
                    help='optional max number of frames to capture before stopping (0 = no limit)')
    ap.add_argument('--max-bytes', type=int, default=0,
                    help='optional max output CSV size in bytes (0 = no limit)')

    args = ap.parse_args()

    ser = open_port(args.port)  # asserts DTR by default
    print(f'Opened {ser.port} (DTR={"on" if ser.dtr else "off"})')

    if args.stop:
        send_stop(ser, wait_reply=False)
    if args.start or args.log:
        send_start(ser, wait_reply=False)

    # Prepare logging if requested
    log = None
    effective_seconds = 0.0

    if args.log:
        path = make_log_path(suffix="cli")

        def _on_log_stop(reason: str) -> None:
            print(f"[log] stopped: {reason}")

        log = LogController(("I", "V", "P"), on_stop=_on_log_stop)

        # CLI overrides when >0, otherwise fall back to centralized defaults
        max_seconds = args.max_seconds if (args.max_seconds and args.max_seconds > 0) else DEFAULTS.max_seconds
        max_frames  = args.max_frames  if (args.max_frames  and args.max_frames  > 0) else DEFAULTS.max_frames
        max_bytes   = args.max_bytes   if (args.max_bytes   and args.max_bytes   > 0) else DEFAULTS.max_bytes

        # store the numeric value once for the wall-time guard
        effective_seconds = float(max_seconds or 0.0)

        try:
            log.start(str(path), max_seconds=max_seconds, max_frames=max_frames, max_bytes=max_bytes)
            print(f'Logging → {path}')
        except RuntimeError as e:
            print(f'[log] {e}')
            log = None
            effective_seconds = 0.0

    print('Listening… Press Ctrl+C to quit')

    # Stats / meter
    last_seq = None
    idx = 0          # monotonically increasing local sample index for logging
    rate_frames = 0
    rate_t0 = time.time()

    # Wall-time guard only until first STREAM frame arrives and only if logging with a time cap.
    wall_start = time.time() if (log and log.active and effective_seconds > 0.0) else None
    saw_first_stream = False

    try:
        while True:
            if wall_start is not None and log and log.active and not saw_first_stream:
                if (time.time() - wall_start) >= effective_seconds:
                    print(f'Auto-stop (wall): reached {effective_seconds}s limit without device frames.')
                    log.stop("max_seconds")
                    break

            hdr, payload = read_frame(ser)
            if not hdr:
                continue

            t = hdr["type"]
            if t == PROTO_TYPE_STREAM:
                if not saw_first_stream:
                    saw_first_stream = True
                    wall_start = None

                try:
                    sample = decode_data_frame(hdr, payload)
                except Exception:
                    # Bad/short payload; skip this frame
                    continue

                # Safe gap (handles u32 wrap)
                gap = 0 if last_seq is None else ((sample.seq - last_seq) & 0xFFFFFFFF)
                last_seq = sample.seq

                v = sample.values
                print(
                    f'seq={sample.seq:8d} ts={sample.ts_ms:10d} '
                    f'I={v.get("I",0):7d}uA V={v.get("V",0):5d}mV P={v.get("P",0):6d}mW gap={gap:3d}'
                )

                # Rate meter ~every 200 frames
                rate_frames += 1
                if rate_frames >= 200:
                    dt = time.time() - rate_t0
                    if dt > 0:
                        print(f'~{rate_frames/dt:.1f} frames/s')
                    rate_frames = 0
                    rate_t0 = time.time()

                # Logging (raw integers in fixed channel order)
                if log and log.active:
                    # Feed the controller; it will auto-stop on limits
                    if not log.append(idx, sample.seq, sample.ts_ms, v):
                        break
                    idx += 1

            elif t in (PROTO_TYPE_ACK, PROTO_TYPE_NACK):
                ev = parse_control_frame(hdr, payload)
                print(format_control_event(ev))

            else:
                print(f'OTHER type={t} len={hdr["len"]} seq={hdr["seq"]}')

    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup on exit (Stop streaming from device if we started it)
        if args.log:
            try:
                send_stop(ser, wait_reply=False)
            except Exception:
                pass
        try:
            ser.close()
        except Exception:
            pass
        if log and log.active:
            log.stop("stopped")

        if log:
            p = log.path or "(unknown)"
            print(f'Captured ~{log.frames_written} frame(s) → {p}')

if __name__ == '__main__':
    main()
