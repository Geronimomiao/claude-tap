"""Browser-safety contracts for the test environment."""

import os
import shutil

import pytest


def test_test_session_disables_external_browser() -> None:
    noop_browser = shutil.which("true")
    if noop_browser is None:
        pytest.skip("the platform does not provide a true command")

    assert os.environ["BROWSER"] == noop_browser
