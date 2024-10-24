from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator
from django.db.models import F, Q, Prefetch
from django.core.files.storage import default_storage
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.db import transaction
from .models import Post, Comment, PostView, Report, PostLike
from .forms import PostForm, CommentForm
import logging

logger = logging.getLogger(__name__)

POSTS_PER_PAGE = 20
CACHE_TTL = 300  # 5 minutes


def get_client_ip(request):
    """
    Extract the client IP address from the request.

    Args:
        request: HttpRequest object

    Returns:
        str: Client IP address from X-Forwarded-For header or REMOTE_ADDR
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return (
        x_forwarded_for.split(",")[0]
        if x_forwarded_for
        else request.META.get("REMOTE_ADDR")
    )


@cache_page(CACHE_TTL)
def home(request):
    """
    Landing page view that serves trending posts.

    Args:
        request: HttpRequest object

    Returns:
        HttpResponse: Rendered home template with trending posts
    """
    trending_posts = cache.get_or_set(
        "trending_posts",
        Post.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=1)
        ).order_by("-views_count")[:5],
        CACHE_TTL,
    )
    return render(request, "social/home.html", {"trending_posts": trending_posts})


@login_required
def feed(request):
    """
    Main feed view with pagination and filtering options.

    Args:
        request: HttpRequest object

    Returns:
        JsonResponse: JSON containing paginated posts and filter information
    """
    page = request.GET.get("page", 1)
    filter_by = request.GET.get("filter", "all")

    posts = (
        Post.objects.select_related("user")
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("user").order_by("-created_at")[
                    :3
                ],
            ),
            "likes",
        )
        .filter(status="published")
    )

    if filter_by == "following":
        posts = posts.filter(user__in=request.user.following.all())
    elif filter_by == "trending":
        posts = posts.order_by("-views_count", "-likes_count", "-created_at")
    else:
        posts = posts.order_by("-created_at")

    paginator = Paginator(posts, POSTS_PER_PAGE)
    page_obj = paginator.get_page(page)

    posts_data = [
        {
            "id": post.id,
            "content": post.content,
            "user": {"id": post.user.id, "username": post.user.username},
            "created_at": post.created_at.isoformat(),
            "likes_count": post.likes_count,
            "comments_count": post.comments.count(),
            "views_count": post.views_count,
            "image_url": post.image.url if post.image else None,
            "video_url": post.video.url if post.video else None,
        }
        for post in page_obj
    ]

    return JsonResponse(
        {
            "status": "success",
            "posts": posts_data,
            "has_next": page_obj.has_next(),
            "current_page": page_obj.number,
            "total_pages": paginator.num_pages,
            "filter_by": filter_by,
        }
    )


@login_required
@require_POST
@transaction.atomic
def like_post(request, post_id):
    """
    Toggle like status for a post.

    Args:
        request: HttpRequest object
        post_id (int): ID of the post to like/unlike

    Returns:
        JsonResponse: Updated like status and count
    """
    try:
        post = Post.objects.select_for_update().get(id=post_id)

        if PostLike.objects.filter(user=request.user, post=post).exists():
            PostLike.objects.filter(user=request.user, post=post).delete()
            post.likes_count = F("likes_count") - 1
            liked = False
        else:
            PostLike.objects.create(user=request.user, post=post)
            post.likes_count = F("likes_count") + 1
            liked = True

        post.save()
        post.refresh_from_db()

        return JsonResponse(
            {"status": "success", "liked": liked, "likes_count": post.likes_count}
        )
    except Post.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Post not found"}, status=404
        )
    except Exception as e:
        logger.error(f"Error in like_post: {str(e)}")
        return JsonResponse({"status": "error", "message": "Server error"}, status=500)


@login_required
@require_POST
def add_comment(request, post_id):
    """
    Add a comment to a post.

    Args:
        request: HttpRequest object
        post_id (int): ID of the post to comment on

    Returns:
        JsonResponse: New comment data or validation errors
    """
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                comment = form.save(commit=False)
                comment.post_id = post_id
                comment.user = request.user
                comment.save()

                return JsonResponse(
                    {
                        "status": "success",
                        "comment": {
                            "id": comment.id,
                            "content": comment.content,
                            "user": {
                                "id": comment.user.id,
                                "username": comment.user.username,
                            },
                            "created_at": comment.created_at.isoformat(),
                            "likes_count": 0,
                        },
                    }
                )
        except Exception as e:
            logger.error(f"Error in add_comment: {str(e)}")
            return JsonResponse(
                {"status": "error", "message": "Server error"}, status=500
            )

    return JsonResponse({"status": "error", "errors": form.errors}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def create_post(request):
    """
    Create a new post with optional media attachments.

    Args:
        request: HttpRequest object

    Returns:
        JsonResponse: Created post data or validation errors
    """
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    post = form.save(commit=False)
                    post.user = request.user
                    post.save()
                    return JsonResponse(
                        {
                            "status": "success",
                            "post": {
                                "id": post.id,
                                "content": post.content,
                                "user": {
                                    "id": post.user.id,
                                    "username": post.user.username,
                                },
                                "created_at": post.created_at.isoformat(),
                                "image_url": post.image.url if post.image else None,
                                "video_url": post.video.url if post.video else None,
                            },
                        }
                    )
            except Exception as e:
                logger.error(f"Error in create_post: {str(e)}")
                return JsonResponse(
                    {"status": "error", "message": "Error creating post"}, status=500
                )
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)

    return render(request, "social/post_create.html", {"form": PostForm()})


@login_required
@require_POST
def increment_view_count(request, post_id):
    """Track post views with rate limiting"""
    cache_key = f"post_view_{post_id}_{request.user.id}_{timezone.now().date()}"

    if not cache.get(cache_key):
        try:
            with transaction.atomic():
                post = Post.objects.select_for_update().get(id=post_id)
                PostView.objects.create(
                    post=post,
                    user=request.user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:200],
                )
                post.views_count = F("views_count") + 1
                post.save()

                cache.set(cache_key, True, timeout=86400)  # 24 hours

                return JsonResponse(
                    {"status": "success", "views_count": post.views_count}
                )
        except Exception as e:
            logger.error(f"Error in increment_view_count: {str(e)}")
            return JsonResponse(
                {"status": "error", "message": "Server error"}, status=500
            )

    return JsonResponse({"status": "success", "message": "View already counted"})


@login_required
def post_detail(request, post_id):
    """
    Get detailed information about a specific post.

    Args:
        request: HttpRequest object
        post_id (int): ID of the post to retrieve

    Returns:
        JsonResponse: Detailed post data including comments and engagement metrics
    """
    try:
        post = get_object_or_404(
            Post.objects.select_related("user").prefetch_related(
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("user")
                    .prefetch_related("replies")
                    .order_by("-created_at"),
                ),
                "likes",
            ),
            id=post_id,
        )

        if post.status != "published" and post.user != request.user:
            return JsonResponse(
                {"status": "error", "message": "Permission denied"}, status=403
            )

        transaction.on_commit(
            lambda: increment_view_count.delay(post.id, request.user.id)
        )

        return JsonResponse(
            {
                "status": "success",
                "post": {
                    "id": post.id,
                    "content": post.content,
                    "user": {"id": post.user.id, "username": post.user.username},
                    "created_at": post.created_at.isoformat(),
                    "image_url": post.image.url if post.image else None,
                    "video_url": post.video.url if post.video else None,
                    "likes_count": post.likes_count,
                    "views_count": post.views_count,
                    "comments": [
                        {
                            "id": comment.id,
                            "content": comment.content,
                            "user": {
                                "id": comment.user.id,
                                "username": comment.user.username,
                            },
                            "created_at": comment.created_at.isoformat(),
                            "likes_count": comment.likes_count,
                        }
                        for comment in post.comments.filter(parent=None)
                    ],
                    "is_liked": request.user in post.likes.all(),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error in post_detail: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Error retrieving post"}, status=500
        )


@login_required
@require_POST
@transaction.atomic
def delete_post(request, post_id):
    """
    Delete a post and its associated media files.

    Args:
        request: HttpRequest object
        post_id (int): ID of the post to delete

    Returns:
        JsonResponse: Success or error status
    """
    try:
        post = get_object_or_404(Post, id=post_id)

        if post.user != request.user and not request.user.is_staff:
            return JsonResponse(
                {"status": "error", "message": "Permission denied"}, status=403
            )

        image_path = post.image.path if post.image else None
        video_path = post.video.path if post.video else None

        post.delete()

        if image_path:
            default_storage.delete(image_path)
        if video_path:
            default_storage.delete(video_path)

        return JsonResponse({"status": "success"})
    except Exception as e:
        logger.error(f"Error in delete_post: {str(e)}")
        return JsonResponse(
            {"status": "error", "message": "Error deleting post"}, status=500
        )


@login_required
def post_engagement(request, post_id, engagement_type):
    """
    Get detailed engagement information for a post.

    Args:
        request: HttpRequest object
        post_id (int): ID of the post
        engagement_type (str): Type of engagement to retrieve (likes/comments/views)

    Returns:
        JsonResponse: Paginated engagement data
    """
    post = get_object_or_404(Post, id=post_id)

    if post.user != request.user and not request.user.is_staff:
        return JsonResponse(
            {"status": "error", "message": "Permission denied"}, status=403
        )

    page = request.GET.get("page", 1)
    items_per_page = 50

    if engagement_type == "likes":
        queryset = post.likes.select_related("profile").order_by(
            "-postlike__created_at"
        )
    elif engagement_type == "comments":
        queryset = post.comments.select_related("user").order_by("-created_at")
    elif engagement_type == "views":
        queryset = post.views.select_related("user").order_by("-viewed_at")
    else:
        return JsonResponse(
            {"status": "error", "message": "Invalid engagement type"}, status=400
        )

    paginator = Paginator(queryset, items_per_page)
    page_obj = paginator.get_page(page)

    data = []
    for item in page_obj:
        if engagement_type == "likes":
            data.append(
                {
                    "user_id": item.id,
                    "username": item.username,
                    "profile_pic": (
                        item.profile.profile_pic.url
                        if item.profile.profile_pic
                        else None
                    ),
                    "timestamp": item.postlike_set.filter(post=post)
                    .first()
                    .created_at.isoformat(),
                }
            )
        elif engagement_type == "comments":
            data.append(
                {
                    "id": item.id,
                    "user_id": item.user.id,
                    "username": item.user.username,
                    "content": item.content,
                    "timestamp": item.created_at.isoformat(),
                    "likes_count": item.likes_count,
                }
            )
        else:  # views
            data.append(
                {
                    "user_id": item.user.id,
                    "username": item.user.username,
                    "timestamp": item.viewed_at.isoformat(),
                    "ip_address": item.ip_address if request.user.is_staff else None,
                }
            )

    return JsonResponse(
        {
            "status": "success",
            "data": data,
            "has_next": page_obj.has_next(),
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
        }
    )
