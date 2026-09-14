from monitor import total_alarm_count


def test_combines_temperature_and_vibration_alarm_counts() -> None:
    assert total_alarm_count(7, 5) == 12


def test_temperature_only_alarm_count() -> None:
    assert total_alarm_count(3, 0) == 3


def test_zero_alarm_count() -> None:
    assert total_alarm_count(0, 0) == 0
