from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .middleware import log_response_time
from .serializers import BatchTransactionSerializer, SalesTransactionSerializer


class BatchTransactionView(APIView):
    """
    Recibe un lote de transacciones de ventas, valida y persiste en PostgreSQL.

    POST /api/transactions/batch/
    Body: { "transactions": [ { transaction_id, amount, date, customer_id }, ... ] }
    """

    @log_response_time
    def post(self, request):
        serializer = BatchTransactionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instances = serializer.save()
        except Exception as exc:
            return Response(
                {"error": "Error interno al guardar las transacciones.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        output = SalesTransactionSerializer(instances, many=True)
        return Response(
            {
                "created": len(instances),
                "transactions": output.data,
            },
            status=status.HTTP_201_CREATED,
        )
