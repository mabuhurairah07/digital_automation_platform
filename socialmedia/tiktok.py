import requests
import digitalplatform.settings as settings
from .models import TikTok, PostedContent
from datetime import datetime, timedelta
import uuid
import pandas as pd
from .enums import PostStatus, PostType
import math
import os


def download_video_from_url(video_url):
    try:
        base_dir = settings.BASE_DIR

        save_dir = os.path.join(base_dir, "videos")
        os.makedirs(save_dir, exist_ok=True)

        response = requests.get(video_url, stream=True)
        if response.status_code != 200:
            raise Exception(
                f"Failed to download video, status code: {response.status_code}"
            )

        filename = str(uuid.uuid4()) + ".mp4"
        save_path = os.path.join(save_dir, filename)

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return save_path
    except Exception as e:
        return None


def authorize_user_tiktok(code: str):
    if not code:
        return None
    url = f"{settings.TIKTOK_API_URL}oauth/token/"
    data = {
        "client_key": settings.TIKTOK_CLIENT_ID,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URL,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    get_access_and_refresh_tokens = requests.post(url, data=data, headers=headers)
    try:
        get_access_and_refresh_tokens.raise_for_status()
    except Exception as e:
        print(e)
        return None
    return get_access_and_refresh_tokens.json()


def refresh_tiktok_access_token(user_tiktok: TikTok):
    url = f"{settings.TIKTOK_API_URL}oauth/token/"
    data = {
        "client_key": settings.TIKTOK_CLIENT_ID,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "refresh_token": user_tiktok.refresh_token,
        "grant_type": "refresh_token",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    get_access_and_refresh_tokens = requests.post(url, data=data, headers=headers)
    try:
        get_access_and_refresh_tokens.raise_for_status()
    except Exception as e:
        print(e)
        return None
    authorization_response = get_access_and_refresh_tokens.json()
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


def post_video_on_tiktok(
    user_tiktok: TikTok, video_url: str, posted_content: PostedContent, content: str
):
    if not user_tiktok or not user_tiktok.is_authenticated:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            "User not authenticated or TikTok profile not found"
        )
        posted_content.save()
        return
    access_token = user_tiktok.access_token
    if not access_token:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = "Access token not found"
        posted_content.save()
        return
    video_path = download_video_from_url(video_url=video_url)
    if not video_path:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = "Failed to download video from URL"
        posted_content.save()
        return
    posted_content.post_status = PostStatus.STARTED.value
    posted_content.save()

    video_size = os.path.getsize(video_path)
    min_chunk = 5 * 1024 * 1024
    max_chunk = 64 * 1024 * 1024
    max_final_chunk = 128 * 1024 * 1024
    max_chunks = 1000

    if video_size < min_chunk or video_size <= max_chunk:
        chunk_size = video_size
        total_chunk_count = 1
    else:
        chunk_size = min(max_chunk, math.ceil(video_size / max_chunks))
        total_chunk_count = math.floor(video_size / chunk_size)
        if video_size % chunk_size != 0:
            total_chunk_count += 1

    url = f"{settings.TIKTOK_API_URL}post/publish/creator_info/query/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    try:
        response = requests.post(url, headers=headers)
        if response.status_code not in [200, 201]:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Failed to fetch creator info"
            posted_content.save()
            return

        creator_data = response.json().get("data")
        if not creator_data:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Creator data not found"
            posted_content.save()
            return

        privacy_options = creator_data.get("privacy_level_options", ["SELF_ONLY"])
        comment_disabled = creator_data.get("comment_disabled", False)
        duet_disabled = creator_data.get("duet_disabled", False)
        stitch_disabled = creator_data.get("stitch_disabled", True)

        upload_video_url = f"{settings.TIKTOK_API_URL}post/publish/video/init/"
        post_video_headers = headers.copy()
        post_video_data = {
            "post_info": {
                "title": content if content else "#fypost",
                "privacy_level": "SELF_ONLY",
                "disable_duet": duet_disabled,
                "disable_comment": comment_disabled,
                "disable_stitch": stitch_disabled,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        }
        post_video_response = requests.post(
            upload_video_url, headers=post_video_headers, json=post_video_data
        )
        if post_video_response.status_code not in [200, 201]:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Failed to initiate video upload"
            posted_content.save()
            return
        posted_content.post_status = PostStatus.PROCESSED.value
        posted_content.save()
        post_video_response_data = post_video_response.json().get("data")
        if not post_video_response_data:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Failed to get video upload URL"
            posted_content.save()
            return

        url_for_video_upload = post_video_response_data.get("upload_url")
        with open(video_path, "rb") as f:
            for i in range(total_chunk_count):
                start_byte = i * chunk_size
                end_byte = min((i + 1) * chunk_size - 1, video_size - 1)
                f.seek(start_byte)
                chunk_data = f.read(end_byte - start_byte + 1)
                upload_video_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk_data)),
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
                }
                response_of_chunk_upload = requests.put(
                    url_for_video_upload,
                    headers=upload_video_headers,
                    data=chunk_data,
                    timeout=(10, 480),
                )
                if response_of_chunk_upload.status_code not in [200, 201]:
                    print(
                        f"Failed to upload chunk {i + 1}/{total_chunk_count}, status code: {response_of_chunk_upload.status_code}"
                    )
                    posted_content.post_status = PostStatus.ERROR.value
                    posted_content.error_reason = f"Failed to post video chunk {i + 1}/{total_chunk_count}, posting response: {response_of_chunk_upload.text}"
                    posted_content.save()
                    return

        posted_content.post_status = PostStatus.POSTED.value
        posted_content.is_posted = True
        posted_content.save()
        return
    except Exception as e:
        print(f"Error while uploading video to TikTok: {e}")
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = f"Error while uploading video to TikTok: {e}"
        posted_content.save()
    finally:
        if os.path.isfile(video_path):
            os.remove(video_path)
