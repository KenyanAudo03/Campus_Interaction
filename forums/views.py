from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from .models import (
    Forum,
    ForumMembership,
    LeftForumMembership,
    Post,
    Like,
    Comment,
    PostView,
    Draft,
    LikeComment,
    PostFlag,
)
from .forms import ForumForm, PostForm, CommentForm, PostFlagForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
import os
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from forums.templatetags.custom_filters import short_timesince
from django.views.decorators.http import require_http_methods
from django.db.models import Count
from django.views.decorators.csrf import csrf_protect
import json
from django.views.decorators.csrf import csrf_exempt
import logging
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.timezone import now


# View that handles displaying the list of forums.
class ForumListView(ListView):
    model = Forum
    template_name = "forums/forum_list.html"
    context_object_name = "forums"

    def get_queryset(self):
        return Forum.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        total_members = 0
        total_discussions = 0
        total_active_posts = 0
        total_posts = 0

        for forum in context["forums"]:
            forum.members_count = forum.members.count()
            total_members += forum.members_count
            forum_post_count = forum.forums_posts.count()
            total_posts += forum_post_count

            forum.discussions_count = forum.forums_posts.count()
            total_discussions += forum.discussions_count

            forum.active_posts_count = forum.forums_posts.filter(
                created_at__gte=timezone.now() - timedelta(days=1)
            ).count()

            total_active_posts += forum.active_posts_count

            forum.members_count_display = self.format_count(forum.members_count)
            forum.discussions_count_display = self.format_count(forum.discussions_count)
            forum.active_posts_count_display = self.format_count(
                forum.active_posts_count
            )
            forum.forum_post_count = forum_post_count

        context["total_members_display"] = self.format_count(total_members)
        context["total_discussions_display"] = self.format_count(total_discussions)
        context["total_posts_display"] = self.format_count(total_posts)
        context["total_active_posts_display"] = self.format_count(total_active_posts)

        return context

    def format_count(self, count):
        if count >= 1000:
            return f"{count // 1000}k"
        return str(count)


class ForumDetailView(LoginRequiredMixin, DetailView):
    model = Forum
    template_name = "forums/forum_detail.html"
    context_object_name = "forum"

    def get_queryset(self):
        return Forum.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forum = self.get_object()
        user = self.request.user

        # Process posts with role determination
        posts = forum.forums_posts.all().order_by("-created_at")
        for post in posts:
            post.liked = post.likes.filter(user=user).exists()

            # Determine the user's role for this specific forum
            membership = ForumMembership.objects.filter(
                user=post.user, forum=forum
            ).first()

            if forum.created_by == post.user:
                post.user_role = "Main Admin"
            elif membership and membership.role == "admin":
                post.user_role = "Forum Admin"
            elif membership and membership.role == "member":
                post.user_role = "Member"
            else:
                post.user_role = post.user.username

        post_count = posts.count()
        comments = (
            Comment.objects.filter(post__forum=forum)
            .select_related("user", "post")
            .prefetch_related("replies", "likecomment_set")
        )
        comment_count = comments.count()

        # Process members with roles
        members_with_roles = []
        for member in forum.members.all():
            membership = ForumMembership.objects.filter(
                user=member, forum=forum
            ).first()
            total_likes = Post.objects.filter(user=member, forum=forum).aggregate(
                total_likes=models.Count("likes")
            )["total_likes"]

            members_with_roles.append(
                {
                    "user": member,
                    "role": (
                        "Main Admin"
                        if member == forum.created_by
                        else (
                            "Forum Admin"
                            if membership and membership.role == "admin"
                            else "Member"
                        )
                    ),
                    "is_admin": membership and membership.role == "admin",
                    "is_online": (
                        member.profile.is_online
                        if hasattr(member, "profile")
                        else False
                    ),
                    "post_likes": total_likes or 0,
                }
            )

        members_with_roles.sort(key=lambda x: x["is_admin"], reverse=True)

        # Count online members
        online_members_count = sum(
            1 for member_info in members_with_roles if member_info["is_online"]
        )

        # Process left members and admin status
        left_members = LeftForumMembership.objects.filter(forum=forum)
        user_is_admin = ForumMembership.objects.filter(
            user=user, forum=forum, role="admin"
        ).exists()

        # Process all forums for context
        all_forums = Forum.objects.annotate(post_count=Count("forums_posts")).order_by(
            "-post_count"
        )

        forum_details = []

        for f in all_forums:
            is_member = ForumMembership.objects.filter(user=user, forum=f).exists()
            is_admin = ForumMembership.objects.filter(user=user, forum=f).first()
            is_admin = is_admin.role == "admin" if is_admin else False
            is_main_admin = f.created_by == user
            total_members = f.members.count()

            forum_details.append(
                {
                    "forum": f,
                    "total_members": total_members,
                    "user_is_member": is_member,
                    "user_is_admin": is_admin,
                    "user_is_main_admin": is_main_admin,
                    "is_current_forum": f == forum,
                }
            )

        # Update context with all processed data
        context.update(
            {
                "members_with_roles": members_with_roles,
                "user_is_admin": user_is_admin,
                "forum": forum,
                "posts": posts,
                "post_count": post_count,
                "membership": ForumMembership.objects.filter(
                    forum=forum, user=user
                ).first(),
                "left_members": left_members,
                "post_form": PostForm(),
                "online_members_count": online_members_count,
                "total_members_count": len(members_with_roles),
                "forum_details": forum_details,
                "comment_count": comment_count,
            }
        )

        return context


