"""Regression coverage for workflow retry limits and checkpoint ordering."""

import pytest

from gameday_lab.workflows.executor import WorkflowExecutor, checkpoint_key, idempotency_key
from gameday_lab.workflows.runner import RefundRequest
from gameday_lab.workflows.services import (
    DurableStore,
    FaultProfile,
    ServiceError,
    Services,
    ServiceTimeout,
    WorkerCrash,
)

REQ = RefundRequest("extra-session", "ord_extra", 4900, "extra@example.com")
NO_FAULTS = FaultProfile(0.0, 0.0, 0.0)


def test_exhausted_retry_budget_never_checkpoints_failed_step() -> None:
    services, store = Services.build(1, NO_FAULTS), DurableStore()
    services.llm.faults = FaultProfile(1.0, 0.0, 0.0)

    with pytest.raises(ServiceError):
        WorkflowExecutor(services, store, max_attempts=3).run(REQ)

    assert services.llm.requests == 3
    assert services.llm.executions == 0
    assert store.writes == 0
    assert services.payments.requests == 0


def test_final_timeout_leaves_payment_uncheckpointed_and_resume_deduplicates() -> None:
    services, store = Services.build(1, NO_FAULTS), DurableStore()
    services.payments.faults = FaultProfile(0.0, 1.0, 0.0)

    with pytest.raises(ServiceTimeout):
        WorkflowExecutor(services, store, max_attempts=1).run(REQ)

    assert services.payments.requests == 1
    assert len(services.payments.ledger) == 1
    assert store.get(checkpoint_key(REQ, "issue_refund")) is None
    assert store.get(checkpoint_key(REQ, "send_email")) is None

    result = WorkflowExecutor(services, store, max_attempts=1).run(REQ)
    assert result["status"] == "done"
    assert services.payments.requests == 2
    assert len(services.payments.ledger) == 1


def test_crash_after_email_preserves_completed_steps_and_deduplicates_email() -> None:
    services, store = Services.build(1, NO_FAULTS), DurableStore()
    services.email.faults = FaultProfile(0.0, 0.0, 1.0)

    with pytest.raises(WorkerCrash):
        WorkflowExecutor(services, store).run(REQ)

    assert store.get(checkpoint_key(REQ, "issue_refund")) is not None
    assert store.get(checkpoint_key(REQ, "send_email")) is None
    assert store.writes == 3
    assert services.email.requests == 1

    result = WorkflowExecutor(services, store).run(REQ)
    assert result["status"] == "done"
    assert services.llm.executions == 2
    assert services.payments.requests == 1
    assert len(services.email.outbox) == 1
    assert store.writes == 5


@pytest.mark.parametrize("key_fn", [idempotency_key, checkpoint_key])
def test_session_and_step_delimiters_cannot_collide(key_fn) -> None:
    left = RefundRequest("session:part", "ord_extra", 4900, "extra@example.com")
    right = RefundRequest("session", "ord_extra", 4900, "extra@example.com")
    assert key_fn(left, "refund") != key_fn(right, "part:refund")


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_nonpositive_attempt_limit_is_rejected(max_attempts: int) -> None:
    with pytest.raises(ValueError):
        WorkflowExecutor(Services.build(1, NO_FAULTS), DurableStore(), max_attempts=max_attempts)
