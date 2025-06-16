from celery import shared_task
from celery.utils.log import get_task_logger
from .models import Linkedin, PostedContent, X, TikTok, UserUploadedFiles
from datetime import datetime, timedelta
from django.utils import timezone
from . import linkedin as LIN, tiktok as TT, x as XT
from threading import Thread
import pandas as pd
import pytz
from .enums import PostStatus, PostType, Platforms

logger = get_task_logger(__name__)


@shared_task
def refresh_linkedin_tokens():
    from .linkedin import refresh_linkedin_access_token

    linkedin_accounts = Linkedin.objects.filter(is_authenticated=True)
    if not linkedin_accounts:
        logger.info("No authenticated LinkedIn accounts found.")
        return
    for linkedin in linkedin_accounts:
        if linkedin.token_expires_on <= (timezone.now() + timedelta(1)):
            try:
                refresh_linkedin_access_token(linkedin)
                logger.info(
                    f"Refreshed LinkedIn token for user {linkedin.user.username}."
                )
            except Exception as e:
                logger.error(
                    f"Error refreshing LinkedIn token for user {linkedin.user.username}: {str(e)}"
                )
        else:
            logger.warning(
                f"LinkedIn account for user {linkedin.user.username} does not require refresh or has no refresh token."
            )


@shared_task
def refresh_tiktok_tokens():
    from .tiktok import refresh_tiktok_access_token

    tiktok_accounts = TikTok.objects.filter(is_authenticated=True)
    if not tiktok_accounts:
        logger.info("No authenticated TikTok accounts found.")
        return
    for tiktok in tiktok_accounts:
        if tiktok.token_expires_on <= (timezone.now() + timedelta(hours=6)):
            try:
                refresh_tiktok_access_token(tiktok)
                logger.info(f"Refreshed TikTok token for user {tiktok.user.username}.")
            except Exception as e:
                logger.error(
                    f"Error refreshing TikTok token for user {tiktok.user.username}: {str(e)}"
                )
        else:
            logger.warning(
                f"TikTok account for user {tiktok.user.username} does not require refresh or has no refresh token."
            )


