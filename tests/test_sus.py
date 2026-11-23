"""SUS: формула, межі, файл-приклад."""
from pathlib import Path

import pytest

from eval.sus import main, sus_score

EXAMPLE = Path(__file__).resolve().parents[1] / "eval" / "sus_example.csv"


def test_sus_score_matches_methodical_example():
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75.0
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0


def test_sus_rejects_wrong_input():
    with pytest.raises(ValueError):
        sus_score([3] * 9)
    with pytest.raises(ValueError):
        sus_score([3, 3, 3, 3, 3, 3, 3, 3, 3, 6])


def test_sus_main_prints_mean(capsys):
    main(str(EXAMPLE))
    assert "SUS mean" in capsys.readouterr().out