@require_http_methods(["GET"])
def search_posts(request):
    query = request.GET.get("q", "")
    forum_id = request.GET.get("forum_id")

    if not query or not forum_id:
        return JsonResponse({"suggestions": []})

    suggestions = Post.objects.filter(
        Q(forum_id=forum_id) & (Q(title__icontains=query) | Q(content__icontains=query))
    ).order_by("-created_at")[:5]

    suggestion_list = []
    for post in suggestions:
        media_url = (
            post.image.url
            if post.image
            else (
                post.video.url
                if post.video
                else (
                    post.user.profile.profile_pic.url
                    if hasattr(post.user, "profile") and post.user.profile.profile_pic
                    else None
                )
            )
        )

        suggestion_list.append(
            {
                "id": post.id,
                "title": post.title[:35] + ("..." if len(post.title) > 35 else ""),
                "url": reverse(
                    "forums:post_detail",
                    kwargs={"forum_id": forum_id, "post_id": post.id},
                ),
                "author": post.user.username,
                "created_at": f"{short_timesince(post.created_at)}",
                "media": media_url,
            }
        )

    return JsonResponse({"suggestions": suggestion_list})


class CreatePostView(View):
    def get(self, request, forum_id, *args, **kwargs):
        # Fetch the forum
        forum = get_object_or_404(Forum, id=forum_id)
        posts = forum.forums_posts.all().order_by("-created_at")
        post_count = posts.count()
        form = PostForm()

        # Fetch other popular forums
        all_forums = Forum.objects.annotate(post_count=Count("forums_posts")).order_by(
            "-post_count"
        )[:5]
        forum_details = []
        user = request.user

        # Check if the user is subscribed to this forum
        user_is_sub = ForumMembership.objects.filter(user=user, forum=forum).exists()

        for f in all_forums:
            is_member = ForumMembership.objects.filter(user=user, forum=f).exists()
            is_admin = ForumMembership.objects.filter(user=user, forum=f).first()
            is_admin = is_admin.role == "admin" if is_admin else False
            is_main_admin = f.created_by == user
            total_members = f.members.count()

            forum_details.append(
                {
                    "forum": f,
                    "total_members": total_members,
                    "user_is_member": is_member,
                    "user_is_admin": is_admin,
                    "user_is_main_admin": is_main_admin,
                    "is_current_forum": f == forum,
                }
            )
        comments = (
            Comment.objects.filter(post__forum=forum)
            .select_related("user", "post")
            .prefetch_related("replies", "likecomment_set")
        )
        comment_count = comments.count()

        return render(
            request,
            "forums/create_post.html",
            {
                "post_form": form,
                "forum": forum,
                "post_count": post_count,
                "forum_details": forum_details,
                "user_is_sub": user_is_sub,  # Add subscription status to the context
                "comment_count": comment_count,
            },
        )

    def post(self, request, forum_id, *args, **kwargs):
        # Fetch the forum
        forum = get_object_or_404(Forum, id=forum_id)

        # Check if the user is subscribed to this forum
        user_is_sub = ForumMembership.objects.filter(
            user=request.user, forum=forum
        ).exists()

        if not user_is_sub:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You must subscribe to this forum to create a post or draft.",
                },
                status=403,
            )

        # Handle draft or post creation
        form = PostForm(request.POST, request.FILES)
        is_draft = request.POST.get("is_draft", "false") == "true"
        


        if is_draft:
            # Save the draft post
            draft = Draft(
                forum=forum,
                user=request.user,
                title=request.POST.get("title", ""),
                content=request.POST.get("content", ""),
                image=request.FILES.get("image"),
                video=request.FILES.get("video"),
            )
            draft.save()

            return JsonResponse(
                {
                    "success": True,
                    "redirect_url": "/drafts/",  # Redirect to drafts page
                    "draft": {
                        "id": draft.id,
                        "title": draft.title,
                        "content": draft.content,
                    },
                }
            )
        else:
            if form.is_valid():
                # Save the post as published
                post = form.save(commit=False)
                post.forum = forum
                post.user = request.user
                post.approved = True
                post.save()

                return JsonResponse(
                    {
                        "success": True,
                        "redirect_url": forum.get_absolute_url(),  # Redirect to forum details
                    }
                )

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "errors": form.errors}, status=400
                )

        return render(
            request, "forums/create_post.html", {"post_form": form, "forum": forum}
        )


