"""Budget business logic services — SQLAlchemy version."""
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import func

from config.database import get_db
from apps.budget.models import (
    BsaMain, BsaVolumeActual, BsaVolume, BsaActual, BsaSpending,
    BsaRebaseFinanceview, BsaRebaseOpsview, BsaSaving, BsaNewadd,
    BsaNewaddApproved, BsaFinalBudget,
)
from apps.importer.validators import SCENARIO_ORDER, extract_scenario, DIMENSION_COLUMNS


def get_budget_data(version, filters=None, data_type='spending'):
    """
    Get budget data for the pivot table display.
    Returns a list of row dicts with dimension columns and period values.
    """
    with get_db() as session:
        qs = session.query(BsaMain).filter(BsaMain.version == version)

        if filters:
            if filters.get('area'):
                qs = qs.filter(BsaMain.area == filters['area'])
            if filters.get('dept'):
                qs = qs.filter(BsaMain.dept == filters['dept'])
            if filters.get('dept_ppt'):
                dept_ppt_list = filters.getlist('dept_ppt') if hasattr(filters, 'getlist') else [filters['dept_ppt']]
                qs = qs.filter(BsaMain.dept_ppt.in_(dept_ppt_list))
            if filters.get('category'):
                qs = qs.filter(BsaMain.category == filters['category'])
            if filters.get('budgeter'):
                qs = qs.filter(BsaMain.budgeter == filters['budgeter'])
            if filters.get('under_ops_control'):
                qs = qs.filter(BsaMain.under_ops_control == filters['under_ops_control'])
            if filters.get('spends_control'):
                qs = qs.filter(BsaMain.spends_control == filters['spends_control'])

        rows = []
        for main in qs.order_by(BsaMain.dept_ppt, BsaMain.category, BsaMain.accounts):
            row = {
                'id': main.id,
                'version': main.version,
                'dept_ppt': main.dept_ppt,
                'dept': main.dept,
                'dept_group': main.dept_group,
                'category': main.category,
                'cc': main.cc,
                'glc': main.glc,
                'accounts': main.accounts,
                'levels': main.levels,
                'budgeter': main.budgeter,
                'under_ops_control': main.under_ops_control,
                'at_var': main.at_var,
                'area': main.area,
                'data_type': main.data_type,
            }

            period_data = _get_period_data(session, main, data_type)
            row['periods'] = period_data
            rows.append(row)

        return rows


def _get_period_data(session, main, data_type):
    """Get period->value dict for a given data type."""
    model_map = {
        'spending': BsaSpending,
        'saving': BsaSaving,
        'newadd': BsaNewadd,
        'newadd_approved': BsaNewaddApproved,
        'final_budget': BsaFinalBudget,
        'rebase_financeview': BsaRebaseFinanceview,
        'rebase_opsview': BsaRebaseOpsview,
        'actual': BsaActual,
    }

    model = model_map.get(data_type)
    if not model:
        return {}

    objs = session.query(model).filter(model.main_id == main.id).all()
    return {obj.period: obj.value for obj in objs}


def get_all_periods(version, data_type='spending'):
    """Get sorted list of all periods for a data type in a version."""
    model_map = {
        'spending': BsaSpending,
        'saving': BsaSaving,
        'newadd': BsaNewadd,
        'newadd_approved': BsaNewaddApproved,
        'final_budget': BsaFinalBudget,
        'rebase_financeview': BsaRebaseFinanceview,
        'rebase_opsview': BsaRebaseOpsview,
        'actual': BsaActual,
        'volume_actual': BsaVolumeActual,
    }
    model = model_map.get(data_type)
    if not model:
        return []

    with get_db() as session:
        rows = (
            session.query(model.period)
            .join(BsaMain, model.main_id == BsaMain.id)
            .filter(BsaMain.version == version)
            .distinct()
            .order_by(model.period)
            .all()
        )
        return [r[0] for r in rows]


def get_filter_options(version):
    """Get distinct values for filter dropdowns."""
    with get_db() as session:
        qs = session.query(BsaMain).filter(BsaMain.version == version)

        def _distinct(col):
            return sorted([r[0] for r in qs.with_entities(col).distinct().all()])

        return {
            'areas': _distinct(BsaMain.area),
            'depts': _distinct(BsaMain.dept),
            'dept_ppts': _distinct(BsaMain.dept_ppt),
            'categories': _distinct(BsaMain.category),
            'budgeters': _distinct(BsaMain.budgeter),
        }


