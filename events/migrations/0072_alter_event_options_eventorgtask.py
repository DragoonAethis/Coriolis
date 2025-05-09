# Generated by Django 4.2.19 on 2025-02-09 22:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0071_eventorg_location_tag"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="event",
            options={
                "permissions": [
                    ("crew_accreditation", "Can access the crew accreditation panel."),
                    ("crew_mod_queue", "Can access the crew mod queue."),
                    ("crew_orgs", "Can access the crew organization lists."),
                    (
                        "crew_orgs_view_tasks",
                        "Can access the crew organization task lists.",
                    ),
                    (
                        "crew_orgs_view_invoices",
                        "Can access the org invoices from the crew panel.",
                    ),
                    (
                        "crew_orgs_view_billing_details",
                        "Can access the org billing details from the crew panel.",
                    ),
                ],
                "verbose_name": "event",
                "verbose_name_plural": "events",
            },
        ),
        migrations.CreateModel(
            name="EventOrgTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(auto_now_add=True, verbose_name="created"),
                ),
                (
                    "updated",
                    models.DateTimeField(auto_now=True, verbose_name="updated"),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Large task name displayed in the org overview",
                        max_length=256,
                        verbose_name="name",
                    ),
                ),
                ("done", models.BooleanField(default=False, verbose_name="done")),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Extra notes displayed under the task",
                        verbose_name="notes",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_set",
                        to="events.event",
                        verbose_name="event",
                    ),
                ),
                (
                    "event_org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_set",
                        to="events.eventorg",
                        verbose_name="event org",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="updated by",
                    ),
                ),
            ],
        ),
    ]
