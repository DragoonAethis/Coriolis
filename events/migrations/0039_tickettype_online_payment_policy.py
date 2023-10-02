# Generated by Django 4.2.5 on 2023-10-02 04:02

from django.db import migrations, models


def ticket_type_unify_payment_policy(apps, schema_editor):
    for row in apps.get_model("events", "TicketType").objects.all():
        if not row.can_pay_online:
            policy = 0  # Disabled
        elif not row.must_pay_online:
            policy = 1  # Enabled
        else:
            policy = 2  # Required

        row.online_payment_policy = policy
        row.save(update_fields=["online_payment_policy"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0038_remove_ticket_vaccination_proof"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettype",
            name="online_payment_policy",
            field=models.IntegerField(
                choices=[(0, "Disabled"), (1, "Enabled"), (2, "Required")],
                default=1,
                verbose_name="online payment policy",
            ),
        ),
        migrations.RunPython(ticket_type_unify_payment_policy, reverse_code=migrations.RunPython.noop),
    ]
