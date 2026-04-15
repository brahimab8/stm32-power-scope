from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from host.core.session_identity import context_identity_with_board_uid, session_matches


def test_context_identity_with_board_uid_includes_normalized_uid():
    ctx = SimpleNamespace(protocol_version=0, protocol_hashes={"a": "1"}, metadata_hashes={"m": "2"})
    identity = context_identity_with_board_uid(ctx, board_uid_hex="AABBCC")
    assert identity["board_uid_hex"] == "aabbcc"


def test_session_matches_requires_board_uid_when_provided(tmp_path: Path):
    session_json = tmp_path / "session.json"
    session_json.write_text(
        json.dumps(
            {
                "protocol": {
                    "protocol_version": 0,
                    "board_uid_hex": "001122",
                    "files_sha256": {"p": "x"},
                },
                "metadata": {"files_sha256": {"m": "y"}},
                "transport": {"type_id": 1},
            }
        ),
        encoding="utf-8",
    )

    identity = {
        "protocol_version": 0,
        "board_uid_hex": "aabbcc",
        "protocol_files_sha256": {"p": "x"},
        "metadata_files_sha256": {"m": "y"},
    }
    assert session_matches(session_json, identity=identity, transport_fp={"type_id": 1}) is False


def test_session_matches_accepts_matching_board_uid_case_insensitive(tmp_path: Path):
    session_json = tmp_path / "session.json"
    session_json.write_text(
        json.dumps(
            {
                "protocol": {
                    "protocol_version": 0,
                    "board_uid_hex": "AABBCC",
                    "files_sha256": {"p": "x"},
                },
                "metadata": {"files_sha256": {"m": "y"}},
                "transport": {"type_id": 1},
            }
        ),
        encoding="utf-8",
    )

    identity = {
        "protocol_version": 0,
        "board_uid_hex": "aabbcc",
        "protocol_files_sha256": {"p": "x"},
        "metadata_files_sha256": {"m": "y"},
    }
    assert session_matches(session_json, identity=identity, transport_fp={"type_id": 1}) is True
