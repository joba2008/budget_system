import json

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from config.database import get_db
from .models import BsaPermission

MASTER_PASSWORD = '0000'


def login_view(request):
    """Login view with bsa_permission table validation and master password support."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username:
            messages.error(request, 'Please enter a username.')
            return render(request, 'accounts/login.html')

        if password != MASTER_PASSWORD:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'accounts/login.html', {'username': username})

        with get_db() as session:
            role = BsaPermission.get_highest_role(session, username)
            if role is None:
                perm = BsaPermission(user_mail=username, user_role='admin', user_area=[])
                session.add(perm)
                session.flush()
                role = 'admin'

        request.session['user_name'] = username
        request.session['user_role'] = role
        request.session['user_display'] = username

        next_url = request.GET.get('next', '/')
        return redirect(next_url)

    return render(request, 'accounts/login.html')


def logout_view(request):
    request.session.flush()
    return redirect('accounts:login')


@login_required
def profile_view(request):
    role = request.session.get('user_role', 'viewer')
    return render(request, 'accounts/profile.html', {'role': role})


@login_required
def user_management(request):
    """Admin page - manage user accounts and roles."""
    if request.session.get('user_role') != 'admin':
        messages.error(request, 'Only admin can manage users.')
        return redirect('dashboard:index')

    with get_db() as session:
        permissions = session.query(BsaPermission).order_by(
            BsaPermission.user_mail, BsaPermission.user_role
        ).all()
        # Detach from session for template use
        perm_list = []
        for p in permissions:
            perm_list.append({
                'pk': p.id,
                'user_mail': p.user_mail,
                'user_role': p.user_role,
                'user_area': p.user_area or [],
            })

    return render(request, 'accounts/user_management.html', {
        'permissions': perm_list,
        'role_choices': BsaPermission.ROLE_CHOICES,
        'area_choices': BsaPermission.AREA_CHOICES,
    })


@login_required
@require_POST
def user_save(request):
    """AJAX - create or update a user permission record."""
    if request.session.get('user_role') != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Admin only'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    user_mail = data.get('user_mail', '').strip()
    user_role = data.get('user_role', '').strip()
    user_area = data.get('user_area', [])
    pk = data.get('pk')

    if isinstance(user_area, str):
        user_area = [user_area] if user_area else []

    if not user_mail or not user_role:
        return JsonResponse({'status': 'error', 'message': 'Username and role are required'}, status=400)

    valid_roles = {r[0] for r in BsaPermission.ROLE_CHOICES}
    if user_role not in valid_roles:
        return JsonResponse({'status': 'error', 'message': f'Invalid role: {user_role}'}, status=400)

    with get_db() as session:
        if pk:
            perm = session.get(BsaPermission, pk)
            if not perm:
                return JsonResponse({'status': 'error', 'message': 'Record not found'}, status=404)
            perm.user_mail = user_mail
            perm.user_role = user_role
            perm.user_area = user_area
        else:
            existing = session.query(BsaPermission).filter_by(
                user_mail=user_mail, user_role=user_role
            ).first()
            if existing:
                return JsonResponse({'status': 'error', 'message': 'This user already has this role'}, status=400)
            perm = BsaPermission(user_mail=user_mail, user_role=user_role, user_area=user_area)
            session.add(perm)
        session.flush()

        return JsonResponse({
            'status': 'ok',
            'pk': perm.id,
            'user_mail': perm.user_mail,
            'user_role': perm.user_role,
            'user_area': perm.user_area or [],
        })


@login_required
@require_POST
def user_delete(request):
    """AJAX - delete a user permission record."""
    if request.session.get('user_role') != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Admin only'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    pk = data.get('pk')
    if not pk:
        return JsonResponse({'status': 'error', 'message': 'pk is required'}, status=400)

    with get_db() as session:
        perm = session.get(BsaPermission, pk)
        if not perm:
            return JsonResponse({'status': 'error', 'message': 'Record not found'}, status=404)
        session.delete(perm)

    return JsonResponse({'status': 'ok'})
