import factory

from apps.accounts.models import Customer, User

PASSWORD = "Str0ng!Pass"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    role = User.Role.CUSTOMER

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", PASSWORD)
        return model_class.objects.create_user(password=password, **kwargs)


class AdminFactory(UserFactory):
    role = User.Role.ADMIN


class StaffFactory(UserFactory):
    role = User.Role.STAFF


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    user = factory.SubFactory(UserFactory)
