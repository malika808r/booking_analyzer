from stats_sql import get_trunc_value

def test_get_trunc_value_valid():
    
    assert get_trunc_value("День") == "day"
    assert get_trunc_value("Неделя") == "week"
    assert get_trunc_value("Месяц") == "month"

def test_get_trunc_value_invalid():
    
    assert get_trunc_value("Год") == "day"
    assert get_trunc_value("Абракадабра") == "day"