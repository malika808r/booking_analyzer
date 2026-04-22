def get_trunc_value(group_by: str) -> str:
    trunc_map = {"День": "day", "Неделя": "week", "Месяц": "month"}
    return trunc_map.get(group_by, "day")