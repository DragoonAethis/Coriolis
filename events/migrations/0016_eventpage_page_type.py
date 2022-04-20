# Generated by Django 3.2.13 on 2022-04-20 20:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0015_payment_billing_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventpage',
            name='page_type',
            field=models.CharField(choices=[('info', 'Informational'), ('hidden-info', 'Hidden Informational'), ('ticket-payment-info', 'Ticket Payment Instructions')], default='info', help_text='What this page is going to be used for?', max_length=32, verbose_name='page type'),
        ),
    ]
