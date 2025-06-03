import requests
import digitalplatform.settings as settings
from .models import Linkedin, PostedContent
from datetime import datetime, timedelta
from .enums import PostStatus
import uuid
import os


def authorize_user_linkedin(code: str):
    if not code:
        return None
    url = f"{settings.LINKEDIN_BASE_URL}oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URL,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    get_access_and_refresh_tokens = requests.post(url, data=data, headers=headers)
    try:
        get_access_and_refresh_tokens.raise_for_status()
    except Exception as e:
        return None
    response_tokens = get_access_and_refresh_tokens.json()
    return response_tokens


def get_user_linkedin_profile(access_token: str):
    if not access_token:
        return None
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        user_info_response = requests.get(
            f"{settings.LINKEDIN_API_URL}v2/userinfo", headers=headers
        )
    except Exception as e:
        print(e)
        return None

    if user_info_response.status_code != 200:
        print(user_info_response)
        return None
    return user_info_response.json()


def refresh_linkedin_access_token(user_linkedin: Linkedin):
    url = f"{settings.LINKEDIN_BASE_URL}oauth/v2/accessToken"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": user_linkedin.refresh_token,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    get_access_and_refresh_tokens = requests.post(url, data=data, headers=headers)
    try:
        get_access_and_refresh_tokens.raise_for_status()
    except Exception as e:
        return None
    authorization_response = get_access_and_refresh_tokens.json()
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
    user_linkedin.requires_auth = False if refresh_token_expiry_in_days > 3 else True
    user_linkedin.save()


def create_linkedin_content_post(
    user_linkedin: Linkedin, post_content, posted_content: PostedContent
):
    try:
        if (
            not user_linkedin.access_token
            or not user_linkedin.profile_id
            or not post_content
        ):
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = (
                "User not authenticated or LinkedIn profile not found"
            )

            posted_content.save()
            return
        posted_content.post_status = PostStatus.PROCESSED.value
        posted_content.save()
        post_url = f"{settings.LINKEDIN_API_URL}v2/ugcPosts"
        post_headers = {
            "Authorization": f"Bearer {user_linkedin.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        post_body = {
            "author": user_linkedin.profile_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        post_response = requests.post(post_url, headers=post_headers, json=post_body)

        if post_response.status_code in [200, 201]:
            posted_content.post_status = PostStatus.POSTED.value
            posted_content.is_posted = True
            posted_content.save()
            return
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = ""
        posted_content.save()
        return
    except Exception as e:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            f"An error occurred while posting to LinkedIn: {e}"
        )
        posted_content.save()
        return


def create_linkedin_image_post(
    user_linkedin: Linkedin, post_content: str, posted_content: PostedContent, url: str
):
    try:
        if (
            not user_linkedin.access_token
            or not user_linkedin.profile_id
            or not url
            or not user_linkedin.is_authenticated
        ):
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = (
                "User not authenticated or LinkedIn profile not found"
            )
            posted_content.save()
            return
        access_token = user_linkedin.access_token
        image_file = requests.get(url)
        image_filename = f"{uuid.uuid4()}.jpg"
        save_dir = os.path.join(settings.BASE_DIR, "LinkedIn_images")
        os.makedirs(save_dir, exist_ok=True)
        image_path = os.path.join(save_dir, image_filename)

        with open(image_path, "wb+") as destination:
            for chunk in image_file.iter_content():
                destination.write(chunk)

        register_upload_url = (
            f"{settings.LINKEDIN_API_URL}v2/assets?action=registerUpload"
        )
        register_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        register_body = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": user_linkedin.profile_id,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        register_response = requests.post(
            register_upload_url, headers=register_headers, json=register_body
        )
        if register_response.status_code not in [200, 201]:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Failed to register upload"
            posted_content.save()
            return

        register_data = register_response.json()
        upload_url = register_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = register_data["value"]["asset"]
        if not upload_url or not asset:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Invalid upload URL or asset"
            posted_content.save()
            return

        with open(image_path, "rb") as img_file:
            upload_headers = {
                "Authorization": f"Bearer {access_token}",
            }
            upload_response = requests.put(
                upload_url, headers=upload_headers, data=img_file
            )

        if upload_response.status_code not in [200, 201]:
            posted_content.post_status = PostStatus.ERROR.value
            posted_content.error_reason = "Failed to upload image"
            posted_content.save()
            return

        posted_content.post_status = PostStatus.PROCESSED.value
        posted_content.save()

        post_url = f"{settings.LINKEDIN_API_URL}v2/ugcPosts"
        post_headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        post_body = {
            "author": user_linkedin.profile_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_content},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": "Image post"},
                            "media": asset,
                            "title": {"text": "LinkedIn Image Post"},
                        }
                    ],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        final_post_response = requests.post(
            post_url, headers=post_headers, json=post_body
        )
        if final_post_response.status_code in [200, 201]:
            posted_content.post_status = PostStatus.POSTED.value
            posted_content.is_posted = True
            posted_content.save()
            return
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = "Failed to create LinkedIn post"
        posted_content.save()
        return
    except Exception as e:
        posted_content.post_status = PostStatus.ERROR.value
        posted_content.error_reason = (
            f"An error occurred while posting to LinkedIn: {e}"
        )
        posted_content.save()
        return

    finally:
        if os.path.isfile(image_path):
            os.remove(image_path)
