from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    exempt_from_2fa = models.BooleanField(
        default=False,
        verbose_name=_("exempt from 2FA"),
        help_text=_(
            "If enabled, this user does not have to enable 2FA even if the usual security policies would enforce it."
        ),
    )

    def __str__(self):
        return f"{self.email or self.username or self.id}"
