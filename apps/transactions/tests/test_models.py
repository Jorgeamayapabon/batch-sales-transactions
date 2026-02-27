import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.transactions.models import HIGH_RISK_THRESHOLD
from .factories import SalesTransactionFactory


@pytest.mark.django_db
class TestSalesTransactionModel:
    def test_creates_transaction_successfully(self):
        tx = SalesTransactionFactory(amount=Decimal("500.00"))
        assert tx.pk is not None
        assert tx.transaction_id.startswith("TXN-")

    def test_high_risk_flag_set_when_amount_exceeds_threshold(self):
        tx = SalesTransactionFactory(amount=Decimal("10001.00"))
        assert tx.high_risk is True

    def test_high_risk_flag_not_set_when_amount_equals_threshold(self):
        tx = SalesTransactionFactory(amount=Decimal("10000.00"))
        assert tx.high_risk is False

    def test_high_risk_flag_not_set_below_threshold(self):
        tx = SalesTransactionFactory(amount=Decimal("9999.99"))
        assert tx.high_risk is False

    def test_high_risk_threshold_value(self):
        assert HIGH_RISK_THRESHOLD == 10_000.00

    def test_transaction_id_is_unique(self):
        SalesTransactionFactory(transaction_id="UNIQUE-001")
        with pytest.raises(IntegrityError):
            SalesTransactionFactory(transaction_id="UNIQUE-001")

    def test_str_representation(self):
        tx = SalesTransactionFactory(transaction_id="TXN-999", amount=Decimal("250.50"))
        assert "TXN-999" in str(tx)
        assert "250.50" in str(tx)

    def test_created_at_is_auto_populated(self):
        tx = SalesTransactionFactory()
        assert tx.created_at is not None
