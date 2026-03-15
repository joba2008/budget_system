from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.budget.models import get_all_versions
from apps.reports.services import (
    get_b1_vs_rebase_report, get_saving_detail_report,
    get_budget_heatmap_data, get_category_mix_data,
    get_yoy_comparison, get_controllable_analysis,
    get_budgeter_status,
)


def _get_versions():
    return get_all_versions()


@login_required
def b1_vs_rebase(request):
    """B1 vs Rebase department summary report."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        filters = {
            'under_ops_control': request.GET.get('under_ops_control', ''),
        }
        data = get_b1_vs_rebase_report(version, filters)

    return render(request, 'reports/b1_vs_rebase.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def saving_detail(request):
    """Saving detail tracker."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        data = get_saving_detail_report(version)

    return render(request, 'reports/saving_detail.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def budget_heatmap(request):
    """Monthly budget utilization heatmap."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        data = get_budget_heatmap_data(version)

    return render(request, 'reports/budget_heatmap.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def category_mix(request):
    """Category mix analysis."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        filters = {'dept_ppt': request.GET.get('dept_ppt', '')}
        data = get_category_mix_data(version, filters)

    return render(request, 'reports/category_mix.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def yoy_comparison(request):
    """Year-over-year comparison."""
    versions = _get_versions()
    v1 = request.GET.get('version1', '')
    v2 = request.GET.get('version2', '')
    data = None

    if v1 and v2:
        data = get_yoy_comparison(v1, v2)

    return render(request, 'reports/yoy_comparison.html', {
        'versions': versions,
        'version1': v1,
        'version2': v2,
        'data': data,
    })


@login_required
def controllable(request):
    """Controllable vs Non-Controllable analysis."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        data = get_controllable_analysis(version)

    return render(request, 'reports/controllable.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def budgeter_status_report(request):
    """Budgeter workload and status."""
    versions = _get_versions()
    version = request.GET.get('version', '')
    data = None

    if version:
        data = get_budgeter_status(version)

    return render(request, 'reports/budgeter_status.html', {
        'versions': versions,
        'selected_version': version,
        'data': data,
    })


@login_required
def export_report(request):
    """Export current report as CSV."""
    import csv
    from django.http import HttpResponse

    report_type = request.GET.get('report', '')
    version = request.GET.get('version', '')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="bsa_{report_type}_{version}.csv"'
    writer = csv.writer(response)

    if report_type == 'b1_vs_rebase' and version:
        data = get_b1_vs_rebase_report(version)
        writer.writerow(['Dept PPT', 'Spending', 'Rebase', 'Difference', 'Difference %'])
        for row in data['rows']:
            writer.writerow([row['dept_ppt'], row['spending'], row['rebase'], row['diff'], f"{row['pct']:.1f}%"])
        writer.writerow(['Grand Total', data['grand_total']['spending'], data['grand_total']['rebase'],
                         data['grand_total']['diff'], f"{data['grand_total']['pct']:.1f}%"])

    elif report_type == 'budgeter_status' and version:
        data = get_budgeter_status(version)
        writer.writerow(['Budgeter', 'Total', 'Filled', 'Empty', 'Completion %'])
        for row in data:
            writer.writerow([row['budgeter'], row['total'], row['filled'], row['empty'], f"{row['pct']}%"])

    return response
