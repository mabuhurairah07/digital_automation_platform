from django.db import models
from django.contrib.auth.models import User
import uuid
from datetime import datetime
from .enums import PostStatus, PostType


class Linkedin(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_id = models.CharField(max_length=50, blank=True, null=True)
    access_token = models.CharField(max_length=1000, null=True, blank=True)
    long_live_access_token = models.CharField(max_length=1000, null=True, blank=True)
    refresh_token = models.CharField(max_length=1000, null=True, blank=True)
    token_expires_on = models.DateTimeField()
    is_authenticated = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)
    refresh_token_expires_in = models.IntegerField(null=True, blank=True)


class X(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_id = models.CharField(max_length=50, blank=True, null=True)
    access_token = models.CharField(max_length=1000, null=True, blank=True)
    access_token_secret = models.CharField(max_length=1000, null=True, blank=True)
    is_authenticated = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)


class Instagram(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_id = models.CharField(max_length=50, blank=True, null=True)
    access_token = models.CharField(max_length=1000, null=True, blank=True)
    long_live_access_token = models.CharField(max_length=1000, null=True, blank=True)
    refresh_token = models.CharField(max_length=1000, null=True, blank=True)
    token_expires_on = models.DateTimeField()
    is_authenticated = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)
    refresh_token_expires_in = models.IntegerField(null=True, blank=True)


class TikTok(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=1000, null=True, blank=True)
    long_live_access_token = models.CharField(max_length=1000, null=True, blank=True)
    refresh_token = models.CharField(max_length=1000, null=True, blank=True)
    token_expires_on = models.DateTimeField()
    is_authenticated = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)
    refresh_token_expires_in = models.IntegerField(null=True, blank=True)


class PostedContent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post_id = models.IntegerField(null=True, blank=True)
    post_type = models.CharField(
        max_length=20,
        default=PostType.TEXT.value,
        choices=PostType.choices(),
        null=False,
        blank=False,
    )
    post_status = models.CharField(
        default=PostStatus.PENDING.value, choices=PostStatus.choices()
    )
    is_posted = models.BooleanField(default=False)
    error_reason = models.CharField(max_length=1000, null=True, blank=True)
    platform_name = models.CharField(max_length=100, null=False, blank=False)


class UserUploadedFiles(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    linkedin_file_path = models.CharField(max_length=500, null=True, blank=True)
    x_file_path = models.CharField(max_length=500, null=True, blank=True)
    instagram_file_path = models.CharField(max_length=500, null=True, blank=True)
    tiktok_file_path = models.CharField(max_length=500, null=True, blank=True)
