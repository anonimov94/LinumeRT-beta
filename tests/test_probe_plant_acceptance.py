"""Regression tests for strict Plant probe acceptance.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: ChatGPT
"""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "probe_plant_acceptance",
    Path(__file__).resolve().parents[1] / "tools" / "probe_plant_acceptance.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def sample(contact, surface="0", feed="100"):
    return [{
        "axis": "Z", "feed_mm_min": feed,
        "plant_surface_mm": surface,
        "linuxcnc_contact_mm": str(contact),
    }]


@pytest.mark.parametrize("error,accepted", [
    ("0", True),
    ("0.000999", True),
    ("-0.000999", True),
    ("0.001", False),
    ("-0.001", False),
    ("0.012", False),
])
def test_strict_boundary(error, accepted):
    assert module.evaluate(sample(error))["pass"] is accepted


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "invalid"])
def test_nonfinite_and_invalid_rejected(bad):
    with pytest.raises(ValueError):
        module.evaluate(sample(bad))


def test_empty_and_missing_data_rejected():
    with pytest.raises(ValueError):
        module.evaluate([])
    with pytest.raises(ValueError):
        module.evaluate([{"axis": "Z", "feed_mm_min": "100"}])


def test_grouped_measurements_do_not_hide_failure():
    rows = sample("0.0001", feed="50") + sample("0.012", feed="100")
    report = module.evaluate(rows)
    assert report["samples"] == 2
    assert not report["pass"]
    assert report["groups"][0]["pass"]
    assert not report["groups"][1]["pass"]
