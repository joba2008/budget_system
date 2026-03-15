class SessionUser:
    """Lightweight user object populated from session data (no DB)."""

    def __init__(self, username=None):
        self.username = username or ''
        self.is_authenticated = bool(username)
        self.is_active = bool(username)
        self.is_anonymous = not bool(username)
        self.pk = None
        self.id = None

    def __str__(self):
        return self.username


class SessionAuthMiddleware:
    """Replace Django's AuthenticationMiddleware — reads user from session, no auth_user table."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        username = request.session.get('user_name')
        request.user = SessionUser(username)
        return self.get_response(request)
