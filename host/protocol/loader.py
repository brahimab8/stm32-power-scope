# host/protocol/loader.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from host.utils.hashing import sha256_file


class ProtocolLoader:
    """Load all protocol YAML files into dicts + keep per-file SHA256 hashes."""

    REQUIRED_FILES = (
        "constants.yml",
        "frames.yml",
        "header.yml",
        "commands.yml",
        "errors.yml",
    )

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)

        # Full documents
        self.constants_doc: Dict[str, Any] = {}
        self.frames_doc: Dict[str, Any] = {}
        self.header_doc: Dict[str, Any] = {}
        self.commands_doc: Dict[str, Any] = {}
        self.errors_doc: Dict[str, Any] = {}

        # Extracted structures used by Protocol(...)
        self.constants: Dict[str, Any] = {}
        self.frames: Dict[str, Any] = {}
        self.header: list[Dict[str, Any]] = []
        self.commands: Dict[str, Any] = {}
        self.errors: Dict[str, Any] = {}

        # File fingerprints (filename -> sha256 hex)
        self.file_hashes: Dict[str, str] = {}

    def load_all(self) -> None:
        # Ensure required files exist + compute hashes
        self.file_hashes.clear()
        for fn in self.REQUIRED_FILES:
            path = self.config_dir / fn
            if not path.exists():
                raise FileNotFoundError(f"Protocol file not found: {path}")
            self.file_hashes[fn] = sha256_file(path)

        # Load YAML documents
        self.constants_doc = self._load_yaml("constants.yml")
        self.frames_doc = self._load_yaml("frames.yml")
        self.header_doc = self._load_yaml("header.yml")
        self.commands_doc = self._load_yaml("commands.yml")
        self.errors_doc = self._load_yaml("errors.yml")

        # Extract payloads
        self.constants = self.constants_doc
        self.frames = self.frames_doc.get("frames", {}) or {}
        self.header = self.header_doc.get("header", []) or []
        self.commands = self.commands_doc.get("commands", {}) or {}
        self.errors = self.errors_doc.get("errors", {}) or {}

        # Basic shape validation
        if not isinstance(self.constants, dict):
            raise ValueError("constants.yml must be a mapping")
        if not isinstance(self.frames, dict):
            raise ValueError("frames.yml must contain 'frames' mapping")
        if not isinstance(self.header, list):
            raise ValueError("header.yml must contain 'header' list")
        if not isinstance(self.commands, dict):
            raise ValueError("commands.yml must contain 'commands' mapping")
        if not isinstance(self.errors, dict):
            raise ValueError("errors.yml must contain 'errors' mapping")

    def protocol_version(self) -> int:
        """
        Canonical wire protocol version.
        Defaults to 0 if not specified.
        """
        v = self.constants.get("protocol_version", 0)
        try:
            return int(v)
        except Exception:
            raise ValueError(f"Invalid protocol version in constants.yml: {v!r}")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = self.config_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
