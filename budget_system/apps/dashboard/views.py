"""Dashboard views — SQLAlchemy version."""
import json
from decimal import Decimal
from collections import defaultdict

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from sqlalchemy import func

from config.database import get_db
from apps.budget.models import (
    BsaMain, BsaSpending, BsaRebaseFinanceview,
    BsaActual, BsaSaving, BsaNewadd, BsaVolume,
    get_all_versions,
)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


@login_required
def index(request):
    """Dashboard main page."""
    versions = get_all_versions()
    selected_version = request.GET.get('version', '')

    if not selected_version and versions:
        selected_version = versions[0]

    context = {
        'versions': versions,
        'selected_version': selected_version,
    }

    if selected_version:
        with get_db() as session:
            main_ids = [r[0] for r in session.query(BsaMain.id).filter(
                BsaMain.version == selected_version
            ).all()]

            spending_total = session.query(func.sum(BsaSpending.value)).filter(
                BsaSpending.main_id.in_(main_ids)
            ).scalar() or Decimal(0)

            actual_total = session.query(func.sum(BsaActual.value)).filter(
                BsaActual.main_id.in_(main_ids)
            ).scalar() or Decimal(0)

            saving_total = session.query(func.sum(BsaSaving.value)).filter(
                BsaSaving.main_id.in_(main_ids)
            ).scalar() or Decimal(0)

            rebase_total = session.query(func.sum(BsaRebaseFinanceview.value)).filter(
                BsaRebaseFinanceview.main_id.in_(main_ids)
            ).scalar() or Decimal(0)

            context['kpi'] = {
                'budget': spending_total,
                'actual': actual_total,
                'saving': saving_total,
                'b1_vs_rebase': spending_total - rebase_total,
            }

            dept_ppts = sorted([r[0] for r in session.query(BsaMain.dept_ppt).filter(
                BsaMain.version == selected_version
            ).distinct().all()])
            context['dept_ppts'] = dept_ppts

    return render(request, 'dashboard/index.html', context)


@login_required
def chart_data(request):
    """AJAX endpoint for dashboard chart data."""
    version = request.GET.get('version', '')
    dept_ppts = request.GET.getlist('dept_ppt')
    chart_type = request.GET.get('chart', 'spend_trend')

    if not version:
        return JsonResponse({'error': 'Version required'}, status=400)

    with get_db() as session:
        qs = session.query(BsaMain.id).filter(BsaMain.version == version)
        if dept_ppts:
            qs = qs.filter(BsaMain.dept_ppt.in_(dept_ppts))
        main_ids = [r[0] for r in qs.all()]

        if chart_type == 'spend_trend':
            return _spend_trend_data(session, main_ids, version)
        elif chart_type == 'waterfall':
            return _waterfall_data(session, main_ids, version)
        else:
            return JsonResponse({'error': 'Unknown chart type'}, status=400)


def _period_to_quarter(period):
    """Convert period like 'fy26_202509' to fiscal quarter like 'FY26-Q1'."""
    parts = period.split('_')
    if len(parts) < 2:
        return period
    date_part = parts[-1]
    try:
        month = int(date_part[-2:])
    except (ValueError, IndexError):
        return period

    year = int(date_part[:4])
    if month >= 9:
        fy_num = year - 2000 + 1
        if month <= 11:
            quarter = 1   # Sep(9), Oct(10), Nov(11) -> Q1
        else:
            quarter = 2   # Dec(12) -> Q2
    else:
        fy_num = year - 2000
        if month <= 2:
            quarter = 2   # Jan(1), Feb(2) -> Q2
        elif month <= 5:
            quarter = 3   # Mar(3), Apr(4), May(5) -> Q3
        else:
            quarter = 4   # Jun(6), Jul(7), Aug(8) -> Q4

    return f'FY{fy_num}-Q{quarter}'


def _aggregate_to_quarters(period_data):
    """Aggregate period->value dict into quarter->value dict."""
    quarters = defaultdict(Decimal)
    for period, value in period_data.items():
        q = _period_to_quarter(period)
        quarters[q] += value or Decimal(0)
    return quarters


