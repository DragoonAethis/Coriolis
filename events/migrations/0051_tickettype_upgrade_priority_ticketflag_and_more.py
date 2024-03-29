# Generated by Django 4.2.9 on 2024-01-22 01:37

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0050_ticket_customization_approved_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettype",
            name="upgrade_priority",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Tickets with lower priority may be upgraded to higher priority types in some situations (like being added to an organization).",
                verbose_name="upgrade priority",
            ),
        ),
        migrations.CreateModel(
            name="TicketFlag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=256, verbose_name="name")),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="What does this flag mean?",
                        verbose_name="description",
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        null=True,
                        blank=True,
                        help_text="Additional JSON metadata to attach to this flag.",
                        verbose_name="metadata",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="events.event",
                        verbose_name="event",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="tickettype",
            name="flags",
            field=models.ManyToManyField(
                help_text="Flags to apply on all tickets of this type.",
                to="events.ticketflag",
                verbose_name="flags",
            ),
        ),
    ]
