from django.db import models

class Resource(models.Model):
    CATEGORY_CHOICES = [
        ('lecture_notes', 'Lecture Notes'),
        ('assignments', 'Assignments'),
        ('research_papers', 'Research Papers'),
        ('thesis', 'Thesis and Dissertations'),
        ('ebooks', 'E-books'),
        ('past_papers', 'Past Exam Papers'),
        ('lab_reports', 'Lab Reports'),
        ('presentations', 'Presentations'),
        ('course_projects', 'Course Projects'),
        ('tutorials', 'Tutorials'),
        ('announcements', 'Departmental Announcements'),
        ('general', 'General Resources'),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='resources/')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    uploaded_by = models.CharField(max_length=255, blank=True, null=True, default="Anonymous")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
