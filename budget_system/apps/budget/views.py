from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from config.database import get_db
from apps.budget.models import BsaMain, get_all_versions, parse_version_name
from apps.budget.services import (
    get_budget_data, get_all_periods, get_filter_options, get_overall_data,
    recalc_all_rebase,
)
from apps.status.models import BudgetSubmissionStatus


@login_required
def version_list(request):
    """List all budget versions (derived from bsa_main.version)."""
    version_names = get_all_versions()
    user_role = request.session.get('user_role', '')
    username = request.user.username
    versions = []

    with get_db() as session:
        for name in version_names:
            fy, scenario = parse_version_name(name)
            row_count = session.query(BsaMain).filter(BsaMain.version == name).count()

            is_under_review = False
            if user_role == 'admin':
                all_depts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
                    BsaMain.version == name
                ).distinct().all()]
                is_under_review = session.query(BudgetSubmissionStatus).filter(
                    BudgetSubmissionStatus.version == name,
                    BudgetSubmissionStatus.dept_ppt.in_(all_depts),
                    BudgetSubmissionStatus.status.in_(['under_review', 'complete']),
                ).first() is not None
            elif user_role == 'budgeter':
                user_depts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
                    BsaMain.version == name,
                    BsaMain.budgeter.startswith(username),
                ).distinct().all()]
                is_under_review = session.query(BudgetSubmissionStatus).filter(
                    BudgetSubmissionStatus.version == name,
                    BudgetSubmissionStatus.dept_ppt.in_(user_depts),
                    BudgetSubmissionStatus.status.in_(['under_review', 'complete']),
                ).first() is not None

            versions.append({
                'name': name,
                'fiscal_year': fy,
                'scenario': scenario,
                'row_count': row_count,
                'is_under_review': is_under_review,
            })

    # Overall data for selected version
    selected_version = request.GET.get('version', '')
    if not selected_version and versions:
        selected_version = versions[0]['name']

    overall = None
    if selected_version:
        filters = {}
        if user_role == 'budgeter':
            filters['budgeter'] = username
        overall = get_overall_data(selected_version, filters)

    return render(request, 'budget/version_list.html', {
        'versions': versions,
        'selected_version': selected_version,
        'overall': overall,
    })


@login_required
def budget_edit(request, version_name):
    """Main budget editing page with pivot table."""
    with get_db() as session:
        if not session.query(BsaMain).filter(BsaMain.version == version_name).first():
            messages.error(request, f'Version "{version_name}" not found.')
            return redirect('budget:version_list')

        data_type = request.GET.get('type', 'overall')
        user_role = request.session.get('user_role', '')

        filters = request.GET.copy()
        if user_role == 'budgeter':
            filters['budgeter'] = request.user.username

        filter_options = get_filter_options(version_name)

        editable_types = []
        if user_role in ('admin', 'budgeter'):
            editable_types = ['spending', 'saving', 'newadd', 'newadd_approved']

        is_under_review = False
        if user_role == 'budgeter':
            user_depts = [r[0] for r in session.query(BsaMain.dept_ppt).filter(
                BsaMain.version == version_name,
                BsaMain.budgeter.startswith(request.user.username),
            ).distinct().all()]
            is_under_review = session.query(BudgetSubmissionStatus).filter(
                BudgetSubmissionStatus.version == version_name,
                BudgetSubmissionStatus.dept_ppt.in_(user_depts),
                BudgetSubmissionStatus.status.in_(['under_review', 'complete']),
            ).first() is not None
        elif user_role == 'admin':
            filtered_q = session.query(BsaMain.dept_ppt).filter(BsaMain.version == version_name)
            if filters.get('dept_ppt'):
                filtered_q = filtered_q.filter(BsaMain.dept_ppt == filters['dept_ppt'])
            if filters.get('area'):
                filtered_q = filtered_q.filter(BsaMain.area == filters['area'])
            dept_list = [r[0] for r in filtered_q.distinct().all()]
            is_under_review = session.query(BudgetSubmissionStatus).filter(
                BudgetSubmissionStatus.version == version_name,
                BudgetSubmissionStatus.dept_ppt.in_(dept_list),
                BudgetSubmissionStatus.status.in_(['under_review', 'complete']),
            ).first() is not None

    data_types = [
        ('overall', 'Overall'),
        ('rebase_financeview', 'Rebase Finance'),
        ('rebase_opsview', 'Rebase Ops'),
        ('saving', 'Saving'),
        ('newadd', 'New Add'),
        ('newadd_approved', 'New Add Approved'),
        ('final_budget', 'Final Budget'),
    ]

    context = {
        'version_name': version_name,
        'data_type': data_type,
        'filter_options': filter_options,
        'is_editable': data_type in editable_types and not is_under_review,
        'editable_types': editable_types,
        'user_role': user_role,
        'data_types': data_types,
        'is_under_review': is_under_review,
    }

    if data_type == 'overall':
        overall = get_overall_data(version_name, filters)
        context['overall'] = overall
    else:
        rows = get_budget_data(version_name, filters, data_type)
        periods = get_all_periods(version_name, data_type)
        context['rows'] = rows
        context['periods'] = periods

    return render(request, 'budget/budget_edit.html', context)


@login_required
def version_compare(request, v1_name, v2_name):
    """Compare two budget versions."""
    from apps.budget.services import get_summary_data
    summary1 = get_summary_data(v1_name, data_type='spending')
    summary2 = get_summary_data(v2_name, data_type='spending')

    all_depts = sorted(set(list(summary1.keys()) + list(summary2.keys())))

    comparison = []
    for dept in all_depts:
        s1_total = sum((v or 0) for v in summary1.get(dept, {}).values())
        s2_total = sum((v or 0) for v in summary2.get(dept, {}).values())
        diff = s2_total - s1_total
        pct = (diff / s1_total * 100) if s1_total else 0
        comparison.append({
            'dept_ppt': dept,
            'v1_total': s1_total,
            'v2_total': s2_total,
            'diff': diff,
            'pct': pct,
        })

    return render(request, 'budget/version_compare.html', {
        'v1_name': v1_name, 'v2_name': v2_name, 'comparison': comparison,
    })
