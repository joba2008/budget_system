"""Report service layer — SQLAlchemy version."""
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, and_

from config.database import get_db
from apps.budget.models import (
    BsaMain, BsaSpending, BsaRebaseFinanceview, BsaRebaseOpsview,
    BsaActual, BsaSaving, BsaNewadd, BsaVolumeActual, BsaVolume,
)


def get_b1_vs_rebase_report(version, filters=None):
    """Section 3.5.2 - B1 vs Rebase department summary."""
    with get_db() as session:
        qs = session.query(BsaMain.id).filter(BsaMain.version == version)
        if filters:
            if filters.get('under_ops_control'):
                qs = qs.filter(BsaMain.under_ops_control == filters['under_ops_control'])

        main_ids = [r[0] for r in qs.all()]

        # Get spending by dept_ppt
        spending_by_dept = defaultdict(Decimal)
        for dept, total in (
            session.query(BsaMain.dept_ppt, func.sum(BsaSpending.value))
            .join(BsaSpending, BsaSpending.main_id == BsaMain.id)
            .filter(BsaSpending.main_id.in_(main_ids))
            .group_by(BsaMain.dept_ppt)
            .all()
        ):
            spending_by_dept[dept] = total or Decimal(0)

        # Get rebase by dept_ppt
        rebase_by_dept = defaultdict(Decimal)
        for dept, total in (
            session.query(BsaMain.dept_ppt, func.sum(BsaRebaseFinanceview.value))
            .join(BsaRebaseFinanceview, BsaRebaseFinanceview.main_id == BsaMain.id)
            .filter(BsaRebaseFinanceview.main_id.in_(main_ids))
            .group_by(BsaMain.dept_ppt)
            .all()
        ):
            rebase_by_dept[dept] = total or Decimal(0)

        all_depts = sorted(set(list(spending_by_dept.keys()) + list(rebase_by_dept.keys())))

        rows = []
        grand_spending = Decimal(0)
        grand_rebase = Decimal(0)

        for dept in all_depts:
            s = spending_by_dept.get(dept, Decimal(0))
            r = rebase_by_dept.get(dept, Decimal(0))
            diff = s - r
            pct = (diff / r * 100) if r else Decimal(0)
            rows.append({
                'dept_ppt': dept,
                'spending': s,
                'rebase': r,
                'diff': diff,
                'pct': pct,
            })
            grand_spending += s
            grand_rebase += r

        grand_diff = grand_spending - grand_rebase
        grand_pct = (grand_diff / grand_rebase * 100) if grand_rebase else Decimal(0)

        return {
            'rows': rows,
            'grand_total': {
                'spending': grand_spending,
                'rebase': grand_rebase,
                'diff': grand_diff,
                'pct': grand_pct,
            },
        }


def get_saving_detail_report(version):
    """Section 3.5.3 - Saving detail tracker."""
    with get_db() as session:
        main_ids = [r[0] for r in session.query(BsaMain.id).filter(BsaMain.version == version).all()]

        savings = (
            session.query(BsaSaving)
            .join(BsaMain, BsaSaving.main_id == BsaMain.id)
            .filter(
                BsaSaving.main_id.in_(main_ids),
                BsaSaving.value.isnot(None),
                BsaSaving.value != 0,
            )
            .order_by(BsaMain.dept_ppt, BsaMain.category, BsaMain.accounts)
            .all()
        )

        grouped = defaultdict(lambda: defaultdict(list))
        for s in savings:
            dept = s.main.dept_ppt
            cat = s.main.category
            grouped[dept][cat].append({
                'accounts': s.main.accounts,
                'period': s.period,
                'value': s.value,
                'description': '',
            })

        return dict(grouped)


def get_budget_heatmap_data(version):
    """Section 3.5.4 - Monthly budget utilization heatmap."""
    with get_db() as session:
        main_ids = [r[0] for r in session.query(BsaMain.id).filter(BsaMain.version == version).all()]

        # Spending by dept_ppt + period
        spending_data = defaultdict(lambda: defaultdict(Decimal))
        for dept, period, total in (
            session.query(BsaMain.dept_ppt, BsaSpending.period, func.sum(BsaSpending.value))
            .join(BsaSpending, BsaSpending.main_id == BsaMain.id)
            .filter(BsaSpending.main_id.in_(main_ids))
            .group_by(BsaMain.dept_ppt, BsaSpending.period)
            .all()
        ):
            spending_data[dept][period] = total or Decimal(0)

        # Actual by dept_ppt + period
        actual_data = defaultdict(lambda: defaultdict(Decimal))
        for dept, period, total in (
            session.query(BsaMain.dept_ppt, BsaActual.period, func.sum(BsaActual.value))
            .join(BsaActual, BsaActual.main_id == BsaMain.id)
            .filter(BsaActual.main_id.in_(main_ids))
            .group_by(BsaMain.dept_ppt, BsaActual.period)
            .all()
        ):
            actual_data[dept][period] = total or Decimal(0)

        # Calculate utilization
        all_depts = sorted(set(list(spending_data.keys()) + list(actual_data.keys())))
        all_periods = sorted(
            {p for d in spending_data.values() for p in d.keys()} |
            {p for d in actual_data.values() for p in d.keys()}
        )

        heatmap = []
        for dept in all_depts:
            row = {'dept_ppt': dept, 'periods': {}}
            for period in all_periods:
                spending = spending_data[dept].get(period, Decimal(0))
                actual = actual_data[dept].get(period)
                if actual is not None and spending and spending != 0:
                    pct = float(actual / spending * 100)
                    row['periods'][period] = pct
                else:
                    row['periods'][period] = None
            heatmap.append(row)

        return {'rows': heatmap, 'periods': all_periods}


