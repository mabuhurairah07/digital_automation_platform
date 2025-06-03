from django.shortcuts import render
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import UserUploadedFiles, Linkedin, TikTok, X, Instagram
from .enums import Platforms
from .utils import RESPONSE
import pandas as pd
import digitalplatform.settings as settings
from datetime import timedelta, datetime
from .linkedin import get_user_linkedin_profile, authorize_user_linkedin
from requests_oauthlib import OAuth1
from .tiktok import authorize_user_tiktok
import requests
import time
import base64
import hmac
import hashlib
from urllib.parse import quote, parse_qsl
import uuid
import os


class SignupView(APIView):
    def post(self, request):
        user_name = request.data.get("username", None)
        user_email = request.data.get("email", None)
        password = request.data.get("password", None)
        first_name = request.data.get("firstName", None)
        last_name = request.data.get("lastName", None)

        if not user_name:
            return RESPONSE(
                message="Please Provide A UserName",
                status=False,
                status_code=404,
                response=None,
            )
        if not user_email:
            return RESPONSE(
                message="Please Provide An Email",
                status=False,
                status_code=404,
                response=None,
            )
        if not password:
            return RESPONSE(
                message="Please Provide A Password",
                status=False,
                status_code=404,
                response=None,
            )
        try:
            user = User.objects.get(username=user_name)
            if user:
                return RESPONSE(
                    message="User Already Exists",
                    status=False,
                    status_code=400,
                    response=None,
                )
        except User.DoesNotExist:
            print("Going to create a new User")
        user = User.objects.create(username=user_name, email=user_email)
        user.set_password(password)
        user.first_name = first_name if first_name else ""
        user.last_name = last_name if last_name else ""
        user.is_active = True
        user.save()
        return RESPONSE(
            message="User Created SuccessFully",
            status=True,
            status_code=201,
            response=user.email,
        )


class LoginView(APIView):
    def post(self, request):
        email = request.data.get("email", None)
        password = request.data.get("password", None)
        print(password)

        if not email:
            return RESPONSE(
                message="Please Provide An Email",
                status=False,
                status_code=404,
                response=None,
            )
        if not password:
            return RESPONSE(
                message="Please Provide A Password",
                status=False,
                status_code=404,
                response=None,
            )
        user = User.objects.filter(email=email).first()
        if not user:
            return RESPONSE(
                message="User Not Found",
                status=False,
                status_code=404,
                response=None,
            )
        if not user.check_password(password):
            return RESPONSE(
                message="Password Authentication Failed",
                status=False,
                status_code=400,
                response=None,
            )

        return RESPONSE(
            message="Please Provide A UserName",
            status=False,
            status_code=404,
            response=None,
        )


