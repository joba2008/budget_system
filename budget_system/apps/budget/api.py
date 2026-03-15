"""Budget API views for AJAX operations — SQLAlchemy version."""
import json
import traceback
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie

from config.database import get_db
from apps.budget.models import BsaMain
from apps.budget.services import save_cell, recalc_all_rebase, _get_period_data
from apps.status.models import BudgetSubmissionStatus


# Field-level permission map (section 3.4.10)
EDITABLE_TABLES = {
    'bsa_spending', 'bsa_saving', 'bsa_newadd',
    'bsa_newadd_approved', 'bsa_volume',
}
ADMIN_ONLY_TABLES = {'bsa_rebase_financeview', 'bsa_rebase_opsview'}
READONLY_TABLES = {'bsa_actual', 'bsa_volume_actual'}


@login_required
@require_POST
def cell_save(request):
    """Save a single cell value via AJAX."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    table = data.get('table', '')
    main_id = data.get('main_id')
    period = data.get('period', '')
    value_str = data.get('value', '')

    if not table or not main_id or not period:
        return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

    user_role = request.session.get('user_role', '')

    if table in READONLY_TABLES:
        return JsonResponse({'status': 'error', 'message': 'This field is read-only'}, status=403)

    if table in ADMIN_ONLY_TABLES:
        if user_role != 'admin':
            return JsonResponse({'status': 'error', 'message': 'Only admin can edit rebase fields'}, status=403)
    elif table not in EDITABLE_TABLES:
        return JsonResponse({'status': 'error', 'message': f'Unknown table: {table}'}, status=400)

    if user_role not in ('admin', 'budgeter'):
        return JsonResponse({'status': 'error', 'message': 'No edit permission'}, status=403)

    with get_db() as session:
        main = session.get(BsaMain, main_id)
        if not main:
            return JsonResponse({'status': 'error', 'message': 'Record not found'}, status=404)

        # Budgeter can only edit their own records
        if user_role == 'budgeter':
            username = request.user.username
            if not main.budgeter.startswith(username):
                return JsonResponse(
                    {'status': 'error', 'message': 'You can only edit your own budget entries'},
                    status=403
                )

        # Check submission status
        if user_role != 'admin' and main.dept_ppt:
            sub_status = session.query(BudgetSubmissionStatus).filter(
                BudgetSubmissionStatus.version == main.version,
                BudgetSubmissionStatus.dept_ppt == main.dept_ppt,
                BudgetSubmissionStatus.status.in_(['under_review', 'complete']),
            ).first()
            if sub_status:
                return JsonResponse(
                    {'status': 'error', 'message': 'This department is under review or complete. Cannot edit.'},
                    status=403
                )

        # Validate numeric value
        new_value = None
        if value_str is not None and str(value_str).strip() != '':
            try:
                new_value = Decimal(str(value_str).strip())
            except (InvalidOperation, ValueError):
                return JsonResponse(
                    {'status': 'error', 'message': 'Value must be a valid number'},
                    status=400
                )

        # Get client IP
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()

        # Execute save
        try:
            scenario = data.get('scenario')
            result = save_cell(session, table, main_id, period, new_value, request.user, ip, scenario=scenario)
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f'Save failed: {str(e)}'}, status=500)

    return JsonResponse(result)


@login_required
def row_data(request):
    """Get data for a specific row (lazy loading)."""
    main_id = request.GET.get('main_id')
    data_type = request.GET.get('data_type', 'spending')

    if not main_id:
        return JsonResponse({'status': 'error', 'message': 'main_id required'}, status=400)

    with get_db() as session:
        main = session.get(BsaMain, main_id)
        if not main:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

        periods = _get_period_data(session, main, data_type)

    # Convert Decimal to string for JSON
    period_values = {k: str(v) if v is not None else None for k, v in periods.items()}

    return JsonResponse({
        'status': 'ok',
        'main_id': int(main_id),
        'data_type': data_type,
        'periods': period_values,
    })


@login_required
@require_POST
def recalc_rebase(request):
    """Batch recalculate all rebase values for a version."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    version = data.get('version', '')
    if not version:
        return JsonResponse({'status': 'error', 'message': 'Version required'}, status=400)

    user_role = request.session.get('user_role', '')
    if user_role != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Admin only'}, status=403)

    try:
        updated = recalc_all_rebase(version)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Recalc failed: {str(e)}'}, status=500)

    return JsonResponse({'status': 'ok', 'updated_count': updated})
