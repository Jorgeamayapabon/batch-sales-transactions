from django.db import models

HIGH_RISK_THRESHOLD = 10_000.00


class SalesTransaction(models.Model):
    transaction_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    customer_id = models.CharField(max_length=100)
    high_risk = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaction {self.transaction_id} | ${self.amount} | risk={self.high_risk}"

    def save(self, *args, **kwargs):
        self.high_risk = self.amount > HIGH_RISK_THRESHOLD
        super().save(*args, **kwargs)
