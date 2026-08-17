"""Isolated transformation-task coverage for the weekly business pipeline."""

from __future__ import annotations

from typing import Any

from nexova_pipelines.pipeline import transform_weekly_office_program_performance_task


WEEK_START = "2026-08-03"


def event(
    event_id: str,
    event_type: str,
    *,
    office: str = "valencia",
    programme_id: str = "leadership-foundations",
    currency: str = "EUR",
    timestamp: str = "2026-08-05T10:00:00Z",
    **tags: Any,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "tags": {
            "office": office,
            "programme_id": programme_id,
            "currency": currency,
            **tags,
        },
    }


def transform(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Exercise only the transformation task function, without storage or flows."""

    return transform_weekly_office_program_performance_task.fn(events, WEEK_START)


def test_material_cost_matches_hand_calculated_kpi() -> None:
    result = transform(
        [
            event("inbound-1", "inbound_order_created", quantity=4, unit_cost=12.5),
            event("inbound-2", "inbound_order_created", quantity=2, unit_cost=10),
        ]
    )

    # Hand calculation: (4 x 12.50) + (2 x 10.00) = EUR 70.00.
    assert result["rows"][0]["total_material_cost"] == 70.0
    assert result["rows"][0]["currency"] == "EUR"


def test_operational_event_counts_map_to_the_three_frequency_kpis() -> None:
    result = transform(
        [
            event("delivery-1", "outbound_order_created"),
            event("delivery-2", "outbound_order_created"),
            event("shortage-1", "stock_threshold_triggered"),
            event("variance-1", "kit_cost_variance_detected"),
            event("variance-2", "kit_cost_variance_detected"),
        ]
    )

    assert result["rows"][0] == {
        "office": "valencia",
        "programme_id": "leadership-foundations",
        "week_start": WEEK_START,
        "currency": "EUR",
        "total_material_cost": 0.0,
        "kits_delivered_count": 2,
        "shortage_events_count": 1,
        "cost_variance_events_count": 2,
    }


def test_invalid_inputs_are_rejected_without_creating_a_kpi_row() -> None:
    invalid_events = [
        event("currency", "outbound_order_created", currency="USD"),
        event("quantity", "inbound_order_created", quantity=True, unit_cost=5),
        event(
            "outside-window",
            "outbound_order_created",
            timestamp="2026-08-10T00:00:00Z",
        ),
        event("unknown", "unapproved_event_type"),
        {
            "id": "missing-tags",
            "timestamp": "2026-08-05T10:00:00Z",
            "event_type": "outbound_order_created",
        },
    ]

    result = transform(invalid_events)

    assert result["records_extracted"] == 5
    assert result["records_rejected"] == 5
    assert result["rows"] == []


def test_duplicate_event_id_is_counted_once() -> None:
    delivered = event("same-event", "outbound_order_created")

    result = transform([delivered, dict(delivered)])

    assert result["records_deduplicated"] == 1
    assert result["rows"][0]["kits_delivered_count"] == 1
