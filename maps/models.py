from django.db import models
from django.contrib.auth.models import User

class RecentSearch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recent_searches")
    query = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        unique_together = ("user", "query") 

    def __str__(self):
        return f"{self.user.username} searched for '{self.query}' at {self.timestamp}"