def get_summary_data(version, filters=None, data_type='spending', group_by='dept_ppt'):
    """Get aggregated summary data grouped by a dimension."""
    model_map = {
        'spending': BsaSpending,
        'rebase_financeview': BsaRebaseFinanceview,
        'rebase_opsview': BsaRebaseOpsview,
        'actual': BsaActual,
        'saving': BsaSaving,
        'newadd': BsaNewadd,
    }
    model = model_map.get(data_type)
    if not model:
        return {}

    group_col = getattr(BsaMain, group_by)

    with get_db() as session:
        qs = session.query(BsaMain.id).filter(BsaMain.version == version)
        if filters:
            if filters.get('under_ops_control'):
                qs = qs.filter(BsaMain.under_ops_control == filters['under_ops_control'])

        main_ids = [r[0] for r in qs.all()]

        agg = (
            session.query(group_col, model.period, func.sum(model.value).label('total'))
            .join(BsaMain, model.main_id == BsaMain.id)
            .filter(model.main_id.in_(main_ids))
            .group_by(group_col, model.period)
            .order_by(group_col, model.period)
            .all()
        )

        result = defaultdict(dict)
        for group, period, total in agg:
            result[group][period] = total

        return dict(result)


def save_cell(session, table_name, main_id, period, new_value, user, ip_address=None, scenario=None):
    """
    Save a single cell value and handle cascade calculations.
    Returns dict with status and updated values.
    """
    model_map = {
        'bsa_spending': BsaSpending,
        'bsa_saving': BsaSaving,
        'bsa_newadd': BsaNewadd,
        'bsa_newadd_approved': BsaNewaddApproved,
        'bsa_final_budget': BsaFinalBudget,
        'bsa_rebase_financeview': BsaRebaseFinanceview,
        'bsa_rebase_opsview': BsaRebaseOpsview,
    }

    main = session.get(BsaMain, main_id)
    if not main:
        return {'status': 'error', 'message': 'Record not found'}

    # Volume has a special 3-field unique constraint (main, scenario, period)
    if table_name == 'bsa_volume':
        if not scenario:
            return {'status': 'error', 'message': 'scenario is required for volume edits'}
        obj = session.query(BsaVolume).filter_by(main_id=main.id, scenario=scenario, period=period).first()
        if obj:
            obj.value = new_value
        else:
            obj = BsaVolume(main_id=main.id, scenario=scenario, period=period, value=new_value)
            session.add(obj)
        session.flush()
        result = {'status': 'ok'}
        updated_rfv = _recalc_rebase_financeview(session, main, period)
        result['updated_rebase'] = str(updated_rfv) if updated_rfv is not None else None
        return result

    model = model_map.get(table_name)
    if not model:
        return {'status': 'error', 'message': f'Unknown table: {table_name}'}

    obj = session.query(model).filter_by(main_id=main.id, period=period).first()
    if obj:
        obj.value = new_value
    else:
        obj = model(main_id=main.id, period=period, value=new_value)
        session.add(obj)
    session.flush()

    result = {'status': 'ok'}

    # Cascade: recalculate rebase_financeview when spending, saving, or newadd changes
    if table_name in ('bsa_spending', 'bsa_saving', 'bsa_newadd'):
        updated_rfv = _recalc_rebase_financeview(session, main, period)
        result['updated_rebase'] = str(updated_rfv) if updated_rfv is not None else None

    # Cascade: recalculate final_budget when newadd, newadd_approved, or saving changes
    if table_name in ('bsa_newadd', 'bsa_newadd_approved', 'bsa_saving'):
        updated_fb = _recalc_final_budget(session, main, period)
        result['updated_final_budget'] = str(updated_fb) if updated_fb is not None else None

    return result


