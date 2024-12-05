from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.views import View
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.validators import MaxLengthValidator


class Forum(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=250, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        User, through="ForumMembership", related_name="forums"
    )
    display_picture = models.ImageField(upload_to="forum_dps/", blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Add the creator as an admin member
        ForumMembership.objects.get_or_create(
            user=self.created_by, forum=self, defaults={"role": "admin"}
        )

    def __str__(self):
        return self.name

    def member_count(self):
        return self.members.count()

    def is_new(self):
        return self.created_at >= timezone.now() - timedelta(days=7)

    def is_active(self):
        recent_posts = self.forums_posts.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        return recent_posts.exists()
    def get_absolute_url(self):
        return reverse("forums:forum_detail", kwargs={"pk": self.pk})

class PostRule(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name='post_rules')
    rule_text = models.TextField(
        validators=[MaxLengthValidator(100)] 
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Post Rule for {self.forum.name}"


class CommentRule(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name='comment_rules')
    rule_text = models.TextField(
        validators=[MaxLengthValidator(100)]
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment Rule for {self.forum.name}"

class ForumMembership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forum = models.ForeignKey("Forum", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default="member"
    ) 

    class Meta:
        unique_together = ("user", "forum")


class LeftForumMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE)
    left_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} left {self.forum.name} on {self.left_at}"


class Post(models.Model):
    forum = models.ForeignKey(
        "Forum", on_delete=models.CASCADE, related_name="forums_posts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forums_user_posts",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="forum_post_images/", blank=True, null=True)
    video = models.FileField(upload_to="forum_post_videos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)  

    def __str__(self):
        return f"Post by {self.user.username} in {self.forum.name} - {self.title}"

    def get_media_url(self):
        if self.image:
            return self.image.url
        elif self.video:
            return self.video.url
        return None

    def like_count(self):
        return self.likes.count()
    def comment_count(self):
        return self.comments.count()

    def view_count(self):
        return self.views.count()

    def clean(self):
        """Custom validation to ensure a valid post type."""
        if not self.content and not self.image and not self.video:
            raise ValidationError("A post must have content, an image, or a video.")
        if self.image and self.video:
            raise ValidationError("A post cannot have both an image and a video.")

class Draft(models.Model):
    forum = models.ForeignKey(
        "Forum", on_delete=models.CASCADE, related_name="drafts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_drafts"
    )
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="draft_images/", blank=True, null=True)
    video = models.FileField(upload_to="draft_videos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_posted = models.BooleanField(default=False)  


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")

    def __str__(self):
        return f"{self.user.username} liked Post {self.post.id}"

class PostView(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_post_views",
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")

    def __str__(self):
        return f"Post {self.post.id} viewed by {self.user.username} at {self.viewed_at}"

# Comment Model (with updated related_name for likes)
class Comment(models.Model):
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="forums_comments", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey('self', related_name='replies', on_delete=models.CASCADE, null=True, blank=True)

    def like_count(self):
        return self.likecomment_set.count()

    def is_liked_by_user(self, user):
        return self.likecomment_set.filter(user=user).exists()


# LikeComment Model (with updated related_name for user)
class LikeComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')

class PostFlag(models.Model):
    CATEGORY_CHOICES = [
        ('inappropriate', 'Inappropriate Content'),
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('misinformation', 'Misinformation'),
        ('copyright', 'Copyright Violation'),
        ('other', 'Other'),
    ]

    post = models.ForeignKey('forums.Post', on_delete=models.CASCADE, related_name='flags')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        pass
