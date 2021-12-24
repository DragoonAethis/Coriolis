# Generated by Django 3.2.10 on 2021-12-23 21:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_auto_20211222_0007'),
    ]

    operations = [
        migrations.AddField(
            model_name='tickettype',
            name='show_tickets_remaining',
            field=models.BooleanField(default=True, help_text='Display the number of tickets left publicly?', verbose_name='show tickets remaining'),
        ),
    ]