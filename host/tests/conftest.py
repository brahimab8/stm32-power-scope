from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # All tests collected from host/tests are unit tests.
    for item in items:
        item.add_marker(pytest.mark.unit)