def _recalc_rebase_financeview(session, main, period):
    """
    Recalculate rebase_financeview for a specific main+period.
    Formula (3.4.5 + 3.4.9):
      base = spending * [(1-at_var) + at_var * (vol_prev/vol_curr)]
      final = base - saving + newadd
    """
    version = main.version
    scenario = extract_scenario(version)
    prev_scenario = SCENARIO_ORDER.get(scenario)

    spending_obj = session.query(BsaSpending).filter_by(main_id=main.id, period=period).first()
    if not spending_obj or spending_obj.value is None:
        return None

    spending_val = spending_obj.value
    at_var = main.at_var or Decimal(0)
    under_ops = main.under_ops_control

    if under_ops != 'Y' or not prev_scenario:
        base_rebase = spending_val
    else:
        vol_prev_obj = session.query(BsaVolume).filter_by(main_id=main.id, scenario=prev_scenario, period=period).first()
        vol_curr_obj = session.query(BsaVolume).filter_by(main_id=main.id, scenario=scenario, period=period).first()

        vp = vol_prev_obj.value if vol_prev_obj else None
        vc = vol_curr_obj.value if vol_curr_obj else None

        if vc is None or vc == 0:
            base_rebase = spending_val
        elif vp is None or vp == 0:
            base_rebase = spending_val * (1 - at_var)
        else:
            ratio = vp / vc
            base_rebase = spending_val * ((1 - at_var) + at_var * ratio)

    # Apply saving/newadd adjustments (3.4.9)
    saving_obj = session.query(BsaSaving).filter_by(main_id=main.id, period=period).first()
    saving_val = saving_obj.value if saving_obj and saving_obj.value is not None else Decimal(0)

    newadd_obj = session.query(BsaNewadd).filter_by(main_id=main.id, period=period).first()
    newadd_val = newadd_obj.value if newadd_obj and newadd_obj.value is not None else Decimal(0)

    final_rebase = base_rebase - saving_val + newadd_val

    # Update or create
    rfv = session.query(BsaRebaseFinanceview).filter_by(main_id=main.id, period=period).first()
    if rfv:
        rfv.value = final_rebase
    else:
        rfv = BsaRebaseFinanceview(main_id=main.id, period=period, value=final_rebase)
        session.add(rfv)
    session.flush()

    return final_rebase


def _recalc_rebase_opsview(session, main, period):
    """
    Recalculate rebase_opsview for a specific main+period.
    Formula (3.4.6): weighted average of actuals.
    """
    at_var = main.at_var or Decimal(0)
    under_ops = main.under_ops_control
    baseline_adj = main.baseline_adjustment or Decimal(0)

    # Get first 3 actual periods for weighted average
    actual_periods = [
        r[0] for r in session.query(BsaActual.period)
        .filter(BsaActual.main_id == main.id)
        .distinct()
        .order_by(BsaActual.period)
        .limit(3)
        .all()
    ]
    if not actual_periods:
        return None

    WEIGHTS = [4, 4, 5]
    actual_vals = []
    vol_actual_vals = []
    for p in actual_periods:
        a_obj = session.query(BsaActual).filter_by(main_id=main.id, period=p).first()
        actual_vals.append(a_obj.value if a_obj and a_obj.value is not None else Decimal(0))
        va_obj = session.query(BsaVolumeActual).filter_by(main_id=main.id, period=p).first()
        vol_actual_vals.append(va_obj.value if va_obj and va_obj.value is not None else Decimal(0))

    weights = WEIGHTS[:len(actual_vals)]
    weight_sum = sum(weights)
    if weight_sum == 0:
        return None

    actual_wavg = sum(v * w for v, w in zip(actual_vals, weights)) / weight_sum

    if under_ops != 'Y':
        value = actual_wavg
    else:
        vol_actual_wavg = sum(v * w for v, w in zip(vol_actual_vals, weights)) / weight_sum
        adjusted_base = actual_wavg - baseline_adj
        fixed_part = (1 - at_var) * adjusted_base

        if vol_actual_wavg == 0:
            variable_part = Decimal(0)
        else:
            unit_cost = actual_wavg / vol_actual_wavg
            variable_part = at_var * unit_cost * adjusted_base

        value = fixed_part + variable_part

    rov = session.query(BsaRebaseOpsview).filter_by(main_id=main.id, period=period).first()
    if rov:
        rov.value = value
    else:
        rov = BsaRebaseOpsview(main_id=main.id, period=period, value=value)
        session.add(rov)
    session.flush()

    return value