# View that handles deleting a specific post.
class PostDeleteView(View):
    def delete(self, request, post_id):
        try:
            post = get_object_or_404(Post, id=post_id)

            if post.image:
                os.remove(post.image.path)
            if post.video:
                os.remove(post.video.path)

            post.delete()

            post_count = post.forum.forums_posts.count()

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Post deleted successfully",
                    "post_count": post_count,
                }
            )

        except Post.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Post not found"}, status=404
            )

        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": "Internal server error"}, status=500
            )


# View that handles liking and unliking posts.
class LikePostView(View):
    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        like, created = Like.objects.get_or_create(user=request.user, post=post)

        if created:
            status = "liked"
        else:
            like.delete()
            status = "unliked"

        return JsonResponse(
            {
                "status": status,
                "like_count": post.likes.count(),
            }
        )


# View that handles subscribing to or unsubscribing from a forum.
class JoinForumView(LoginRequiredMixin, View):
    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)
        total_likes = Post.objects.filter(user=request.user, forum=forum).aggregate(
            total_likes=models.Count("likes")
        )["total_likes"]

        left_membership = LeftForumMembership.objects.filter(
            user=request.user, forum=forum
        ).first()

        if left_membership:
            left_membership.delete()
        membership, created = ForumMembership.objects.get_or_create(
            user=request.user, forum=forum
        )

        if created:
            membership.role = "member"
            membership.save()

        return JsonResponse(
            {
                "status": "subscribed",
                "total_likes": total_likes,
                "role": membership.role,
                "member_count": forum.member_count(),
                "posts_count": forum.posts.count(),
                "topics_count": forum.forums_posts.count(),
            }
        )

    def delete(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)

        membership = ForumMembership.objects.filter(
            user=request.user, forum=forum
        ).first()
        if membership:
            LeftForumMembership.objects.create(user=request.user, forum=forum)

            membership.delete()
        return JsonResponse(
            {
                "status": "left",
                "member_count": forum.member_count(),
                "posts_count": forum.posts.count(),
                "topics_count": forum.forums_posts.count(),
            }
        )