@shared_task
def start_social_media_posting():
    time_rnow = timezone.now()
    start_window = time_rnow + timedelta(hours=3)
    end_window = start_window + timedelta(hours=1)
    start_window = start_window.astimezone(pytz.UTC)
    end_window = end_window.astimezone(pytz.UTC)
    logger.info(
        f"Starting social media posting task. Current time: {time_rnow}, Start window: {start_window}, End window: {end_window}"
    )
    users_files = UserUploadedFiles.objects.all()
    if not users_files:
        logger.info("No user files found for posting.")
        return
    for user_file in users_files:
        has_linkedin = False
        has_tiktok = False
        has_x = False
        user = user_file.user
        linkedin_file_path = user_file.linkedin_file_path
        tiktok_file_path = user_file.tiktok_file_path
        x_file_path = user_file.x_file_path
        instagram_file_path = user_file.instagram_file_path
        if (
            linkedin_file_path == tiktok_file_path == x_file_path == instagram_file_path
            and not linkedin_file_path
        ):
            logger.info(f"No files uploaded for user {user.username}.")
            continue
        linkedin = Linkedin.objects.filter(user=user, is_authenticated=True).first()
        if linkedin:
            has_linkedin = True
        tiktok = TikTok.objects.filter(user=user, is_authenticated=True).first()
        if tiktok:
            has_tiktok = True
        x = X.objects.filter(user=user, is_authenticated=True).first()
        if x:
            has_x = True
        if not has_linkedin and not has_tiktok and not has_x:
            logger.info(
                f"No authenticated social media accounts found for user {user.username}."
            )
            continue
        if linkedin_file_path and has_linkedin:
            try:
                df = pd.read_csv(linkedin_file_path, quotechar='"')
                df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_localize("UTC")
                future_posts = df[
                    (df["date_time"] >= start_window) & (df["date_time"] <= end_window)
                ]
                print(future_posts)
                if future_posts.empty:
                    logger.info(
                        f"No future posts found in LinkedIn file for user {user.username}."
                    )
                for _, row in future_posts.iterrows():
                    post_id = row.get("id", "")
                    post_content = row.get("content", "")
                    post_type = row.get("type", "")
                    post_url = row.get("url", "")
                    posting_datetime = row.get("date_time", "")
                    print(posting_datetime)
                    if not post_content or not post_type or not posting_datetime:
                        logger.warning(
                            f"Missing required fields in LinkedIn file for user {user.username}."
                        )
                        continue
                    if post_type == PostType.TEXT.value:
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.TEXT.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.LINKEDIN.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(
                            f"Scheduled LinkedIn text post for user {user.username}."
                        )
                        Thread(
                            target=LIN.create_linkedin_content_post,
                            args=(linkedin, post_content, posted_content),
                        ).start()
                    elif post_type == PostType.IMAGE.value:
                        if not post_url:
                            logger.warning(
                                f"Missing image URL in LinkedIn file for user {user.username}."
                            )
                            continue
                        if not post_id:
                            logger.warning(
                                f"Missing post ID in LinkedIn file for user {user.username}."
                            )
                            post_id = _
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.IMAGE.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.LINKEDIN.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(
                            f"Scheduled LinkedIn image post for user {user.username}."
                        )
                        Thread(
                            target=LIN.create_linkedin_image_post,
                            args=(linkedin, post_content, posted_content, post_url),
                        ).start()
                    elif post_type == PostType.VIDEO.value:
                        logger.info(
                            f"LinkedIn does not support video posts For now. Skipping for user {user.username}."
                        )
                        continue
            except Exception as e:
                logger.error(
                    f"Error processing LinkedIn file for user {user.username}: {str(e)}"
                )
        if tiktok_file_path and has_tiktok:
            try:
                df = pd.read_csv(tiktok_file_path, quotechar='"')
                df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_localize("UTC")
                future_posts = df[
                    (df["date_time"] >= start_window) & (df["date_time"] <= end_window)
                ]
                print(future_posts)
                if future_posts.empty:
                    logger.info(
                        f"No future posts found in Tiktok file for user {user.username}."
                    )
                for _, row in future_posts.iterrows():
                    post_id = row.get("id", "")
                    post_content = row.get("content", "")
                    post_type = row.get("type", "")
                    post_url = row.get("url", "")
                    posting_datetime = row.get("date_time", "")
                    if not post_content or not post_type or not posting_datetime:
                        logger.warning(
                            f"Missing required fields in TikTok file for user {user.username}."
                        )
                        continue
                    if not post_url:
                        logger.warning(
                            f"Missing video URL in TikTok file for user {user.username}."
                        )
                        continue
                    if not post_id:
                        logger.warning(
                            f"Missing post ID in TikTok file for user {user.username}."
                        )
                        post_id = _
                    if post_type == PostType.VIDEO.value:
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.VIDEO.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.TIKTOK.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(
                            f"Scheduled TikTok video post for user {user.username}."
                        )
                        Thread(
                            target=TT.post_video_on_tiktok,
                            args=(tiktok, post_url, posted_content, post_content),
                        ).start()
                    else:
                        logger.info(
                            f"TikTok only supports video posts for Now. Skipping for user {user.username}."
                        )
                        continue
            except Exception as e:
                logger.error(
                    f"Error processing TikTok file for user {user.username}: {str(e)}"
                )
        if x_file_path and has_x:
            try:
                df = pd.read_csv(x_file_path, quotechar='"')
                df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_localize("UTC")
                future_posts = df[
                    (df["date_time"] >= start_window) & (df["date_time"] <= end_window)
                ]
                print(future_posts)
                if future_posts.empty:
                    logger.info(
                        f"No future posts found in Twitter file for user {user.username}."
                    )
                for _, row in future_posts.iterrows():
                    post_id = row.get("id", "")
                    post_content = row.get("content", "")
                    post_type = row.get("type", "")
                    post_url = row.get("url", "")
                    posting_datetime = row.get("date_time", "")
                    if not post_content or not post_type or not posting_datetime:
                        logger.warning(
                            f"Missing required fields in LinkedIn file for user {user.username}."
                        )
                        continue
                    if post_type == PostType.TEXT.value:
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.TEXT.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.X.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(f"Scheduled X text post for user {user.username}.")
                        Thread(
                            target=XT.create_x_content_tweet,
                            args=(post_content, x, posted_content),
                        ).start()
                    elif post_type == PostType.IMAGE.value:
                        if not post_url:
                            logger.warning(
                                f"Missing image URL in X file for user {user.username}."
                            )
                            continue
                        if not post_id:
                            logger.warning(
                                f"Missing post ID in X file for user {user.username}."
                            )
                            post_id = _
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.IMAGE.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.X.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(f"Scheduled X image post for user {user.username}.")
                        Thread(
                            target=XT.create_x_image_or_video_tweet,
                            args=(post_content, post_url, x, posted_content),
                        ).start()
                    elif post_type == PostType.VIDEO.value:
                        if not post_url:
                            logger.warning(
                                f"Missing video URL in X file for user {user.username}."
                            )
                            continue
                        if not post_id:
                            logger.warning(
                                f"Missing post ID in X file for user {user.username}."
                            )
                            post_id = _
                        posted_content = PostedContent.objects.create(
                            user=user,
                            post_type=PostType.VIDEO.value,
                            post_status=PostStatus.STARTED.value,
                            platform_name=Platforms.X.value,
                            post_id=post_id,
                            is_posted=False,
                            error_reason=None,
                        )
                        logger.info(f"Scheduled X video post for user {user.username}.")
                        Thread(
                            target=XT.create_x_image_or_video_tweet,
                            args=(post_content, post_url, x, posted_content),
                        ).start()
            except Exception as e:
                logger.error(
                    f"Error processing X file for user {user.username}: {str(e)}"
                )
