# Generated by Django 5.2.1 on 2025-06-03 13:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('socialmedia', '0003_alter_instagram_access_token_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='x',
            old_name='long_live_access_token',
            new_name='access_token_secret',
        ),
        migrations.RemoveField(
            model_name='x',
            name='refresh_token',
        ),
        migrations.RemoveField(
            model_name='x',
            name='refresh_token_expires_in',
        ),
        migrations.RemoveField(
            model_name='x',
            name='token_expires_on',
        ),
    ]