def get_category_mix_data(version, filters=None):
    """Section 3.5.5 - Category mix analysis."""
    with get_db() as session:
        qs = session.query(BsaMain.id).filter(BsaMain.version == version)
        if filters and filters.get('dept_ppt'):
            qs = qs.filter(BsaMain.dept_ppt == filters['dept_ppt'])

        main_ids = [r[0] for r in qs.all()]

        data = (
            session.query(BsaMain.dept_ppt, BsaMain.category, func.sum(BsaSpending.value).label('total'))
            .join(BsaSpending, BsaSpending.main_id == BsaMain.id)
            .filter(BsaSpending.main_id.in_(main_ids))
            .group_by(BsaMain.dept_ppt, BsaMain.category)
            .order_by(BsaMain.dept_ppt, BsaMain.category)
            .all()
        )

        dept_cat = defaultdict(lambda: defaultdict(Decimal))
        dept_total = defaultdict(Decimal)
        categories = set()

        for dept, cat, val in data:
            val = val or Decimal(0)
            dept_cat[dept][cat] = val
            dept_total[dept] += val
            categories.add(cat)

        categories = sorted(categories)
        rows = []
        for dept in sorted(dept_cat.keys()):
            row = {'dept_ppt': dept, 'total': dept_total[dept], 'categories': {}}
            for cat in categories:
                val = dept_cat[dept].get(cat, Decimal(0))
                pct = float(val / dept_total[dept] * 100) if dept_total[dept] else 0
                row['categories'][cat] = {'value': val, 'pct': pct}
            rows.append(row)

        return {'rows': rows, 'categories': categories}


def get_yoy_comparison(version1, version2):
    """Section 3.5.6 - Year-over-year comparison."""
    def _get_dept_totals(ver):
        with get_db() as session:
            main_ids = [r[0] for r in session.query(BsaMain.id).filter(BsaMain.version == ver).all()]
            totals = {}
            for dept, total in (
                session.query(BsaMain.dept_ppt, func.sum(BsaSpending.value))
                .join(BsaSpending, BsaSpending.main_id == BsaMain.id)
                .filter(BsaSpending.main_id.in_(main_ids))
                .group_by(BsaMain.dept_ppt)
                .all()
            ):
                totals[dept] = total or Decimal(0)
            return totals

    t1 = _get_dept_totals(version1)
    t2 = _get_dept_totals(version2)

    all_depts = sorted(set(list(t1.keys()) + list(t2.keys())))
    rows = []
    for dept in all_depts:
        v1 = t1.get(dept, Decimal(0))
        v2 = t2.get(dept, Decimal(0))
        change = v2 - v1
        pct = float(change / v1 * 100) if v1 else 0
        rows.append({
            'dept_ppt': dept,
            'v1': v1, 'v2': v2,
            'change': change, 'pct': pct,
        })

    return rows


def get_controllable_analysis(version):
    """Section 3.5.7 - Controllable vs Non-Controllable."""
    with get_db() as session:
        qs = session.query(BsaMain.id).filter(BsaMain.version == version)
        main_ids_ctrl = [r[0] for r in qs.filter(BsaMain.under_ops_control == 'Y').all()]
        main_ids_non = [r[0] for r in session.query(BsaMain.id).filter(
            BsaMain.version == version, BsaMain.under_ops_control != 'Y'
        ).all()]

        def _sum_by_dept(ids):
            result = {}
            for dept, total in (
                session.query(BsaMain.dept_ppt, func.sum(BsaSpending.value))
                .join(BsaSpending, BsaSpending.main_id == BsaMain.id)
                .filter(BsaSpending.main_id.in_(ids))
                .group_by(BsaMain.dept_ppt)
                .all()
            ):
                result[dept] = total or Decimal(0)
            return result

        ctrl = _sum_by_dept(main_ids_ctrl)
        non_ctrl = _sum_by_dept(main_ids_non)
        all_depts = sorted(set(list(ctrl.keys()) + list(non_ctrl.keys())))

        rows = []
        for dept in all_depts:
            c = ctrl.get(dept, Decimal(0))
            n = non_ctrl.get(dept, Decimal(0))
            total = c + n
            rows.append({
                'dept_ppt': dept,
                'controllable': c,
                'non_controllable': n,
                'total': total,
                'ctrl_pct': float(c / total * 100) if total else 0,
                'non_ctrl_pct': float(n / total * 100) if total else 0,
            })

        return rows


def get_budgeter_status(version):
    """Section 3.5.8 - Budgeter workload and submission status."""
    with get_db() as session:
        budgeters = (
            session.query(BsaMain.budgeter, func.count(BsaMain.id).label('total_entries'))
            .filter(BsaMain.version == version)
            .group_by(BsaMain.budgeter)
            .order_by(BsaMain.budgeter)
            .all()
        )

        rows = []
        for budgeter, total in budgeters:
            # Count entries with at least one spending value
            filled = (
                session.query(func.count(func.distinct(BsaSpending.main_id)))
                .join(BsaMain, BsaSpending.main_id == BsaMain.id)
                .filter(
                    BsaMain.version == version,
                    BsaMain.budgeter == budgeter,
                    BsaSpending.value.isnot(None),
                    BsaSpending.value != 0,
                )
                .scalar()
            ) or 0

            empty = total - filled
            pct = round(filled / total * 100) if total else 0

            rows.append({
                'budgeter': budgeter,
                'total': total,
                'filled': filled,
                'empty': empty,
                'pct': pct,
            })

        return rows
