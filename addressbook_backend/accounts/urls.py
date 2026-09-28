from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, LoginView, DeleteAccountView, MeView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("delete/", DeleteAccountView.as_view(), name="delete_account"),
    path("me/", MeView.as_view(), name="me"),
]