# View that handles creating a new forum.
class ForumCreateView(LoginRequiredMixin, CreateView):
    model = Forum
    form_class = ForumForm
    template_name = "forums/forum_create.html"
    success_url = reverse_lazy("forums:forum_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forums = Forum.objects.all().order_by("-created_at")
        forum_details = []
        user = self.request.user

        for f in all_forums:
            is_member = ForumMembership.objects.filter(user=user, forum=f).exists()
            is_admin = ForumMembership.objects.filter(user=user, forum=f).first()
            is_admin = is_admin.role == "admin" if is_admin else False
            is_main_admin = f.created_by == user
            total_members = f.members.count()

            forum_details.append(
                {
                    "forum": f,
                    "total_members": total_members,
                    "user_is_member": is_member,
                    "user_is_admin": is_admin,
                    "user_is_main_admin": is_main_admin,
                }
            )

        context["forum_details"] = forum_details
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


@login_required
def post_detail(request, forum_id, post_id):
    forum = get_object_or_404(Forum, id=forum_id)
    post = get_object_or_404(Post, id=post_id, forum=forum)

    posts = forum.forums_posts.all().order_by("-created_at")
    user = request.user
    for forum_post in posts:
        forum_post.liked = forum_post.likes.filter(user=user).exists()

    comments = post.comments.order_by("-created_at")

    if user.is_authenticated:
        for comment in comments:
            comment.is_liked = comment.likecomment_set.filter(user=user).exists()
            for reply in comment.replies.all():
                reply.is_liked = reply.likecomment_set.filter(user=user).exists()
                print(f"Reply ID {reply.id}, is_liked: {reply.is_liked}")

    else:
        for comment in comments:
            comment.is_liked = False
            for reply in comment.replies.all():
                reply.is_liked = False  

    left_posts = forum.forums_posts.all().order_by("-created_at")

    for left_post in left_posts:
        left_post.liked = left_post.likes.filter(user=user).exists()
        membership = ForumMembership.objects.filter(
            user=left_post.user, forum=forum
        ).first()

        # Assign role to the post based on the membership
        if forum.created_by == left_post.user:
            left_post.user_role = "Main Admin"  # Creator of the forum
        elif membership and membership.role == "admin":
            left_post.user_role = "Admin"  # Admins
        elif membership and membership.role == "member":
            left_post.user_role = "Member"  # Forum members
        elif not membership:
            left_post.user_role = left_post.user.username  # Non-members, show username
        else:
            left_post.user_role = None  # If no role is found, assign None

    post_count = left_posts.count()

    members_with_roles = []
    for member in forum.members.all():
        membership = ForumMembership.objects.filter(user=member, forum=forum).first()
        total_likes = Post.objects.filter(user=member, forum=forum).aggregate(
            total_likes=models.Count("likes")
        )["total_likes"]

        members_with_roles.append(
            {
                "user": member,
                "role": (
                    "Main Admin"
                    if member == forum.created_by
                    else (
                        "Admin"
                        if membership and membership.role == "admin"
                        else "Member"
                    )
                ),
                "is_admin": membership and membership.role == "admin",
                "is_online": (
                    member.profile.is_online if hasattr(member, "profile") else False
                ),
                "post_likes": total_likes or 0,
            }
        )

    members_with_roles.sort(key=lambda x: x["is_admin"], reverse=True)

    left_members = LeftForumMembership.objects.filter(forum=forum)
    all_forums = Forum.objects.all().order_by("-created_at")
    forum_details = []

    for f in all_forums:
        membership = ForumMembership.objects.filter(user=user, forum=f).first()
        is_member = bool(membership)
        is_admin = membership.role == "admin" if membership else False
        is_main_admin = f.created_by == user
        total_members = f.members.count()

        forum_details.append(
            {
                "forum": f,
                "total_members": total_members,
                "user_is_member": is_member,
                "membership": ForumMembership.objects.filter(
                    forum=forum, user=user
                ).first(),
                "user_is_admin": is_admin,
                "user_is_main_admin": is_main_admin,
                "is_current_forum": f == forum,
            }
        )

    PostView.objects.get_or_create(post=post, user=request.user)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = user
            comment.save()
            return redirect("forums:post_detail", forum_id=forum.id, post_id=post.id)
    else:
        form = CommentForm()

    # Setting the correct user role for the post (creator, admin, member, or non-member)
    membership = ForumMembership.objects.filter(user=post.user, forum=forum).first()
    if forum.created_by == post.user:
        post.user_role = "Main Admin"
    elif membership and membership.role == "admin":
        post.user_role = "Admin"
    elif membership and membership.role == "member":
        post.user_role = "Member"
    elif not membership:
        post.user_role = post.user.username
    else:
        post.user_role = None
    liked_reply_ids = post.comments.filter(replies__likecomment__user=user).values_list('replies__id', flat=True)

    return render(
        request,
        "forums/post_detail.html",
        {
            "forum": forum,
            "post": post,
            "forum_details": forum_details,
            "post_count": post_count,
            "user_role": post.user_role,
            "left_members": left_members,
            "membership": ForumMembership.objects.filter(
                forum=forum, user=user
            ).first(),
            "members_with_roles": members_with_roles,
            "form": form,
            "comments": comments,
            "comment_count": comments.count(),
            "liked_reply_ids": liked_reply_ids,
        },
    )


@login_required
def drafts_page(request, forum_id):
    forum = get_object_or_404(Forum, id=forum_id)

    # Auto-delete drafts older than 7 days
    one_week_ago = now() - timedelta(days=7)
    Draft.objects.filter(
        user=request.user, forum=forum, is_posted=False, created_at__lt=one_week_ago
    ).delete()

    # Retrieve updated drafts after auto-delete
    drafts = Draft.objects.filter(user=request.user, forum=forum, is_posted=False).order_by(
        "-created_at"
    )
    drafts_count = drafts.count()

    comments = (
        Comment.objects.filter(post__forum=forum)
        .select_related("user", "post")
        .prefetch_related("replies", "likecomment_set")
    )
    user = request.user
    comment_count = comments.count()
    posts = forum.forums_posts.all().order_by("-created_at")
    post_count = posts.count()
    left_members = LeftForumMembership.objects.filter(forum=forum)


    members_with_roles = []
    for member in forum.members.all():
        membership = ForumMembership.objects.filter(user=member, forum=forum).first()
        total_likes = Post.objects.filter(user=member, forum=forum).aggregate(
            total_likes=models.Count("likes")
        )["total_likes"]

        members_with_roles.append(
            {
                "user": member,
                "role": (
                    "Main Admin"
                    if member == forum.created_by
                    else (
                        "Forum Admin"
                        if membership and membership.role == "admin"
                        else "Member"
                    )
                ),
                "is_admin": membership and membership.role == "admin",
                "is_online": (
                    member.profile.is_online if hasattr(member, "profile") else False
                ),
                "post_likes": total_likes or 0,
            }
        )

    members_with_roles.sort(key=lambda x: x["is_admin"], reverse=True)
    
    all_forums = Forum.objects.annotate(post_count=Count('forums_posts')).order_by('-post_count', '-created_at')
    forum_details = []

    for f in all_forums:
        is_member = ForumMembership.objects.filter(user=user, forum=f).exists()
        is_admin = ForumMembership.objects.filter(user=user, forum=f).first()
        is_admin = is_admin.role == "admin" if is_admin else False
        is_main_admin = f.created_by == user
        total_members = f.members.count()

        forum_details.append(
            {
                "forum": f,
                "total_members": total_members,
                "user_is_member": is_member,
                "user_is_admin": is_admin,
                "user_is_main_admin": is_main_admin,
                "is_current_forum": f == forum,
            }
        )

    # Render the page
    return render(
        request,
        "forums/drafts.html",
        {
            "forum": forum,
            "drafts": drafts,
            "comment_count": comment_count,
            "post_count": post_count,
            "membership": ForumMembership.objects.filter(
                forum=forum, user=user
            ).first(),
            "members_with_roles": members_with_roles,
            "forum_details": forum_details,
            "drafts_count": drafts_count,
            "left_members" : left_members,
        },
    )
def post_draft(request, draft_id):
    if request.method == "POST":
        draft = get_object_or_404(Draft, id=draft_id)
        if request.user == draft.user:
            post = Post.objects.create(
                forum=draft.forum,
                user=draft.user,
                title=draft.title,
                content=draft.content,
                image=draft.image,
                video=draft.video,
            )
            draft.is_posted = True
            draft.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Draft posted successfully!',
                'draft_id': draft_id,
                'post_id': post.id
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
@login_required
@csrf_protect
def add_comment_to_post(request, post_id):
    try:
        post = Post.objects.get(id=post_id)

        # Check if the user is a member of the forum
        forum = post.forum  # Assuming each post belongs to a forum
        if not forum.members.filter(id=request.user.id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "You must be a member of the forum to comment.",
                },
                status=403,
            )

        data = json.loads(request.body)
        content = data.get("content", "").strip()

        if not content:
            return JsonResponse(
                {"success": False, "error": "Comment cannot be empty"}, status=400
            )

        # Create comment
        comment = Comment.objects.create(post=post, user=request.user, content=content)

        # Prepare response data
        return JsonResponse(
            {
                "success": True,
                "comment": {
                    "id": comment.id,
                    "username": comment.user.username,
                    "content": comment.content,
                    "profile_pic_url": (
                        comment.user.profile.profile_pic.url
                        if hasattr(comment.user, "profile")
                        else ""
                    ),
                    "likes_count": 0,
                    "replies_count": 0,
                    "user_id": comment.user.id,
                },
            }
        )
    except Post.DoesNotExist:
        return JsonResponse({"success": False, "error": "Post not found"}, status=404)
    except Exception as e:
        logging.error("Error in add_comment_to_post: %s", str(e))
        return JsonResponse(
            {"success": False, "error": "An error occurred."}, status=500
        )


