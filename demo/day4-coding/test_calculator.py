from calculator import add


def test_adds_positive_integers() -> None:
    assert add(7, 5) == 12


def test_adds_negative_integers() -> None:
    assert add(-4, -6) == -10