class GetExcellFileView(APIView):
    def post(self, request):
        excell_file = request.data.get("excell_file", None)
        social_media_name = request.data.get("socialmedia_name", None)
        is_same = request.data.get("is_same", False)
        user_id = request.data.get("user_id", None)
        if not excell_file or not excell_file.name.lower().endswith("xlsx"):
            return RESPONSE(
                message="No Excell File Provided",
                status=False,
                status_code=400,
                response=None,
            )
        if not user_id:
            return RESPONSE(
                message="No User ID Provided",
                status=False,
                status_code=400,
                response=None,
            )
        if not is_same and not social_media_name:
            return RESPONSE(
                message="Either set same for all to True or provide a social media name",
                status=False,
                status_code=400,
                response=None,
            )
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return RESPONSE(
                message="No Relevant User found please create one to continue",
                status=False,
                status_code=400,
                response=None,
            )
        mandatory_cols = ["type", "content", "url", "date_time"]
        csv_filename = f"{str(uuid.uuid4())}.csv"
        csv_path = os.path.join(settings.BASE_DIR, csv_filename)
        if (
            not is_same
            and social_media_name
            and social_media_name not in Platforms.values()
        ):
            return RESPONSE(
                message="Social Media Name is not valid",
                status=False,
                status_code=400,
                response=None,
            )
        if not is_same and social_media_name in Platforms.values():
            csv_dir = os.path.join(settings.BASE_DIR, social_media_name)
            os.makedirs(csv_dir, exist_ok=True)
            csv_path = os.path.join(settings.BASE_DIR, social_media_name, csv_filename)
        try:
            df = pd.read_excel(excell_file)
            if not all(col in df.columns for col in mandatory_cols):
                return RESPONSE(
                    message="These Cols are neccessary to be present",
                    status=False,
                    status_code=400,
                    response=None,
                )
            df = df[mandatory_cols]
            df.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"Error converting Excel to CSV: {e}")
            return None
        user_files, created = UserUploadedFiles.objects.get_or_create(user=user)
        if is_same:
            user_files.linkedin_file_path = csv_path
            user_files.x_file_path = csv_path
            user_files.tiktok_file_path = csv_path
            user_files.instagram_file_path = csv_path
            user_files.save()
        elif social_media_name == Platforms.LINKEDIN.value:
            user_files.linkedin_file_path = csv_path
            user_files.save()
        elif social_media_name == Platforms.X.value:
            user_files.x_file_path = csv_path
            user_files.save()
        elif social_media_name == Platforms.INSTAGRAM.value:
            user_files.instagram_file_path = csv_path
            user_files.save()
        else:
            user_files.tiktok_file_path = csv_path
            user_files.save()
        return RESPONSE(
            message="File Uploaded Successfully. Please make it suer you upload different file for tiktok",
            status=True,
            status_code=200,
            response=None,
        )


class VerifyLinkedInView(APIView):
    def post(self, request):
        code = request.data.get("code", None)
        state = request.data.get("state", None)
        user_id = request.data.get("user_id", None)
        if not code:
            return RESPONSE(
                message="No Code Provided",
                status=False,
                status_code=400,
                response=None,
            )
        if not user_id:
            return RESPONSE(
                message="No User Id Provided",
                status=False,
                status_code=400,
                response=None,
            )
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return RESPONSE(
                message="No User data found",
                status=False,
                status_code=400,
                response=None,
            )
        user_linkedin, created = Linkedin.objects.get_or_create(user=user)
        authorization_response = authorize_user_linkedin(code=code)
        if not authorization_response:
            return RESPONSE(
                message="Request responded without access token",
                status=False,
                status_code=400,
                response=None,
            )
        access_token = authorization_response.get("access_token")
        access_token_expiry_seconds = authorization_response.get("expires_in", 0)
        access_token_expiry_datetime = datetime.now() + timedelta(
            seconds=access_token_expiry_seconds
        )
        refresh_token = authorization_response.get("refresh_token")
        refresh_token_expiry_in_seconds = authorization_response.get(
            "refresh_token_expires_in", 0
        )
        refresh_token_expiry_in_days = refresh_token_expiry_in_seconds / (60 * 60 * 24)
        if created:
            user_info = get_user_linkedin_profile(access_token=access_token)
            if not user_info:
                return RESPONSE(
                    message="Failed to fetch user Unique number",
                    status=False,
                    status_code=400,
                    response=None,
                )
            urn = f"urn:li:person:{user_info.get('sub')}"
            user_linkedin.profile_id = urn
        user_linkedin.access_token = access_token
        user_linkedin.token_expires_on = access_token_expiry_datetime
        user_linkedin.refresh_token = refresh_token
        user_linkedin.refresh_token_expires_in = refresh_token_expiry_in_days
        user_linkedin.is_authenticated = (
            True
            if access_token_expiry_datetime >= datetime.now()
            and refresh_token_expiry_in_days > 3
            else False
        )
        user_linkedin.requires_auth = (
            False if refresh_token_expiry_in_days > 3 else True
        )
        user_linkedin.save()
        return RESPONSE(
            message="Profile Saved SuccessFully",
            status=False,
            status_code=400,
            response=None,
        )


