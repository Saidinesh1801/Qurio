def user_profile(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        return {
            'user_profile': request.user.profile,
            'user_role': request.user.profile.role,
            'user_theme': request.user.profile.theme,
        }
    return {
        'user_profile': None,
        'user_role': 'anonymous',
        'user_theme': 'light',
    }
