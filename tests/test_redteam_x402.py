"""x402 402-challenge validation — the enforce point for scenario 6 (payto-swap).

``validate_challenge`` must accept a challenge that matches the out-of-band provisioning
policy and refuse a mismatched pay_to / asset / amount / scheme — raising a typed
``ChallengeError`` whose message names the FAILED FIELD but never the attacker value.
Pure, no network, never auto-pays.
"""

from __future__ import annotations

import pytest

from gecko.x402 import (
    Challenge,
    ChallengeError,
    PaymentPolicy,
    parse_challenge,
    validate_challenge,
)

_PROVISIONED_PAY_TO = "0xa11ce0000000000000000000000000000000a11e"
_ATTACKER_ADDR = "0xdeaddeaddeaddeaddeaddeaddeaddeaddeaddead"

_POLICY = PaymentPolicy(
    allowed_pay_to=frozenset({_PROVISIONED_PAY_TO}),
    allowed_assets=frozenset({"USDC"}),
    max_amount=1_000_000,
    scheme="exact",
)


def _challenge(**overrides) -> dict:
    body = {
        "pay_to": _PROVISIONED_PAY_TO,
        "max_amount": 500_000,
        "asset": "USDC",
        "scheme": "exact",
    }
    body.update(overrides)
    return body


def test_validate_challenge_accepts_provisioned():
    result = validate_challenge(_challenge(), _POLICY)
    assert isinstance(result, Challenge)
    assert result.pay_to == _PROVISIONED_PAY_TO
    assert result.max_amount == 500_000
    assert result.asset == "USDC"


def test_validate_challenge_rejects_untrusted_pay_to():
    with pytest.raises(ChallengeError):
        validate_challenge(_challenge(pay_to=_ATTACKER_ADDR), _POLICY)


def test_validate_challenge_rejects_unknown_asset():
    with pytest.raises(ChallengeError):
        validate_challenge(_challenge(asset="SCAMCOIN"), _POLICY)


def test_validate_challenge_rejects_amount_over_ceiling():
    with pytest.raises(ChallengeError):
        validate_challenge(_challenge(max_amount=999_000_000), _POLICY)


def test_challenge_error_message_redacts_attacker_address():
    with pytest.raises(ChallengeError) as exc:
        validate_challenge(_challenge(pay_to=_ATTACKER_ADDR), _POLICY)
    assert _ATTACKER_ADDR not in str(exc.value)
    assert "pay_to" in str(exc.value)  # names the field, not the value


def test_parse_challenge_rejects_malformed_body():
    with pytest.raises(ChallengeError):
        parse_challenge({"asset": "USDC", "max_amount": 10})  # missing pay_to
    with pytest.raises(ChallengeError):
        parse_challenge({"pay_to": _PROVISIONED_PAY_TO, "asset": "USDC"})  # no amount


def test_parse_challenge_accepts_real_x402_accepts_envelope():
    body = {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "payTo": _PROVISIONED_PAY_TO,
                "maxAmountRequired": "500000",
                "asset": "USDC",
            }
        ],
    }
    result = validate_challenge(body, _POLICY)
    assert result.max_amount == 500_000
