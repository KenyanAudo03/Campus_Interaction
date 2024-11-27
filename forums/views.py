from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from .models import Forum, ForumMembership, LeftForumMembership, Post, Like
from .forms import ForumForm, PostForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
import os
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


# View that handles displaying the list of forums.
class ForumListView(ListView):
    model = Forum
    template_name = "forums/forum_list.html"
    context_object_name = "forums"

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
            return f"{count / 1000:.1f}k"
        return str(count)


# View that handles displaying details of a specific forum, including posts and members.
class ForumDetailView(DetailView):
    model = Forum
    template_name = "forums/forum_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forum = self.get_object()
        user = self.request.user

        posts = forum.forums_posts.all().order_by("-created_at")

        for post in posts:
            liked = post.likes.filter(user=user).exists()
            post.liked = liked

        post_count = posts.count()

        members_with_roles = []
        for member in forum.members.all():
            total_likes = Post.objects.filter(user=member, forum=forum).aggregate(
                total_likes=models.Count("likes")
            )["total_likes"]

            members_with_roles.append({
                "user": member,
                "role": ForumMembership.objects.filter(user=member, forum=forum).first().role,
                "is_admin": ForumMembership.objects.filter(
                    user=member, forum=forum, role="admin"
                ).exists(),
                "is_online": (
                    member.profile.is_online if hasattr(member, "profile") else False
                ),
                "post_likes": total_likes or 0,
            })

        members_with_roles.sort(key=lambda x: x["is_admin"], reverse=True)

        online_members_count = sum(
            1 for member_info in members_with_roles if member_info["is_online"]
        )

        left_members = LeftForumMembership.objects.filter(forum=forum)
        user_is_admin = ForumMembership.objects.filter(
            user=user, forum=forum, role="admin"
        ).exists()

        context["members_with_roles"] = members_with_roles
        context["user_is_admin"] = user_is_admin
        context["forum"] = forum
        context["posts"] = posts
        context["post_count"] = post_count
        context["membership"] = ForumMembership.objects.filter(
            forum=forum, user=user
        ).first()
        context["left_members"] = left_members
        context["post_form"] = PostForm()
        context["online_members_count"] = online_members_count
        context["total_members_count"] = len(members_with_roles)

        return context


# View that handles the creation of a new post in a forum.
@method_decorator(csrf_exempt, name='dispatch')
class CreatePostView(View):
    def post(self, request, *args, **kwargs):
        forum = get_object_or_404(Forum, id=kwargs['forum_id'])
        post_form = PostForm(request.POST, request.FILES)
        
        if post_form.is_valid():
            new_post = post_form.save(commit=False)
            new_post.user = request.user
            new_post.forum = forum
            new_post.save()
            
            post_count = Post.objects.filter(forum=forum).count()
            
            return JsonResponse({
                "status": "posted",
                "post_id": new_post.id,
                "username": new_post.user.username,
                "user_profile_pic": new_post.user.profile.profile_pic.url,
                "user_role": "Forum Admin" if ForumMembership.objects.filter(
                    user=request.user, forum=forum, role="admin"
                ).exists() else "Member",
                "forum_name": forum.name,
                "content": new_post.content,
                "media_url": new_post.get_media_url(),
                "created_at": new_post.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "likes_count": new_post.likes.count(),
                "is_liked": new_post.likes.filter(user=request.user).exists(),
                "views_count": new_post.views.count(),
                "user_can_delete": request.user == new_post.user,
                "post_count": post_count,
            })
        else:
            return JsonResponse({"status": "error", "errors": post_form.errors}, status=400)


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
class JoinForumView(View):
    def post(self, request, forum_id):
        forum = get_object_or_404(Forum, id=forum_id)

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

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


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
