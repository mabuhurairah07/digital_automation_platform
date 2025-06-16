from requests_oauthlib import OAuth1
import requests
import digitalplatform.settings as settings
from .models import X, PostedContent
from datetime import datetime, timedelta
from .enums import PostStatus
import uuid
import mimetypes
import time
import os


def upload_media_to_x(url: str, x: X):
    if not x.is_authenticated or not x.access_token or not x.access_token_secret:
        return None
    access_token = x.access_token
    access_token_secret = x.access_token_secret
    auth = OAuth1(
        client_key=settings.X_CONSUMER_ID,
        client_secret=settings.X_CONSUMER_SECRET,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )
    get_file = requests.get(url)
    if get_file.status_code != 200:
        print(f"Failed to download media file: {get_file.text}")
        return None
    filename = str(uuid.uuid4())
    if url.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
        filename += ".mp4"
    else:
        filename += ".jpg"
    dir_path = os.path.join(settings.BASE_DIR, "x")
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, "wb") as media_file:
        media_file.write(get_file.content)
    upload_url = f"{settings.X_UPLOAD_URL}1.1/media/upload.json"
    if filename.endswith(".mp4"):
        initialzing_payload = {
            "command": "INIT",
            "total_bytes": os.path.getsize(file_path),
            "media_type": mimetypes.guess_type(file_path),
            "media_category": "tweet_video",
        }
        init_resp = requests.post(upload_url, auth=auth, data=initialzing_payload)
        if init_resp.status_code not in (201, 202):
            print(f"INIT failed: {init_resp.text}")
            return None
        media_id = init_resp.json().get("media_id")
        if not media_id:
            print("Failed to get media_id from INIT response.")
            return None
        with open(file_path, "rb") as media_file:
            try:
                media_file.seek(0)
                segment_id = 0
                chunk_size = 4 * 1024 * 1024
                while True:
                    chunk = media_file.read(chunk_size)
                    if not chunk:
                        break
                    append_data = {
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": segment_id,
                    }
                    files = {"media": chunk}
                    for retry in range(3):
                        append_resp = requests.post(
                            upload_url,
                            auth=auth,
                            data=append_data,
                            files=files,
                            timeout=60,
                        )
                        if append_resp.status_code == 204:
                            break
                        time.sleep(2**retry)
                    segment_id += 1
            except Exception as e:
                print(f"Error initializing video upload: {str(e)}")
                return None
            finally:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            finalize_data = {"command": "FINALIZE", "media_id": media_id}
            finalize_resp = requests.post(upload_url, auth=auth, data=finalize_data)
            if finalize_resp.status_code not in (200, 201):
                print(f"FINALIZE failed: {finalize_resp.text}")
                return None
            proc_info = finalize_resp.json().get("processing_info")
            if proc_info:
                state = proc_info.get("state")
                while state in ["pending", "in_progress"]:
                    check_after = proc_info.get("check_after_secs", 5)
                    time.sleep(check_after)
                    status_params = {"command": "STATUS", "media_id": media_id}
                    status_resp = requests.get(
                        upload_url, auth=auth, params=status_params, timeout=30
                    )
                    if status_resp.status_code != 200:
                        print(f"STATUS check failed: {status_resp.text}")
                        return None
                    proc_info = status_resp.json().get("processing_info")
                    state = proc_info.get("state")
                    if state == "failed":
                        error_msg = proc_info.get("error", {}).get(
                            "message", "Unknown processing error"
                        )
                        print(f"Processing failed: {error_msg}")
                        return None
        return str(media_id) if media_id and not isinstance(media_id, str) else media_id
    else:
        with open(file_path, "rb") as media_file:
            mime_type, _ = mimetypes.guess_type(file_path)
            try:
                files = {
                    "media": (
                        media_file.name,
                        media_file.read(),
                        mime_type or "application/octet-stream",
                    )
                }
                data = {"media_category": "tweet_image"}
                response = requests.post(upload_url, auth=auth, files=files, data=data)
                if response.status_code == 200:
                    media_id = response.json().get("media_id")
                    if media_id and not isinstance(media_id, str):
                        media_id = str(media_id)
                    return media_id if media_id else None
                print(f"Simple image upload failed: {response.text}")
                return None
            except Exception as e:
                print(f"Simple image upload exception: {str(e)}")
                return None
            finally:
                if os.path.isfile(file_path):
                    os.remove(file_path)


def create_x_content_tweet(content: str, x: X, posted_content: PostedContent):
    try:
        if not x.is_authenticated or not x.access_token or not x.access_token_secret:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = (
                "X account is not authenticated or missing access tokens."
            )
            posted_content.save()
            return
        if not content:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Content cannot be empty."
            posted_content.save()
            return
        posted_content.post_status = PostStatus.PROCESSED.value
        posted_content.save()
        access_token = x.access_token
        access_token_secret = x.access_token_secret
        auth = OAuth1(
            client_key=settings.X_CONSUMER_ID,
            client_secret=settings.X_CONSUMER_SECRET,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
        )
        payload = {"text": content}
        post_content = requests.post(
            f"{settings.TWITTER_BASED_API_URL}2/tweets",
            json=payload,
            auth=auth,
        )
        if post_content.status_code in [200, 201]:
            posted_content.post_status = PostStatus.POSTED.value
            posted_content.is_posted = True
            posted_content.save()
            return
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            f"Failed to post content.Response: {post_content.text}"
        )
        posted_content.save()
        return
    except Exception as e:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            f"An error occurred while posting content: {str(e)}"
        )
        posted_content.save()
        return


def create_x_image_or_video_tweet(
    content: str, url: str, x: X, posted_content: PostedContent
):
    if not x.is_authenticated or not x.access_token or not x.access_token_secret:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            "X account is not authenticated or missing access tokens."
        )
        posted_content.save()
        return
    if not content or not url:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = "Content and URL cannot be empty."
        posted_content.save()
        return
    access_token = x.access_token
    access_token_secret = x.access_token_secret
    auth = OAuth1(
        client_key=settings.X_CONSUMER_ID,
        client_secret=settings.X_CONSUMER_SECRET,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )
    payload = {"text": content}
    media_id = upload_media_to_x(url, x)
    if not media_id:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = "Failed to upload media. No Media Id Returned"
        posted_content.save()
        return
    posted_content.post_status = PostStatus.PROCESSED.value
    posted_content.save()
    payload["media"] = {"media_ids": [str(media_id)]}
    post_content = requests.post(
        f"{settings.TWITTER_BASED_API_URL}2/tweets",
        json=payload,
        auth=auth,
    )
    if post_content.status_code in [200, 201]:
        posted_content.post_status = PostStatus.POSTED.value
        posted_content.is_posted = True
        posted_content.save()
        return
    posted_content.post_status = PostStatus.ERROR.value
    posted_content.error_reason = (
        f"Failed to post content.Response: {post_content.text}"
    )
    posted_content.save()
    return
