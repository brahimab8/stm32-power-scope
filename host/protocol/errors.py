# host/protocol/errors.py

class ProtocolError(Exception):
    """Base for protocol-level failures (framing/parse/command semantics)."""

class CommandFailed(ProtocolError):
    def __init__(self, cmd: str, resp: dict):
        super().__init__(f"{cmd} failed: {resp}")
        self.cmd = cmd
        self.resp = resp

class CommandTimeout(ProtocolError):
    def __init__(self, cmd: str, timeout_s: float):
        super().__init__(f"{cmd} timed out after {timeout_s}s")
        self.cmd = cmd
        self.timeout_s = timeout_s

class SendFailed(ProtocolError):
    def __init__(self, cmd: str, reason: str = "send_failed"):
        super().__init__(f"{cmd} send failed ({reason})")
        self.cmd = cmd
        self.reason = reason

class DecodeError(ProtocolError):
    pass
