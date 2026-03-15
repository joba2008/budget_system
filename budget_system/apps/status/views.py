import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from config.database import get_db
from apps.budget.models import BsaMain, BsaSpending, get_all_versions
from apps.status.models import BudgetSubmissionStatus


VALID_STATUSES = {'not_started', 'editing', 'under_review', 'complete'}


@login_required
def overview(request):
    """Admin view - department submission status dashboard with area/dept summary."""
    if request.session.get('user_role') != 'admin':
        messages.error(request, 'Only admin can view submission status.')
        return redirect('dashboard:index')

    versions = get_all_versions()
    selected_version = request.GET.get('version', '')

    if not selected_version and versions:
        selected_version = versions[0]

    statuses = []
    summary = {
        'complete': 0, 'under_review': 0,
        'editing': 0, 'not_started': 0, 'total': 0,
    }

    if selected_version:
        with get_db() as session:
            dept_info = (
                session.query(BsaMain.dept_ppt, BsaMain.area, BsaMain.dept)
                .filter(BsaMain.version == selected_version)
                .distinct()
                .order_by(BsaMain.area, BsaMain.dept, BsaMain.dept_ppt)
                .all()
            )

            for dept_ppt, area, dept in dept_info:
                status_obj = session.query(BudgetSubmissionStatus).filter_by(
                    version=selected_version, dept_ppt=dept_ppt,
                ).first()
                if not status_obj:
                    status_obj = BudgetSubmissionStatus(
                        version=selected_version, dept_ppt=dept_ppt,
                        status='not_started', submitted_by=[],
                    )
                    session.add(status_obj)
                    session.flush()

                # Auto-detect editing status
                if status_obj.status == 'not_started':
                    has_data = session.query(BsaSpending).join(
                        BsaMain, BsaSpending.main_id == BsaMain.id
                    ).filter(
                        BsaMain.version == selected_version,
                        BsaMain.dept_ppt == dept_ppt,
                        BsaSpending.value.isnot(None),
                        BsaSpending.value != 0,
                    ).first() is not None
                    if has_data:
                        status_obj.status = 'editing'

                budgeter = session.query(BsaMain.budgeter).filter(
                    BsaMain.version == selected_version,
                    BsaMain.dept_ppt == dept_ppt,
                ).first()
                budgeter_name = budgeter[0] if budgeter else '-'

                statuses.append({
                    'dept_ppt': dept_ppt,
                    'area': area,
                    'dept': dept,
                    'status': status_obj.status,
                    'submitted_by': status_obj.submitted_by or [],
                    'updated_at': status_obj.updated_at,
                    'budgeter': budgeter_name,
                })

                summary[status_obj.status] = summary.get(status_obj.status, 0) + 1
                summary['total'] += 1

    return render(request, 'status/overview.html', {
        'versions': versions,
        'selected_version': selected_version,
        'statuses': statuses,
        'summary': summary,
    })


@login_required
@require_POST
def update_status(request):
    """Admin API to update a department's submission status."""
    if request.session.get('user_role') != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Admin only'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    version = data.get('version', '')
    dept_ppt = data.get('dept_ppt', '')
    new_status = data.get('new_status', '')

    if not version or not dept_ppt:
        return JsonResponse({'status': 'error', 'message': 'Missing fields'}, status=400)

    if new_status not in VALID_STATUSES:
        return JsonResponse({'status': 'error', 'message': f'Invalid status: {new_status}'}, status=400)

    with get_db() as session:
        status_obj = session.query(BudgetSubmissionStatus).filter_by(
            version=version, dept_ppt=dept_ppt,
        ).first()
        if not status_obj:
            status_obj = BudgetSubmissionStatus(
                version=version, dept_ppt=dept_ppt,
                status=new_status, submitted_by=[],
            )
            session.add(status_obj)
        else:
            status_obj.status = new_status

    return JsonResponse({'status': 'ok', 'new_status': new_status})


@login_required
def submit_status(request, version_name):
    """Mark departments for review."""
    if request.method != 'POST':
        return redirect('dashboard:index')

    user_role = request.session.get('user_role', '')
    if user_role not in ('budgeter', 'admin'):
        messages.error(request, 'No permission.')
        return redirect('dashboard:index')

    username = request.user.username

    with get_db() as session:
        if user_role == 'admin':
            dept_ppts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
                BsaMain.version == version_name
            ).distinct().all()]
        else:
            dept_ppts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
                BsaMain.version == version_name,
                BsaMain.budgeter.startswith(username),
            ).distinct().all()]

        updated = 0
        for dept in dept_ppts:
            status_obj = session.query(BudgetSubmissionStatus).filter_by(
                version=version_name, dept_ppt=dept,
            ).first()
            if not status_obj:
                status_obj = BudgetSubmissionStatus(
                    version=version_name, dept_ppt=dept,
                    status='under_review', submitted_by=[username],
                )
                session.add(status_obj)
            else:
                status_obj.status = 'under_review'
                status_obj.submitted_by = [username]
            updated += 1

    messages.success(request, f'Budget submitted for review ({updated} departments).')
    return redirect('budget:version_list')


@login_required
def withdraw_status(request, version_name):
    """Budgeter withdraws completion status."""
    if request.method != 'POST':
        return redirect('dashboard:index')

    username = request.user.username

    with get_db() as session:
        dept_ppts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
            BsaMain.version == version_name,
            BsaMain.budgeter.startswith(username),
        ).distinct().all()]

        for dept in dept_ppts:
            status_obj = session.query(BudgetSubmissionStatus).filter_by(
                version=version_name, dept_ppt=dept,
            ).first()
            if status_obj:
                status_obj.status = 'editing'
                status_obj.submitted_by = []

    messages.success(request, 'Status withdrawn. You can continue editing.')
    return redirect('budget:budget_edit', version_name=version_name)
