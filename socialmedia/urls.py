"""
URL configuration for digitalplatform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("upload_file/", views.GetExcellFileView.as_view(), name="upload_file"),
    path(
        "verify_linkedin/", views.VerifyLinkedInView.as_view(), name="verify_linkedin"
    ),
    path("verify_tiktok/", views.VerifyTikTokView.as_view(), name="verify_tiktok"),
    path("get_x_auth/", views.GetXAuthorizationURLView.as_view(), name="get_x_auth"),
    path("verify_x/", views.VerifyTwitterView.as_view(), name="verify_x"),
    path("posts_stats/", views.GetPostStatsView.as_view(), name="verify_x"),
    path(
        "user_accounts/",
        views.GetUserSocialMediaAccountsView.as_view(),
        name="user_accounts",
    ),
]
