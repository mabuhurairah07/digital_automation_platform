from django.shortcuts import render
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import UserUploadedFiles
from .enums import Platforms
from .utils import RESPONSE
import pandas as pd
import digitalplatform.settings as settings
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


class GetExcellFile(APIView):
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
            message="File Uploaded Successfully",
            status=True,
            status_code=200,
            response=None,
        )