def _recalc_final_budget(session, main, period):
    """
    Recalculate final_budget for a specific main+period.
    Formula: rebase_opsview + newadd + newadd_approved - saving
    """
    rov_obj = session.query(BsaRebaseOpsview).filter_by(main_id=main.id, period=period).first()
    rov_val = rov_obj.value if rov_obj and rov_obj.value is not None else Decimal(0)

    newadd_obj = session.query(BsaNewadd).filter_by(main_id=main.id, period=period).first()
    newadd_val = newadd_obj.value if newadd_obj and newadd_obj.value is not None else Decimal(0)

    naa_obj = session.query(BsaNewaddApproved).filter_by(main_id=main.id, period=period).first()
    naa_val = naa_obj.value if naa_obj and naa_obj.value is not None else Decimal(0)

    saving_obj = session.query(BsaSaving).filter_by(main_id=main.id, period=period).first()
    saving_val = saving_obj.value if saving_obj and saving_obj.value is not None else Decimal(0)

    final_val = rov_val + newadd_val + naa_val - saving_val

    fb = session.query(BsaFinalBudget).filter_by(main_id=main.id, period=period).first()
    if fb:
        fb.value = final_val
    else:
        fb = BsaFinalBudget(main_id=main.id, period=period, value=final_val)
        session.add(fb)
    session.flush()

    return final_val


def recalc_all_rebase(version):
    """
    Batch recalculate ALL rebase_financeview and rebase_opsview values for a version.
    """
    scenario = extract_scenario(version)
    prev_scenario = SCENARIO_ORDER.get(scenario)

    with get_db() as session:
        main_list = session.query(BsaMain).filter(BsaMain.version == version).all()
        if not main_list:
            return 0

        main_ids = [m.id for m in main_list]

        # Pre-load all sub-table data: {main_id: {period: value}}
        def _load(model, extra_filter=None):
            q = session.query(model.main_id, model.period, model.value).filter(model.main_id.in_(main_ids))
            if extra_filter:
                for col, val in extra_filter.items():
                    q = q.filter(getattr(model, col) == val)
            data = defaultdict(dict)
            for mid, period, value in q.all():
                data[mid][period] = value
            return data

        spending_data = _load(BsaSpending)
        saving_data = _load(BsaSaving)
        newadd_data = _load(BsaNewadd)
        newadd_approved_data = _load(BsaNewaddApproved)
        actual_data = _load(BsaActual)
        vol_actual_data = _load(BsaVolumeActual)

        # Volume by scenario
        vol_prev_data = defaultdict(dict)
        vol_curr_data = defaultdict(dict)
        if prev_scenario:
            vol_prev_data = _load(BsaVolume, {'scenario': prev_scenario})
        vol_curr_data = _load(BsaVolume, {'scenario': scenario})

        # Collect all spending periods and actual periods
        spending_periods = set()
        for mid_periods in spending_data.values():
            spending_periods.update(mid_periods.keys())

        actual_periods_set = set()
        for mid_periods in actual_data.values():
            actual_periods_set.update(mid_periods.keys())

        actual_periods_sorted = sorted(actual_periods_set)[:3]
        WEIGHTS = [4, 4, 5]

        # Rebase financeview periods
        existing_rfv_periods = set()
        for mid, period in session.query(BsaRebaseFinanceview.main_id, BsaRebaseFinanceview.period).filter(
            BsaRebaseFinanceview.main_id.in_(main_ids)
        ).all():
            existing_rfv_periods.add(period)
        rfv_periods = spending_periods | existing_rfv_periods

        existing_rov_periods = set()
        for mid, period in session.query(BsaRebaseOpsview.main_id, BsaRebaseOpsview.period).filter(
            BsaRebaseOpsview.main_id.in_(main_ids)
        ).all():
            existing_rov_periods.add(period)
        rov_periods = rfv_periods | existing_rov_periods

        updated_count = 0

        for main in main_list:
            mid = main.id
            at_var = main.at_var or Decimal(0)
            under_ops = main.under_ops_control
            baseline_adj = main.baseline_adjustment or Decimal(0)

            # === Rebase Finance View (3.4.5 + 3.4.9) ===
            for period in rfv_periods:
                spending_val = spending_data.get(mid, {}).get(period)
                if spending_val is None:
                    continue

                if under_ops != 'Y' or not prev_scenario:
                    base_rebase = spending_val
                else:
                    vp = vol_prev_data.get(mid, {}).get(period)
                    vc = vol_curr_data.get(mid, {}).get(period)

                    if vc is None or vc == 0:
                        base_rebase = spending_val
                    elif vp is None or vp == 0:
                        base_rebase = spending_val * (1 - at_var)
                    else:
                        ratio = vp / vc
                        base_rebase = spending_val * ((1 - at_var) + at_var * ratio)

                saving_val = saving_data.get(mid, {}).get(period) or Decimal(0)
                newadd_val = newadd_data.get(mid, {}).get(period) or Decimal(0)
                final_rfv = base_rebase - saving_val + newadd_val

                rfv = session.query(BsaRebaseFinanceview).filter_by(main_id=mid, period=period).first()
                if rfv:
                    rfv.value = final_rfv
                else:
                    session.add(BsaRebaseFinanceview(main_id=mid, period=period, value=final_rfv))
                updated_count += 1

            # === Rebase Ops View (3.4.6) ===
            if actual_periods_sorted:
                actual_vals = []
                vol_actual_vals = []
                for p in actual_periods_sorted:
                    actual_vals.append(actual_data.get(mid, {}).get(p) or Decimal(0))
                    vol_actual_vals.append(vol_actual_data.get(mid, {}).get(p) or Decimal(0))

                weights = WEIGHTS[:len(actual_vals)]
                weight_sum = sum(weights)

                if weight_sum > 0:
                    actual_wavg = sum(v * w for v, w in zip(actual_vals, weights)) / weight_sum

                    if under_ops != 'Y':
                        ov_value = actual_wavg
                    else:
                        vol_actual_wavg = sum(v * w for v, w in zip(vol_actual_vals, weights)) / weight_sum
                        adjusted_base = actual_wavg - baseline_adj
                        fixed_part = (1 - at_var) * adjusted_base

                        if vol_actual_wavg == 0:
                            variable_part = Decimal(0)
                        else:
                            unit_cost = actual_wavg / vol_actual_wavg
                            variable_part = at_var * unit_cost * adjusted_base

                        ov_value = fixed_part + variable_part

                    for period in rov_periods:
                        rov = session.query(BsaRebaseOpsview).filter_by(main_id=mid, period=period).first()
                        if rov:
                            rov.value = ov_value
                        else:
                            session.add(BsaRebaseOpsview(main_id=mid, period=period, value=ov_value))
                        updated_count += 1

            # === Final Budget = rebase_opsview + newadd + newadd_approved - saving ===
            for period in rov_periods:
                rov = session.query(BsaRebaseOpsview).filter_by(main_id=mid, period=period).first()
                rov_val = rov.value if rov and rov.value is not None else Decimal(0)
                na_val = newadd_data.get(mid, {}).get(period) or Decimal(0)
                naa_val = newadd_approved_data.get(mid, {}).get(period) or Decimal(0)
                sav_val = saving_data.get(mid, {}).get(period) or Decimal(0)
                fb_val = rov_val + na_val + naa_val - sav_val

                fb = session.query(BsaFinalBudget).filter_by(main_id=mid, period=period).first()
                if fb:
                    fb.value = fb_val
                else:
                    session.add(BsaFinalBudget(main_id=mid, period=period, value=fb_val))

        return updated_count


