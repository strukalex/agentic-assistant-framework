from datetime import datetime, timedelta, timezone
import pytest

from paias.models.approval_request import ApprovalRequest, ApprovalStatus


def test_approval_request_defaults_and_timeout_window() -> None:
    req = ApprovalRequest(
        action_type="send_email",
        action_description="Send summary email",
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.timeout_at is not None
    delta = abs((req.timeout_at - req.requested_at).total_seconds())
    assert 290 <= delta <= 310


def test_approval_request_rejects_bad_timeout() -> None:
    requested_at = datetime.now(timezone.utc)
    bad_timeout = requested_at + timedelta(seconds=200)
    with pytest.raises(ValueError):
        ApprovalRequest(
            action_type="send_email",
            action_description="Send summary email",
            requested_at=requested_at,
            timeout_at=bad_timeout,
        )

