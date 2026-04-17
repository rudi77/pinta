"""Startup config validation for paid flows."""

from types import SimpleNamespace

import pytest

from src.main import _validate_production_config


def _cfg(**kwargs):
    defaults = {
        "debug": False,
        "stripe_secret_key": "",
        "stripe_webhook_secret": "",
        "stripe_price_id": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestProductionConfigValidation:
    def test_no_stripe_configured_is_fine(self):
        _validate_production_config(_cfg())  # no-op

    def test_debug_bypasses_check(self):
        # Even with half-configured Stripe, debug mode boots.
        _validate_production_config(
            _cfg(debug=True, stripe_secret_key="sk_test_x")
        )

    def test_missing_webhook_secret_fails(self):
        with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
            _validate_production_config(
                _cfg(stripe_secret_key="sk_live_x", stripe_price_id="price_1")
            )

    def test_missing_price_id_fails(self):
        with pytest.raises(RuntimeError, match="STRIPE_PRICE_ID"):
            _validate_production_config(
                _cfg(stripe_secret_key="sk_live_x", stripe_webhook_secret="whsec_x")
            )

    def test_missing_both_lists_both(self):
        with pytest.raises(RuntimeError) as exc:
            _validate_production_config(_cfg(stripe_secret_key="sk_live_x"))
        assert "STRIPE_WEBHOOK_SECRET" in str(exc.value)
        assert "STRIPE_PRICE_ID" in str(exc.value)

    def test_fully_configured_passes(self):
        _validate_production_config(
            _cfg(
                stripe_secret_key="sk_live_x",
                stripe_webhook_secret="whsec_x",
                stripe_price_id="price_1",
            )
        )
