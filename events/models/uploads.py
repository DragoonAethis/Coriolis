import pyrage
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from events.dynaforms.fields import SIMPLE_IDENTIFIER_PATTERN
from events.models.events import Event


class AgePublicKeyType(models.TextChoices):
    AGE_X25519 = "age-x25519", _("Age-native X25519 Public Key (age1...)")
    SSH_ED25519 = "ssh-ed25519", _("SSH Ed25519 Public Key (ssh-ed25519 ...)")


class AgePublicKey(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name=_("event"))
    name = models.CharField(
        max_length=256,
        verbose_name=_("name"),
        help_text=_("Friendly public key name to be used as its unique identifier."),
        validators=[
            RegexValidator(
                regex=SIMPLE_IDENTIFIER_PATTERN,
                message=_("The name may contain ASCII letters, numbers, underscores and dashes only."),
            ),
        ],
    )
    kind = models.CharField(
        verbose_name=_("kind"),
        choices=AgePublicKeyType,
    )
    pubkey = models.CharField(
        verbose_name=_("pubkey"),
        max_length=2048,
        help_text=_("The public key to use for cryptographic operations."),
    )

    class Meta:
        verbose_name = _("Age public key")
        verbose_name_plural = _("Age public keys")
        constraints = [models.UniqueConstraint(fields=["event", "name"], name="pubkey_names_unique_in_event")]

    def __str__(self) -> str:
        return f"{self.name}"

    def clean(self):
        self.pubkey = self.pubkey.strip()

        if self.kind == AgePublicKeyType.AGE_X25519:
            if not self.pubkey.startswith("age1"):
                raise ValidationError({"pubkey": _("Age-native X25519 keys must begin with 'age1'.")})
        elif self.kind == AgePublicKeyType.SSH_ED25519:
            if not self.pubkey.startswith("ssh-ed25519 "):
                raise ValidationError({"pubkey": _("SSH Ed25519 keys must begin with 'ssh-ed25519'.")})
        else:
            raise NotImplementedError("New key kind, check the format!")

    def to_pyrage_recipient(self):
        if self.kind == AgePublicKeyType.AGE_X25519:
            recipient_type = pyrage.x25519.Recipient
        elif self.kind == AgePublicKeyType.SSH_ED25519:
            recipient_type = pyrage.ssh.Recipient
        else:
            raise TypeError(f"Age public key type {self.kind} is not known.")

        return recipient_type.from_str(self.pubkey)

    @classmethod
    def resolve_pubkeys(cls, event: Event, key_names: list[str]) -> (list, dict[str, Exception]):
        recipients = []
        errors = {}

        for pubkey_name in sorted(set(key_names)):
            try:
                key = cls.objects.get(event=event, name=pubkey_name)
                recipients.append(key.to_pyrage_recipient())
            except Exception as e:
                errors[pubkey_name] = e

        return recipients, errors
