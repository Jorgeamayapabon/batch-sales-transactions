from django.urls import path
from .views import BatchTransactionView

app_name = "transactions"

urlpatterns = [
    path("transactions/batch/", BatchTransactionView.as_view(), name="batch-transactions"),
]
