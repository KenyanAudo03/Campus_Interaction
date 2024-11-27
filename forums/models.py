from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.views import View
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

class Forum(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=500, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, through='ForumMembership', related_name='forums')
    display_picture = models.ImageField(upload_to='forum_dps/', blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Add the creator as an admin member
        ForumMembership.objects.get_or_create(
            user=self.created_by, 
            forum=self, 
            defaults={'role': 'admin'}
        )

    def __str__(self):
        return self.name
    def member_count(self):
        return self.members.count()
    def is_new(self):
        return self.created_at >= timezone.now() - timedelta(days=7)

    def is_active(self):
        recent_posts = self.forums_posts.filter(created_at__gte=timezone.now() - timedelta(days=30))
        return recent_posts.exists()


class ForumMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forum = models.ForeignKey('Forum', on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')  # New field

    class Meta:
        unique_together = ('user', 'forum')

class LeftForumMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE)
    left_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} left {self.forum.name} on {self.left_at}"


class Post(models.Model):
    forum = models.ForeignKey('Forum', on_delete=models.CASCADE, related_name='forums_posts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forums_user_posts')
    content = models.TextField()
    image = models.ImageField(upload_to='forum_post_images/', blank=True, null=True)
    video = models.FileField(upload_to='forum_post_videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post by {self.user.username} in {self.forum.name}"

    def get_media_url(self):
        if self.image:
            return self.image.url
        elif self.video:
            return self.video.url
        return None

    def like_count(self):
        return self.likes.count()
    def view_count(self):
        return self.views.count()

class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_likes'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='likes'  
    )
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} liked Post {self.post.id}"

class PostView(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='forum_post_views'  
    )
    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='views'
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post') 

    def __str__(self):
        return f"Post {self.post.id} viewed by {self.user.username} at {self.viewed_at}"