def _spend_trend_data(session, main_ids, version):
    """Data for Spend & Loading Trend combo chart."""
    spending = defaultdict(Decimal)
    for period, total in (
        session.query(BsaSpending.period, func.sum(BsaSpending.value))
        .filter(BsaSpending.main_id.in_(main_ids))
        .group_by(BsaSpending.period).all()
    ):
        spending[period] = total or Decimal(0)

    rebase = defaultdict(Decimal)
    for period, total in (
        session.query(BsaRebaseFinanceview.period, func.sum(BsaRebaseFinanceview.value))
        .filter(BsaRebaseFinanceview.main_id.in_(main_ids))
        .group_by(BsaRebaseFinanceview.period).all()
    ):
        rebase[period] = total or Decimal(0)

    from apps.importer.validators import extract_scenario
    scenario = extract_scenario(version)
    volume = defaultdict(Decimal)
    for period, total in (
        session.query(BsaVolume.period, func.sum(BsaVolume.value))
        .filter(BsaVolume.main_id.in_(main_ids), BsaVolume.scenario == scenario)
        .group_by(BsaVolume.period).all()
    ):
        volume[period] = total or Decimal(0)

    actual = defaultdict(Decimal)
    for period, total in (
        session.query(BsaActual.period, func.sum(BsaActual.value))
        .filter(BsaActual.main_id.in_(main_ids))
        .group_by(BsaActual.period).all()
    ):
        actual[period] = total or Decimal(0)

    spending_q = _aggregate_to_quarters(spending)
    rebase_q = _aggregate_to_quarters(rebase)
    volume_q = _aggregate_to_quarters(volume)
    actual_q = _aggregate_to_quarters(actual)

    all_quarters = sorted(set(
        list(spending_q.keys()) + list(rebase_q.keys()) +
        list(volume_q.keys()) + list(actual_q.keys())
    ))

    data = {
        'periods': all_quarters,
        'spending': [float(spending_q.get(q, 0)) for q in all_quarters],
        'rebase': [float(rebase_q.get(q, 0)) for q in all_quarters],
        'volume': [float(volume_q.get(q, 0)) for q in all_quarters],
        'actual': [float(actual_q.get(q, 0)) for q in all_quarters],
    }

    return JsonResponse(data, encoder=DecimalEncoder)


def _waterfall_data(session, main_ids, version):
    """Data for Budget Waterfall chart."""
    actual_total = float(
        session.query(func.sum(BsaActual.value)).filter(
            BsaActual.main_id.in_(main_ids)
        ).scalar() or 0
    )

    spending_total = float(
        session.query(func.sum(BsaSpending.value)).filter(
            BsaSpending.main_id.in_(main_ids)
        ).scalar() or 0
    )

    rebase_total = float(
        session.query(func.sum(BsaRebaseFinanceview.value)).filter(
            BsaRebaseFinanceview.main_id.in_(main_ids)
        ).scalar() or 0
    )

    saving_total = float(
        session.query(func.sum(BsaSaving.value)).filter(
            BsaSaving.main_id.in_(main_ids)
        ).scalar() or 0
    )

    newadd_total = float(
        session.query(func.sum(BsaNewadd.value)).filter(
            BsaNewadd.main_id.in_(main_ids)
        ).scalar() or 0
    )

    volume_impact = rebase_total - actual_total
    baseline_adj = float(
        session.query(func.sum(BsaMain.baseline_adjustment)).filter(
            BsaMain.id.in_(main_ids)
        ).scalar() or 0
    )

    data = {
        'categories': ['Actual', 'Volume', 'Baseline Adj', 'Rebase', 'Cost Saving', 'Adder New', 'Budget'],
        'values': [
            actual_total,
            volume_impact,
            -baseline_adj,
            rebase_total,
            -abs(saving_total),
            abs(newadd_total),
            spending_total,
        ],
        'types': ['total', 'increase', 'decrease', 'total', 'decrease', 'increase', 'total'],
    }
    return JsonResponse(data)
