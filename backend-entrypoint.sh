set -e
echo "Fundval backend fast start"
export DJANGO_SETTINGS_MODULE=fundval.local_settings
: "${FUNDVAL_ADMIN_USERNAME:=admin}"
: "${FUNDVAL_ADMIN_PASSWORD:?FUNDVAL_ADMIN_PASSWORD is required. Set it in .env.}"
export FUNDVAL_ADMIN_USERNAME FUNDVAL_ADMIN_PASSWORD
python manage.py migrate --noinput
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

username = os.environ.get("FUNDVAL_ADMIN_USERNAME", "admin")
password = os.environ["FUNDVAL_ADMIN_PASSWORD"]

User = get_user_model()
user, _ = User.objects.get_or_create(
    username=username,
    defaults={"is_active": True, "is_staff": True, "is_superuser": True},
)
changed = False
for field, value in (("is_active", True), ("is_staff", True), ("is_superuser", True)):
    if hasattr(user, field) and getattr(user, field) != value:
        setattr(user, field, value)
        changed = True
user.set_password(password)
user.save()
PY
python manage.py collectstatic --noinput
python manage.py check_bootstrap
exec gunicorn fundval.wsgi:application --bind 0.0.0.0:8000 --workers 4 --access-logfile - --error-logfile -
