# serial_link.py
import sys
import serial
from serial.tools import list_ports

def list_candidates():
    """Return a list of pyserial port info objects (for error messages/UI)."""
    return list(list_ports.comports())

def autodetect_port(
    prefer_vid_pid=((0x0483, 0x5740),),               # ST CDC default
    prefer_substrings=("ST", "STM", "STMicro", "CDC", "Virtual COM"),
):
    """
    Return a likely CDC ACM port path, or None if not confidently found.
    Strategy: (1) VID:PID exact match, (2) descriptor substring match. No fallback.
    """
    ports = list_candidates()
    if not ports:
        return None

    # exact VID:PID
    for p in ports:
        if p.vid is not None and p.pid is not None:
            for vid, pid in prefer_vid_pid:
                if p.vid == vid and p.pid == pid:
                    return p.device

    # descriptor/manufacturer/product substrings
    for p in ports:
        desc = " ".join(filter(None, [p.manufacturer, p.product, p.description]))
        if any(s.lower() in desc.lower() for s in prefer_substrings):
            return p.device

    # No matching device found
    return None

def open_port(port=None, timeout=1.0, assert_dtr=True):
    """
    Open a CDC ACM port. If 'port' is None, try to auto-detect; otherwise fail with a
    clear message listing available ports. CDC ignores baud; pyserial requires one.
    """
    if port is None:
        port = autodetect_port()
        if port is None:
            ports = list_candidates()
            listing = "\n".join(
                f"- {p.device} "
                f"[{p.vid:04X}:{p.pid:04X}] "
                f"{(p.manufacturer or '')} {(p.product or '')} {(p.description or '')}".strip()
                if (p.vid is not None and p.pid is not None)
                else f"- {p.device} {(p.description or '')}".strip()
                for p in ports
            ) or "(no serial ports found)"
            raise RuntimeError(
                "Could not auto-detect the STM32 CDC port. "
                "Specify it with -p/--port.\nCandidates:\n" + listing
            )

    kwargs = dict(baudrate=115200, timeout=timeout, write_timeout=timeout)
    if sys.platform != "win32":
        # asks the OS for exclusive access to the device 
        # Windows doesn’t support this flag.
        kwargs["exclusive"] = True
    ser = serial.Serial(port, **kwargs)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    if assert_dtr:
        ser.dtr = True  # firmware gates on DTR
    return ser

def read_exact(ser, n):
    """Read exactly n bytes or return None on timeout."""
    buf = b""
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def resync(ser, magic, hdr_size):
    """
    Scan stream for 2-byte little-endian 'magic'. Return raw header or None on timeout.
    """
    win = b""
    while True:
        b = ser.read(1)
        if not b:
            return None
        win = (win + b)[-2:]
        if len(win) == 2 and int.from_bytes(win, "little") == magic:
            rest = read_exact(ser, hdr_size - 2)
            if not rest:
                return None
            return win + rest
