"""Additional boundary checks for Part E; the supplied tests stay unchanged."""

from gameday_lab.slo.alerting import (
    AlertEvent,
    AlertRule,
    BurnRateAlerter,
    WindowSums,
    error_budget_report,
)


def test_inclusive_threshold_and_exclusive_episode_end() -> None:
    rule = AlertRule("boundary", "ticket", 1, 1, 1.0)
    events = BurnRateAlerter(rules=(rule,)).evaluate(
        [1000] * 5, [0, 5, 5, 0, 5]
    )
    assert events == [
        AlertEvent("boundary", "ticket", 1, 3),
        AlertEvent("boundary", "ticket", 4, 5),
    ]


def test_long_window_must_also_reach_threshold() -> None:
    rule = AlertRule("both", "page", 4, 1, 1.0)
    # At minute 3 short-window burn is 2x, long-window burn is only 0.5x.
    assert BurnRateAlerter(slo=0.5, rules=(rule,)).evaluate(
        [100] * 4, [0, 0, 0, 100]
    ) == []


def test_episodes_sorted_across_rules() -> None:
    rules = (
        AlertRule("late", "page", 3, 1, 1.0),
        AlertRule("early", "ticket", 1, 1, 1.0),
    )
    events = BurnRateAlerter(slo=0.5, rules=rules).evaluate(
        [100] * 4, [0, 0, 100, 100]
    )
    assert events == [
        AlertEvent("early", "ticket", 2, 4),
        AlertEvent("late", "page", 3, 4),
    ]


def test_burn_rate_weights_requests_instead_of_minutes() -> None:
    # 10 bad of 1000 requests, despite one minute having 100% errors.
    assert abs(BurnRateAlerter().burn_rate(
        WindowSums([990, 10]), WindowSums([0, 10]), 1, 2
    ) - 2.0) < 1e-9


def test_no_traffic_does_not_fire() -> None:
    alerter = BurnRateAlerter()
    assert alerter.burn_rate(WindowSums([0]), WindowSums([0]), 0, 1) == 0.0
    assert alerter.evaluate([0, 0], [0, 0]) == []
    assert alerter.evaluate([], []) == []


def test_budget_with_no_requests() -> None:
    assert error_budget_report([], []) == {
        "requests": 0,
        "allowed_bad": 0.0,
        "bad": 0,
        "availability": 1.0,
        "budget_consumed": 0.0,
        "budget_remaining": 1.0,
        "freeze_releases": False,
    }


def test_budget_uses_unrounded_allowance_for_small_volume() -> None:
    result = error_budget_report([1], [1])
    assert result["allowed_bad"] == 0.0
    assert result["budget_consumed"] == 200.0
    assert result["budget_remaining"] == -199.0
    assert result["freeze_releases"] is True


def test_exactly_exhausted_budget_freezes_releases() -> None:
    result = error_budget_report([100000], [500])
    assert result["budget_remaining"] == 0.0
    assert result["freeze_releases"] is True


def test_rounding_does_not_freeze_while_one_request_of_budget_remains() -> None:
    result = error_budget_report([10_000_000], [49_999])
    assert result["budget_remaining"] == 0.0  # display rounding only
    assert result["freeze_releases"] is False
