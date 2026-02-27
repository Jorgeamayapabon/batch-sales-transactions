import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.transactions.models import SalesTransaction


BATCH_URL = "/api/transactions/batch/"

VALID_PAYLOAD = {
    "transactions": [
        {
            "transaction_id": "TXN-VIEW-001",
            "amount": "250.00",
            "date": "2024-03-10",
            "customer_id": "CUST-V01",
        },
        {
            "transaction_id": "TXN-VIEW-002",
            "amount": "12500.00",
            "date": "2024-03-11",
            "customer_id": "CUST-V02",
        },
    ]
}


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestBatchTransactionView:
    def test_returns_201_on_valid_payload(self, api_client):
        response = api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_response_contains_created_count(self, api_client):
        response = api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        assert response.data["created"] == 2

    def test_response_contains_transactions_list(self, api_client):
        response = api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        assert len(response.data["transactions"]) == 2

    def test_high_risk_flag_is_set_correctly_in_response(self, api_client):
        response = api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        txns = {t["transaction_id"]: t for t in response.data["transactions"]}
        assert txns["TXN-VIEW-001"]["high_risk"] is False
        assert txns["TXN-VIEW-002"]["high_risk"] is True

    def test_transactions_are_persisted_in_db(self, api_client):
        api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        assert SalesTransaction.objects.filter(transaction_id="TXN-VIEW-001").exists()
        assert SalesTransaction.objects.filter(transaction_id="TXN-VIEW-002").exists()

    def test_returns_400_for_empty_transactions(self, api_client):
        response = api_client.post(BATCH_URL, {"transactions": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_400_for_missing_required_fields(self, api_client):
        payload = {
            "transactions": [
                {"amount": "100.00", "date": "2024-01-01"},
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.data

    def test_returns_400_for_negative_amount(self, api_client):
        payload = {
            "transactions": [
                {
                    "transaction_id": "TXN-NEG",
                    "amount": "-500.00",
                    "date": "2024-01-01",
                    "customer_id": "CUST-NEG",
                }
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_400_for_duplicate_transaction_ids(self, api_client):
        payload = {
            "transactions": [
                {
                    "transaction_id": "SAME-ID",
                    "amount": "100.00",
                    "date": "2024-01-01",
                    "customer_id": "C1",
                },
                {
                    "transaction_id": "SAME-ID",
                    "amount": "200.00",
                    "date": "2024-01-02",
                    "customer_id": "C2",
                },
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_400_for_invalid_date_format(self, api_client):
        payload = {
            "transactions": [
                {
                    "transaction_id": "TXN-DATE",
                    "amount": "100.00",
                    "date": "01/01/2024",
                    "customer_id": "CUST-DATE",
                }
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_post_only_method_allowed(self, api_client):
        response = api_client.get(BATCH_URL)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_response_includes_id_and_created_at_fields(self, api_client):
        response = api_client.post(BATCH_URL, VALID_PAYLOAD, format="json")
        txn = response.data["transactions"][0]
        assert "id" in txn
        assert "created_at" in txn

    def test_high_risk_boundary_exactly_10000(self, api_client):
        payload = {
            "transactions": [
                {
                    "transaction_id": "TXN-BOUNDARY",
                    "amount": "10000.00",
                    "date": "2024-01-01",
                    "customer_id": "CUST-B",
                }
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["transactions"][0]["high_risk"] is False

    def test_high_risk_boundary_just_above_10000(self, api_client):
        payload = {
            "transactions": [
                {
                    "transaction_id": "TXN-ABOVE",
                    "amount": "10000.01",
                    "date": "2024-01-01",
                    "customer_id": "CUST-AB",
                }
            ]
        }
        response = api_client.post(BATCH_URL, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["transactions"][0]["high_risk"] is True
