"""Concurrent cooldown results must retain the reason for the selected expiry."""

from gameday_lab.client import ResilientClient
from gameday_lab.errors import ErrorKind
from gameday_lab.sim.contracts import Attempt, CallContext, GiveUp, ProviderError, ProviderInfo, Send


def test_late_rate_limit_cannot_turn_quota_into_a_short_wait() -> None:
    client = ResilientClient(
        {"alpha": ProviderInfo("alpha", "A", "us", True, 1.0)},
        ["alpha"], {"quota_cooldown_s": 300.0},
    )
    calls = [CallContext(i, i, "tool", 0.0, 30.0) for i in (1, 2)]
    sends = [client.start(call, 0.0) for call in calls]
    assert all(isinstance(send, Send) for send in sends)
    for call, send, error, now in zip(calls, sends, [
        ProviderError("alpha", 429, "insufficient_quota"),
        ProviderError("alpha", 429, "rate_limit_exceeded", retry_after=2.0),
    ], [0.0, 1.0]):
        assert isinstance(send, Send)
        client.on_error(Attempt(call, "alpha", 1, 0.0, send.tag), error, now)
    assert client.cooldown_until["alpha"] == 300.0
    action = client.start(CallContext(3, 3, "tool", 296.0, 326.0), 296.0)
    assert isinstance(action, GiveUp)
    assert client.cooldown_kind["alpha"] is ErrorKind.QUOTA_EXHAUSTED