class VerifyTikTokView(APIView):
    def post(self, request):
        code = request.data.get("code", None)
        state = request.data.get("state", None)
        user_id = request.data.get("user_id", None)
        if not code:
            return RESPONSE(
                message="No Code Provided",
                status=False,
                status_code=400,
                response=None,
            )
        if not user_id:
            return RESPONSE(
                message="No User Id Provided",
                status=False,
                status_code=400,
                response=None,
            )
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return RESPONSE(
                message="No User data found",
                status=False,
                status_code=400,
                response=None,
            )
        user_tiktok, created = TikTok.objects.get_or_create(user=user)
        authorization_response = authorize_user_tiktok(code=code)
        if not authorization_response:
            return RESPONSE(
                message="Request responded without access token",
                status=False,
                status_code=400,
                response=None,
            )
        access_token = authorization_response.get("access_token")
        access_token_expiry_seconds = authorization_response.get("expires_in", 0)
        access_token_expiry_datetime = datetime.now() + timedelta(
            seconds=access_token_expiry_seconds
        )
        refresh_token = authorization_response.get("refresh_token")
        refresh_token_expiry_in_seconds = authorization_response.get(
            "refresh_expires_in", 0
        )
        refresh_token_expiry_in_days = refresh_token_expiry_in_seconds / (60 * 60 * 24)
        user_tiktok.access_token = access_token
        user_tiktok.token_expires_on = access_token_expiry_datetime
        user_tiktok.refresh_token = refresh_token
        user_tiktok.refresh_token_expires_in = refresh_token_expiry_in_days
        user_tiktok.is_authenticated = (
            True
            if access_token_expiry_datetime >= datetime.now()
            and refresh_token_expiry_in_days > 3
            else False
        )
        user_tiktok.requires_auth = False if refresh_token_expiry_in_days > 3 else True
        user_tiktok.save()
        return RESPONSE(
            message="Profile Saved SuccessFully",
            status=False,
            status_code=400,
            response=None,
        )


class GetXAuthorizationURLView(APIView):
    def get(self, request):
        try:
            url = f"{settings.X_API_URL}oauth/request_token"
            callback = settings.X_REDIRECT_URL
            consumer_key = settings.X_CONSUMER_ID
            consumer_secret = settings.X_CONSUMER_SECRET

            oauth_data = {
                "oauth_callback": callback,
                "oauth_consumer_key": consumer_key,
                "oauth_nonce": uuid.uuid4().hex,
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": str(int(time.time())),
                "oauth_version": "1.0",
            }

            # Generate signature
            param_string = "&".join(
                f"{quote(k)}={quote(v)}" for k, v in sorted(oauth_data.items())
            )
            base_string = "&".join(
                [
                    "POST",
                    quote(url, safe=""),
                    quote(param_string, safe=""),
                ]
            )
            signing_key = f"{quote(consumer_secret)}&"
            signature = base64.b64encode(
                hmac.new(
                    signing_key.encode(), base_string.encode(), hashlib.sha1
                ).digest()
            ).decode()
            oauth_data["oauth_signature"] = signature

            # Build Authorization header
            auth_header = "OAuth " + ", ".join(
                f'{k}="{quote(v)}"' for k, v in oauth_data.items()
            )
            headers = {
                "Authorization": auth_header,
                "User-Agent": "MyApp",
            }

            res = requests.post(url, headers=headers)
            res.raise_for_status()
            data = dict(parse_qsl(res.text))
            request_token = data.get("oauth_token")
            request_token_secret = data.get("oauth_token_secret")
            if not request_token or not request_token_secret:
                return RESPONSE(
                    message="Failed to get request token",
                    status=False,
                    status_code=400,
                    response=None,
                )
            data["auth_url"] = (
                f"https://x.com/oauth/authorize?oauth_token={request_token}"
            )
            return RESPONSE(
                message="X Authorization Creds Retrieved Successfully",
                status=True,
                status_code=200,
                response=data,
            )

        except requests.RequestException as e:
            print(f"Error: {e}")
            return RESPONSE(
                message="Failed to get X Authorization Creds",
                status=False,
                status_code=500,
                response=None,
            )


