# shell.py
import argparse, time
from host.common.serial_link import open_port
from host.common.protocol import read_frame, send_start, send_stop

def main():
    ap = argparse.ArgumentParser(description="STM32 Power Scope shell (CDC streaming)")
    ap.add_argument('-p', '--port', help='Serial port (auto-detect if omitted)')
    ap.add_argument('--start', action='store_true', help='send START on open (once)')
    ap.add_argument('--stop',  action='store_true', help='send STOP on open (once)')
    args = ap.parse_args()

    ser = open_port(args.port)  # asserts DTR by default
    print(f'Opened {ser.port} (DTR={"on" if ser.dtr else "off"})')

    if args.stop:
        send_stop(ser)
    if args.start:
        send_start(ser)

    print('Listening… Ctrl+C to quit')
    last_seq = None
    frames = 0
    t0 = time.time()

    try:
        while True:
            hdr, payload = read_frame(ser)
            if not hdr:
                continue

            frames += 1
            gap = (hdr["seq"] - last_seq) if last_seq is not None else 0
            last_seq = hdr["seq"]

            print(f'seq={hdr["seq"]:8d} ts={hdr["ts_ms"]:10d} len={hdr["len"]:3d} gap={gap:3d}')

            if frames % 200 == 0:
                dt = time.time() - t0
                if dt > 0:
                    print(f'~{frames/dt:.1f} frames/s')
                frames = 0
                t0 = time.time()

    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass

if __name__ == '__main__':
    main()
