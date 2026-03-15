def user_role(request):
    """Add user role to template context."""
    return {
        'user_role': request.session.get('user_role', ''),
        'is_admin': request.session.get('user_role') == 'admin',
        'is_budgeter': request.session.get('user_role') == 'budgeter',
        'is_viewer': request.session.get('user_role') == 'viewer',
    }