class VerifyTwitterView(APIView):
    def percent_encode(self, s):
        return quote(str(s), safe="")

    def generate_oauth_signature(
        self, method, url, oauth_params, consumer_secret, token_secret=""
    ):
        sorted_params = sorted(
            (self.percent_encode(k), self.percent_encode(v))
            for k, v in oauth_params.items()
        )
        param_string = "&".join(f"{k}={v}" for k, v in sorted_params)

        base_string = "&".join(
            [
                method.upper(),
                self.percent_encode(url),
                self.percent_encode(param_string),
            ]
        )

        signing_key = f"{self.percent_encode(consumer_secret)}&{self.percent_encode(token_secret)}"

        hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
        return base64.b64encode(hashed.digest()).decode()

    def post(self, request):
        oauth_token = request.data.get("oauth_token")
        oauth_verifier = request.data.get("oauth_verifier")
        request_token = request.data.get("request_token")
        request_token_secret = request.data.get("request_token_secret")
        user_id = request.data.get("user_id", None)
        if not oauth_token or not oauth_verifier:
            return RESPONSE(
                message="Missing OAuth token or verifier",
                status=False,
                status_code=400,
                response=None,
            )
        if not request_token or not request_token_secret:
            return RESPONSE(
                message="Missing request token or secret",
                status=False,
                status_code=400,
                response=None,
            )
        if not user_id:
            return RESPONSE(
                message="No User Id Provided",
                status=False,
                status_code=400,
                response=None,
            )
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return RESPONSE(
                message="No User data found",
                status=False,
                status_code=400,
                response=None,
            )
        url = f"{settings.X_API_URL}oauth/access_token"
        method = "POST"
        oauth_params = {
            "oauth_consumer_key": settings.X_CONSUMER_ID,
            "oauth_token": request_token,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": "1.0",
        }
        signature = self.generate_oauth_signature(
            method, url, oauth_params, settings.X_CONSUMER_SECRET, request_token_secret
        )
        oauth_params["oauth_signature"] = signature
        auth_header = "OAuth " + ", ".join(
            [
                f'{self.percent_encode(k)}="{self.percent_encode(v)}"'
                for k, v in oauth_params.items()
                if k != "oauth_verifier"
            ]
        )
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "custom-oauth-client",
        }
        data = {"oauth_verifier": oauth_verifier}
        response = requests.post(url, headers=headers, data=data)

        if response.status_code != 200:
            return RESPONSE(
                message="Failed to get access token",
                status=False,
                status_code=response.status_code,
                response=None,
            )
        response_data = dict(parse_qsl(response.text))
        access_token = response_data.get("oauth_token")
        access_token_secret = response_data.get("oauth_token_secret")
        if not access_token or not access_token_secret:
            return RESPONSE(
                message="Failed to retrieve access token or secret",
                status=False,
                status_code=400,
                response=None,
            )
        auth = OAuth1(
            client_key=settings.X_CONSUMER_ID,
            client_secret=settings.X_CONSUMER_SECRET,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
        )
        fetch_profile = requests.get(
            f"{settings.X_API_URL}1.1/account/verify_credentials.json", auth=auth
        )
        if fetch_profile.status_code != 200:
            return RESPONSE(
                message="Failed to fetch user profile",
                status=False,
                status_code=fetch_profile.status_code,
                response=None,
            )
        user_info = fetch_profile.json()
        user_x, created = X.objects.get_or_create(user=user)
        if created:
            user_x.profile_id = user_info.get("id_str")
        user_x.access_token = access_token
        user_x.access_token_secret = access_token_secret
        user_x.is_authenticated = True
        user_x.requires_auth = False
        user_x.save()
        return RESPONSE(
            message="X Profile Saved Successfully",
            status=True,
            status_code=200,
            response=None,
        )


class RefreshAccessTokenView(APIView):
    def post(self, request): ...


class GetPostStatsView(APIView):
    def get(self, request): ...
