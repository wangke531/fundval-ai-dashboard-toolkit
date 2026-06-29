import os

from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication


def local_admin_username():
    return os.environ.get("FUNDVAL_ADMIN_USERNAME", "admin")


class LocalAutoAdminMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            return None
        User = get_user_model()
        user = User.objects.filter(username=local_admin_username(), is_active=True).first()
        if user is not None:
            request.user = user
        return None


class LocalAutoAdminJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        try:
            result = super().authenticate(request)
            if result is not None:
                return result
        except Exception:
            pass
        User = get_user_model()
        user = User.objects.filter(username=local_admin_username(), is_active=True).first()
        if user is None:
            return None
        return (user, None)
