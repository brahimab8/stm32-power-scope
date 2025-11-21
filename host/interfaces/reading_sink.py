# host/interfaces/reading_sink.py
from typing import Protocol
from host.model.sensor import DecodedReading


class ReadingSink(Protocol):
    def on_reading(self, runtime_id: int, reading: DecodedReading) -> None: ...
    def close(self) -> None: ...
