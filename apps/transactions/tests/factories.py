import factory
from factory.django import DjangoModelFactory
from apps.transactions.models import SalesTransaction


class SalesTransactionFactory(DjangoModelFactory):
    class Meta:
        model = SalesTransaction

    transaction_id = factory.Sequence(lambda n: f"TXN-{n:05d}")
    amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    date = factory.Faker("date_object")
    customer_id = factory.Sequence(lambda n: f"CUST-{n:04d}")
    high_risk = False