@login_required
@require_http_methods(["POST"])
@csrf_protect
def reply_to_comment(request, comment_id):
    """
    Add a reply to a specific comment via AJAX
    """
    try:
        parent_comment = get_object_or_404(Comment, id=comment_id)

        # Check if the current user is a member of the post's forum
        post = parent_comment.post
        forum = post.forum  # Assuming each post belongs to a forum
        if not forum.members.filter(id=request.user.id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "You must be a member of the forum to reply to this comment.",
                },
                status=403,
            )

        # Proceed with processing the reply
        data = json.loads(request.body)
        content = data.get("content", "").strip()

        if not content:
            return JsonResponse(
                {"success": False, "error": "Comment cannot be empty"}, status=400
            )

        # Create reply
        reply = Comment.objects.create(
            post=parent_comment.post,
            user=request.user,
            content=content,
            parent_comment=parent_comment,
        )

        # Prepare response data
        return JsonResponse(
            {
                "success": True,
                "comment": {
                    "id": reply.id,
                    "username": reply.user.username,
                    "content": reply.content,
                    "profile_pic_url": (
                        reply.user.profile.profile_pic.url
                        if hasattr(reply.user, "profile")
                        else ""
                    ),
                    "likes_count": 0,
                    "user_id": reply.user.id,  # Add the user_id
                },
            }
        )

    except Exception as e:
        logging.error("Error in reply_to_comment: %s", str(e))
        return JsonResponse(
            {"success": False, "error": "An error occurred while replying."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def like_comment(request, comment_id):
    try:
        comment = Comment.objects.get(id=comment_id)
        forum = comment.post.forum  # Assuming each post belongs to a forum

        # Check if the user is a member of the forum
        if not forum.members.filter(id=request.user.id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "You must be a member of the forum to like comments.",
                },
                status=403,
            )

        user = request.user
        like, created = LikeComment.objects.get_or_create(user=user, comment=comment)

        if not created:
            like.delete()
            return JsonResponse(
                {"success": True, "liked": False, "likes_count": comment.like_count()}
            )

        return JsonResponse(
            {"success": True, "liked": True, "likes_count": comment.like_count()}
        )
    except Comment.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Comment not found"}, status=404
        )


