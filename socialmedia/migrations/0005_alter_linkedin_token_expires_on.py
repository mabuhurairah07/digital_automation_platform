# Generated by Django 5.2.1 on 2025-06-04 09:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('socialmedia', '0004_rename_long_live_access_token_x_access_token_secret_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='linkedin',
            name='token_expires_on',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