def _apply_filters(qs, filters):
    """Apply common filters to a BsaMain query."""
    if not filters:
        return qs
    if filters.get('area'):
        qs = qs.filter(BsaMain.area == filters['area'])
    if filters.get('dept_ppt'):
        dept_ppt_list = filters.getlist('dept_ppt') if hasattr(filters, 'getlist') else [filters['dept_ppt']]
        qs = qs.filter(BsaMain.dept_ppt.in_(dept_ppt_list))
    if filters.get('category'):
        qs = qs.filter(BsaMain.category == filters['category'])
    if filters.get('budgeter'):
        qs = qs.filter(BsaMain.budgeter == filters['budgeter'])
    return qs


def get_overall_data(version, filters=None):
    """
    Get all data in a flat CSV-like format.
    Returns {'headers': [...], 'rows': [[val, ...], ...], 'dimension_count': int}
    """
    scenario = extract_scenario(version)
    prev_scenario = SCENARIO_ORDER.get(scenario, '')

    with get_db() as session:
        qs = _apply_filters(
            session.query(BsaMain).filter(BsaMain.version == version),
            filters,
        )
        main_list = list(qs.order_by(BsaMain.dept_ppt, BsaMain.category, BsaMain.accounts).all())
        main_ids = [m.id for m in main_list]

        if not main_ids:
            return {'headers': DIMENSION_COLUMNS, 'rows': [], 'dimension_count': len(DIMENSION_COLUMNS)}

        def _periods(model, extra_filter=None):
            q = session.query(model.period).filter(model.main_id.in_(main_ids))
            if extra_filter:
                for col, val in extra_filter.items():
                    q = q.filter(getattr(model, col) == val)
            return sorted([r[0] for r in q.distinct().all()])

        vol_actual_periods = _periods(BsaVolumeActual)
        vol_prev_periods = _periods(BsaVolume, {'scenario': prev_scenario}) if prev_scenario else []
        vol_curr_periods = _periods(BsaVolume, {'scenario': scenario})
        actual_periods = _periods(BsaActual)
        spending_periods = _periods(BsaSpending)
        rebase_fv_periods = _periods(BsaRebaseFinanceview)
        rebase_ov_periods = _periods(BsaRebaseOpsview)
        saving_periods = _periods(BsaSaving)
        newadd_periods = _periods(BsaNewadd)
        newadd_approved_periods = _periods(BsaNewaddApproved)
        final_budget_periods = _periods(BsaFinalBudget)

        # Build headers
        headers = list(DIMENSION_COLUMNS)
        for p in vol_actual_periods:
            headers.append(f'volume_actual_{p}')
        if prev_scenario:
            for p in vol_prev_periods:
                headers.append(f'volume_{prev_scenario}_{p}')
        for p in vol_curr_periods:
            headers.append(f'volume_{scenario}_{p}')
        for p in actual_periods:
            headers.append(f'actual_{p}')
        for p in spending_periods:
            headers.append(f'spending_{p}')
        for p in rebase_fv_periods:
            headers.append(f'rebase_financeview_{p}')
        for p in rebase_ov_periods:
            headers.append(f'rebase_opsview_{p}')
        for p in saving_periods:
            headers.append(f'saving_{p}')
        for p in newadd_periods:
            headers.append(f'newadd_{p}')
        for p in newadd_approved_periods:
            headers.append(f'newadd_approved_{p}')
        for p in final_budget_periods:
            headers.append(f'final_budget_{p}')

        # Pre-load all sub-table data
        def _load(model, extra_filter=None):
            q = session.query(model.main_id, model.period, model.value).filter(model.main_id.in_(main_ids))
            if extra_filter:
                for col, val in extra_filter.items():
                    q = q.filter(getattr(model, col) == val)
            data = defaultdict(dict)
            for mid, period, value in q.all():
                data[mid][period] = value
            return data

        va_data = _load(BsaVolumeActual)
        vp_data = _load(BsaVolume, {'scenario': prev_scenario}) if prev_scenario else {}
        vc_data = _load(BsaVolume, {'scenario': scenario})
        act_data = _load(BsaActual)
        sp_data = _load(BsaSpending)
        rfv_data = _load(BsaRebaseFinanceview)
        rov_data = _load(BsaRebaseOpsview)
        sav_data = _load(BsaSaving)
        na_data = _load(BsaNewadd)
        naa_data = _load(BsaNewaddApproved)
        fb_data = _load(BsaFinalBudget)

        # Build rows
        rows = []
        for m in main_list:
            row = [
                m.version, m.data_type, m.under_ops_control,
                str(m.ccgl) if m.ccgl else '',
                m.glc, m.cc,
                m.non_controllable, m.area, m.dept, m.dept_group, m.dept_ppt,
                m.category, m.discretionary, m.at_var, m.self_study_var,
                m.spends_control, m.iecs_view, m.levels, m.accounts, m.budgeter,
                m.baseline_adjustment,
            ]
            mid = m.id
            for p in vol_actual_periods:
                row.append(va_data.get(mid, {}).get(p))
            for p in vol_prev_periods:
                row.append(vp_data.get(mid, {}).get(p) if vp_data else None)
            for p in vol_curr_periods:
                row.append(vc_data.get(mid, {}).get(p))
            for p in actual_periods:
                row.append(act_data.get(mid, {}).get(p))
            for p in spending_periods:
                row.append(sp_data.get(mid, {}).get(p))
            for p in rebase_fv_periods:
                row.append(rfv_data.get(mid, {}).get(p))
            for p in rebase_ov_periods:
                row.append(rov_data.get(mid, {}).get(p))
            for p in saving_periods:
                row.append(sav_data.get(mid, {}).get(p))
            for p in newadd_periods:
                row.append(na_data.get(mid, {}).get(p))
            for p in newadd_approved_periods:
                row.append(naa_data.get(mid, {}).get(p))
            for p in final_budget_periods:
                row.append(fb_data.get(mid, {}).get(p))
            rows.append(row)

        return {
            'headers': headers,
            'rows': rows,
            'dimension_count': len(DIMENSION_COLUMNS),
        }
