from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    def __str__(self):
        return f"{self.email or self.username or self.id}"
