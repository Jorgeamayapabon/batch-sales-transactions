from rest_framework import serializers
from .models import SalesTransaction, HIGH_RISK_THRESHOLD


class SalesTransactionSerializer(serializers.ModelSerializer):
    high_risk = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SalesTransaction
        fields = [
            "id",
            "transaction_id",
            "amount",
            "date",
            "customer_id",
            "high_risk",
            "created_at",
        ]
        read_only_fields = ["id", "high_risk", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value

    def validate_transaction_id(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("El ID de transacción no puede estar vacío.")
        return value.strip()

    def validate_customer_id(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("El ID de cliente no puede estar vacío.")
        return value.strip()


class BatchTransactionSerializer(serializers.Serializer):
    transactions = SalesTransactionSerializer(many=True, allow_empty=False)

    def validate_transactions(self, transactions):
        transaction_ids = [t["transaction_id"] for t in transactions]
        if len(transaction_ids) != len(set(transaction_ids)):
            raise serializers.ValidationError(
                "El lote contiene IDs de transacción duplicados."
            )
        return transactions

    def create(self, validated_data):
        items = validated_data["transactions"]
        instances = []
        for item in items:
            item["high_risk"] = item["amount"] > HIGH_RISK_THRESHOLD
            instance = SalesTransaction(**item)
            instances.append(instance)
        return SalesTransaction.objects.bulk_create(instances)
