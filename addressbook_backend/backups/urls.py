from django.urls import path

from .views import backup_tick

urlpatterns = [
    path("backup-tick/", backup_tick, name="backup-tick"),
]
