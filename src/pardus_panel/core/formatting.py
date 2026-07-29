def format_bytes(value: float | int) -> str:
    amount = max(0.0, float(value))
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{amount:.{precision}f} {unit}"
        amount /= 1024.0
