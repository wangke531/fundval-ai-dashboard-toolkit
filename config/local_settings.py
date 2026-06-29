from fundval.settings import *  # noqa

LOCAL_AUTO_LOGIN = True

MIDDLEWARE = [
    *MIDDLEWARE,
    "fundval.auto_auth.LocalAutoAdminMiddleware",
    "fundval.local_estimate_patch.LocalEstimatePatchMiddleware",
]

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "fundval.auto_auth.LocalAutoAdminJWTAuthentication",
    ],
}
