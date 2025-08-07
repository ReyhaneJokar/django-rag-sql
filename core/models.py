from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class ConnectionConfig(models.Model):
    DB_CHOICES = [
        ('postgres', 'PostgreSQL'),
        ('sqlserver', 'SQL Server'),
        ('oracle', 'Oracle'),
    ]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='connections')
    db_type = models.CharField(max_length=20, choices=DB_CHOICES)
    host = models.CharField(max_length=100)
    port = models.IntegerField()
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=50)
    database_name = models.CharField(max_length=50)
    custom_prompt = models.TextField(blank=True, help_text="Any additional text you want to be added to the RAG prompt")
    created_at    = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.database_name}"
    
class AudioQuery(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audio_queries')
    audio_file = models.FileField(upload_to='voice_queries/')
    transcript = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner.username} @ {self.created_at:%Y-%m-%d %H:%M}"