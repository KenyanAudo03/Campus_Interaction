# Generated by Django 5.1.2 on 2024-10-29 05:07

import django.core.validators
import django.db.models.deletion
import feeds.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('forums', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=500)),
                ('image', models.ImageField(blank=True, null=True, upload_to='post_images/%Y/%m/', validators=[feeds.models.validate_file_size])),
                ('video', models.FileField(blank=True, null=True, upload_to='post_videos/%Y/%m/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'avi']), feeds.models.validate_file_size])),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('views_count', models.PositiveIntegerField(db_index=True, default=0)),
                ('likes_count', models.PositiveIntegerField(db_index=True, default=0)),
                ('comments_count', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_boosted', models.BooleanField(db_index=True, default=False)),
                ('boost_expires_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')], db_index=True, default='published', max_length=20)),
                ('forum', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='posts', to='forums.forum')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PostLike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='feeds.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='post',
            name='likes',
            field=models.ManyToManyField(blank=True, related_name='liked_posts', through='feeds.PostLike', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='PostView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(auto_now_add=True)),
                ('viewed_date', models.DateField(editable=False)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=200)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='views', to='feeds.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(choices=[('spam', 'Spam'), ('inappropriate', 'Inappropriate Content'), ('harassment', 'Harassment'), ('copyright', 'Copyright Violation'), ('violence', 'Violence'), ('hate_speech', 'Hate Speech'), ('other', 'Other')], max_length=20)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('investigating', 'Under Investigation'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')], default='pending', max_length=20)),
                ('resolution_note', models.TextField(blank=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='feeds.post')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports_made', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_reports', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_edited', models.BooleanField(default=False)),
                ('likes_count', models.PositiveIntegerField(default=0)),
                ('likes', models.ManyToManyField(blank=True, related_name='liked_comments', to=settings.AUTH_USER_MODEL)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='feeds.comment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='feeds.post')),
            ],
            options={
                'indexes': [models.Index(fields=['post', '-created_at'], name='feeds_comme_post_id_057f58_idx')],
            },
        ),
        migrations.AddIndex(
            model_name='postlike',
            index=models.Index(fields=['post', '-created_at'], name='feeds_postl_post_id_f89ddd_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='postlike',
            unique_together={('user', 'post')},
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['-created_at', 'status'], name='feeds_post_created_cee2ed_idx'),
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['user', '-created_at'], name='feeds_post_user_id_387e63_idx'),
        ),
        migrations.AddIndex(
            model_name='postview',
            index=models.Index(fields=['post', '-viewed_at'], name='feeds_postv_post_id_3046ec_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='postview',
            unique_together={('post', 'user', 'viewed_date')},
        ),
        migrations.AddIndex(
            model_name='report',
            index=models.Index(fields=['status', '-created_at'], name='feeds_repor_status_253a02_idx'),
        ),
        migrations.AddIndex(
            model_name='report',
            index=models.Index(fields=['post', 'status'], name='feeds_repor_post_id_3a2d08_idx'),
        ),
    ]