@login_required
@require_http_methods(["GET"])
def check_post_updates(request, post_id):
    """
    Check for any new comments or likes since the last check
    """
    try:
        post = Post.objects.get(id=post_id)

        # Get recent comments for this post (last 10 minutes)
        from django.utils import timezone
        from datetime import timedelta

        recent_comments = Comment.objects.filter(
            post=post, created_at__gte=timezone.now() - timedelta(minutes=10)
        ).count()

        # Get recent likes
        recent_likes = LikeComment.objects.filter(
            comment__post=post, created_at__gte=timezone.now() - timedelta(minutes=10)
        ).count()

        return JsonResponse(
            {
                "success": True,
                "new_comments": recent_comments,
                "new_likes": recent_likes,
            }
        )

    except Post.DoesNotExist:
        return JsonResponse({"success": False, "error": "Post not found"}, status=404)


@csrf_exempt
@login_required
def delete_comment(request, comment_id):
    if request.method == "DELETE":
        comment = get_object_or_404(Comment, id=comment_id)

        # Check if the user is the comment owner or a forum member
        forum = comment.post.forum  # Assuming each post belongs to a forum
        if (
            comment.user != request.user
            and not forum.members.filter(id=request.user.id).exists()
        ):
            return JsonResponse(
                {"error": "You do not have permission to delete this comment."},
                status=403,
            )

        post = comment.post
        comment.replies.all().delete()
        comment.delete()

        # Get the updated comment count
        comment_count = post.comments.count()

        return JsonResponse({"success": True, "comment_count": comment_count})

    return JsonResponse({"error": "Invalid request method."}, status=400)


