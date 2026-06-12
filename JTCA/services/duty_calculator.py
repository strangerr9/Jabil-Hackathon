"""
============================================================
JTCA - Services: Duty Calculator
Formula: Estimated Duty = Declared Value × (Tariff Percent / 100)
============================================================
"""

import logging

logger = logging.getLogger(__name__)


def calculate_duty(declared_value: float, tariff_percent: float) -> float:
    """
    Calculate estimated import duty.

    Formula:
        Estimated Duty = Declared Value × (Tariff % / 100)

    Args:
        declared_value: Product value in USD
        tariff_percent: Tariff rate as percentage (e.g., 5.0 = 5%)

    Returns:
        Calculated duty amount in USD, rounded to 2 decimal places
    """
    if declared_value <= 0 or tariff_percent < 0:
        return 0.0

    duty = declared_value * (tariff_percent / 100.0)
    result = round(duty, 2)
    logger.debug(
        f"Duty calculation: ${declared_value:,.2f} × {tariff_percent}% = ${result:,.2f}"
    )
    return result


def calculate_landed_cost(declared_value: float, estimated_duty: float) -> float:
    """
    Calculate total landed cost (value + duty).

    Args:
        declared_value: Product value in USD
        estimated_duty: Calculated duty in USD

    Returns:
        Total landed cost in USD
    """
    return round(declared_value + estimated_duty, 2)


def format_duty_breakdown(
    declared_value: float,
    tariff_percent: float,
    estimated_duty: float,
) -> list[str]:
    """
    Generate calculation step strings for display in the UI.

    Args:
        declared_value: Product value in USD
        tariff_percent: Applied tariff rate %
        estimated_duty: Calculated duty amount

    Returns:
        List of calculation step strings
    """
    landed_cost = calculate_landed_cost(declared_value, estimated_duty)
    return [
        f"Step 1 — Declared Value:       USD {declared_value:>12,.2f}",
        f"Step 2 — Applied Tariff Rate:  {tariff_percent:>11.2f}%",
        f"Step 3 — Duty Calculation:     {declared_value:,.2f} × {tariff_percent}% ÷ 100",
        f"Step 4 — Estimated Duty:       USD {estimated_duty:>12,.2f}",
        "-" * 52,
        f"Step 5 — Total Landed Cost:    USD {landed_cost:>12,.2f}",
    ]
