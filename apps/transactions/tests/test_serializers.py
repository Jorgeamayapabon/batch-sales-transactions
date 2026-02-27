import pytest
from apps.transactions.serializers import (
    SalesTransactionSerializer,
    BatchTransactionSerializer,
)


VALID_TRANSACTION = {
    "transaction_id": "TXN-001",
    "amount": "500.00",
    "date": "2024-01-15",
    "customer_id": "CUST-001",
}

HIGH_RISK_TRANSACTION = {
    "transaction_id": "TXN-002",
    "amount": "15000.00",
    "date": "2024-01-15",
    "customer_id": "CUST-002",
}


@pytest.mark.django_db
class TestSalesTransactionSerializer:
    def test_valid_data_is_accepted(self):
        serializer = SalesTransactionSerializer(data=VALID_TRANSACTION)
        assert serializer.is_valid(), serializer.errors

    def test_missing_transaction_id_raises_error(self):
        data = {**VALID_TRANSACTION}
        del data["transaction_id"]
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "transaction_id" in serializer.errors

    def test_missing_amount_raises_error(self):
        data = {**VALID_TRANSACTION}
        del data["amount"]
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_missing_date_raises_error(self):
        data = {**VALID_TRANSACTION}
        del data["date"]
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "date" in serializer.errors

    def test_missing_customer_id_raises_error(self):
        data = {**VALID_TRANSACTION}
        del data["customer_id"]
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "customer_id" in serializer.errors

    def test_zero_amount_raises_error(self):
        data = {**VALID_TRANSACTION, "amount": "0.00"}
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_negative_amount_raises_error(self):
        data = {**VALID_TRANSACTION, "amount": "-100.00"}
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_empty_transaction_id_raises_error(self):
        data = {**VALID_TRANSACTION, "transaction_id": "   "}
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "transaction_id" in serializer.errors

    def test_invalid_date_format_raises_error(self):
        data = {**VALID_TRANSACTION, "date": "15-01-2024"}
        serializer = SalesTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "date" in serializer.errors

    def test_high_risk_is_read_only(self):
        data = {**VALID_TRANSACTION, "high_risk": True}
        serializer = SalesTransactionSerializer(data=data)
        assert serializer.is_valid()
        # high_risk read_only: no aparece en validated_data
        assert "high_risk" not in serializer.validated_data


@pytest.mark.django_db
class TestBatchTransactionSerializer:
    def test_valid_batch_is_accepted(self):
        data = {"transactions": [VALID_TRANSACTION, HIGH_RISK_TRANSACTION]}
        serializer = BatchTransactionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_empty_batch_raises_error(self):
        serializer = BatchTransactionSerializer(data={"transactions": []})
        assert not serializer.is_valid()
        assert "transactions" in serializer.errors

    def test_missing_transactions_key_raises_error(self):
        serializer = BatchTransactionSerializer(data={})
        assert not serializer.is_valid()
        assert "transactions" in serializer.errors

    def test_duplicate_transaction_ids_in_batch_raises_error(self):
        data = {
            "transactions": [
                VALID_TRANSACTION,
                {**VALID_TRANSACTION, "customer_id": "CUST-999"},
            ]
        }
        serializer = BatchTransactionSerializer(data=data)
        assert not serializer.is_valid()
        assert "transactions" in serializer.errors

    def test_batch_create_persists_records(self):
        data = {"transactions": [VALID_TRANSACTION, HIGH_RISK_TRANSACTION]}
        serializer = BatchTransactionSerializer(data=data)
        assert serializer.is_valid()
        instances = serializer.save()
        assert len(instances) == 2

    def test_batch_create_sets_high_risk_correctly(self):
        data = {"transactions": [VALID_TRANSACTION, HIGH_RISK_TRANSACTION]}
        serializer = BatchTransactionSerializer(data=data)
        assert serializer.is_valid()
        instances = serializer.save()

        normal = next(i for i in instances if i.transaction_id == "TXN-001")
        risky = next(i for i in instances if i.transaction_id == "TXN-002")

        assert normal.high_risk is False
        assert risky.high_risk is True

    def test_batch_with_invalid_item_returns_errors(self):
        data = {
            "transactions": [
                VALID_TRANSACTION,
                {"transaction_id": "TXN-003", "amount": "-50", "date": "2024-01-01", "customer_id": "C1"},
            ]
        }
        serializer = BatchTransactionSerializer(data=data)
        assert not serializer.is_valid()