# Hide Posts
@login_required
def toggle_post_approval(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Ensure that the user can only toggle their own post, or is a superuser
    if post.user == request.user or request.user.is_superuser:
        post.approved = not post.approved
        post.save()

        return JsonResponse(
            {"success": True, "approved": post.approved, "post_id": post.id}
        )

    return JsonResponse(
        {"success": False, "error": "You do not have permission to toggle this post."},
        status=403,
    )


@login_required
@require_POST
def flag_post(request, post_id):
    form = PostFlagForm(request.POST)
    if form.is_valid():
        try:
            post = Post.objects.get(id=post_id)
            PostFlag.objects.create(
                post=post,
                user=request.user,
                category=form.cleaned_data["category"],
                description=form.cleaned_data["description"],
            )
            return JsonResponse(
                {"status": "success", "message": "Post flagged successfully"}
            )
        except Post.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Post not found"}, status=404
            )
    # Send specific form errors
    return JsonResponse({"status": "error", "errors": form.errors}, status=400)


# View that handles managing members' roles and actions in a forum.
class ManageMembersView(LoginRequiredMixin, View):
    def post(self, request, forum_id, user_id):
        forum = get_object_or_404(Forum, id=forum_id)
        user_to_manage = get_object_or_404(User, id=user_id)
        membership = ForumMembership.objects.filter(
            user=user_to_manage, forum=forum
        ).first()

        if not ForumMembership.objects.filter(
            user=request.user, forum=forum, role="admin"
        ).exists():
            messages.error(request, "You do not have permission to manage members.")
            return redirect("forums:forum_detail", pk=forum.id)

        action = request.POST.get("action")
        if action == "remove" and membership:
            membership.delete()
            messages.success(
                request, f"{user_to_manage.username} has been removed from the forum."
            )
        elif action == "make_admin" and membership:
            membership.role = "admin"
            membership.save()
            messages.success(request, f"{user_to_manage.username} is now an admin.")
        elif action == "revoke_admin" and membership:
            membership.role = "member"
            membership.save()
            messages.success(
                request,
                f"{user_to_manage.username}'s admin privileges have been revoked.",
            )
        else:
            messages.error(request, "Invalid action.")

        return redirect("forums:forum_detail", pk=forum.id)


def manage_forum(request, forum_id):
    forum = get_object_or_404(Forum, id=forum_id)
    user = request.user
    posts = forum.forums_posts.all().order_by("-created_at")
    post_count = posts.count()
    comments = (
            Comment.objects.filter(post__forum=forum)
            .select_related("user", "post")
            .prefetch_related("replies", "likecomment_set")
        )
    comment_count = comments.count()
    return render(
        request,
        "forums/manage.html",
        {
            "forum_id": forum_id,
            "forum": forum,
            "membership": ForumMembership.objects.filter(
                forum=forum, user=user
            ).first(),
            "post_count": post_count,
            "comment_count": comment_count,
        },
    )
