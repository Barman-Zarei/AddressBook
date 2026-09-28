from django.conf import settings
from django.db import models


class Contact(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=150, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can't have two contacts with the same name+phone
        unique_together = ("owner", "name", "phone")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"
