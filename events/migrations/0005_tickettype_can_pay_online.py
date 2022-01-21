# Generated by Django 3.2.11 on 2022-01-21 23:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_alter_event_notice'),
    ]

    operations = [
        migrations.AddField(
            model_name='tickettype',
            name='can_pay_online',
            field=models.BooleanField(default=True, help_text='Determines if online payments are allowed at all for this type.', verbose_name='can pay online'),
        ),
    ]
