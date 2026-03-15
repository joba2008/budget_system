"""CSV/Excel import service — SQLAlchemy version."""
import csv
import io
import json
from decimal import Decimal, InvalidOperation

import pandas as pd

from config.database import get_db
from apps.budget.models import (
    BsaMain, BsaVolumeActual, BsaVolume, BsaActual, BsaSpending,
    BsaRebaseFinanceview, BsaRebaseOpsview, BsaSaving, BsaNewadd,
    BsaNewaddApproved, BsaFinalBudget,
)

from apps.importer.validators import (
    DIMENSION_COLUMNS, SCENARIO_ORDER, extract_scenario, validate_import_data,
)


def to_decimal(val):
    """Convert a value to Decimal, returning None for empty/invalid values."""
    if val is None or (isinstance(val, str) and val.strip() == ''):
        return None
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return None


def parse_csv_file(file_obj):
    """Parse uploaded CSV file and return (headers, rows)."""
    content = file_obj.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def parse_excel_file(file_obj):
    """Parse uploaded Excel file and return (headers, rows)."""
    df = pd.read_excel(file_obj, dtype=str, keep_default_na=False)
    headers = list(df.columns)
    rows = df.to_dict('records')
    return headers, rows


def get_import_preview(headers, rows, version):
    """Generate preview summary of import data."""
    depts = set()
    budgeters = set()
    categories = set()
    for row in rows:
        depts.add(row.get('dept_ppt', row.get('dept', '')))
        budgeters.add(row.get('budgeter', ''))
        categories.add(row.get('category', ''))

    spending_cols = [h for h in headers if h.startswith('spending_')]
    vol_cols = [h for h in headers if h.startswith('volume_') and not h.startswith('volume_actual_')]

    return {
        'total_rows': len(rows),
        'version': version,
        'departments': sorted(depts - {''}),
        'budgeters': sorted(budgeters - {''}),
        'categories': sorted(categories - {''}),
        'spending_periods': len(spending_cols),
        'volume_columns': len(vol_cols),
    }


def classify_columns(headers):
    """Classify columns into their data categories."""
    result = {
        'dimension': [],
        'volume_actual': [],
        'volume': {},  # scenario -> [(col_name, period)]
        'actual': [],
        'spending': [],
        'rebase_financeview': [],
        'rebase_opsview': [],
        'saving': [],
        'newadd': [],
        'newadd_approved': [],
        'final_budget': [],
    }

    for h in headers:
        if h in DIMENSION_COLUMNS:
            result['dimension'].append(h)
        elif h.startswith('volume_actual_'):
            period = h.replace('volume_actual_', '')
            result['volume_actual'].append((h, period))
        elif h.startswith('volume_'):
            parts = h.split('_', 2)
            if len(parts) >= 3:
                scenario = parts[1]
                period = parts[2]
                result['volume'].setdefault(scenario, []).append((h, period))
        elif h.startswith('actual_'):
            period = h.replace('actual_', '')
            result['actual'].append((h, period))
        elif h.startswith('spending_'):
            period = h.replace('spending_', '')
            result['spending'].append((h, period))
        elif h.startswith('rebase_financeview_'):
            period = h.replace('rebase_financeview_', '')
            result['rebase_financeview'].append((h, period))
        elif h.startswith('rebase_opsview_'):
            period = h.replace('rebase_opsview_', '')
            result['rebase_opsview'].append((h, period))
        elif h.startswith('saving_'):
            period = h.replace('saving_', '')
            result['saving'].append((h, period))
        elif h.startswith('newadd_approved_'):
            period = h.replace('newadd_approved_', '')
            result['newadd_approved'].append((h, period))
        elif h.startswith('newadd_'):
            period = h.replace('newadd_', '')
            result['newadd'].append((h, period))
        elif h.startswith('final_budget_'):
            period = h.replace('final_budget_', '')
            result['final_budget'].append((h, period))

    return result


def calc_rebase_financeview(row, version, spending_periods, col_map):
    """Calculate rebase_financeview values for a row (section 3.4.5)."""
    current_scenario = extract_scenario(version)
    prev_scenario = SCENARIO_ORDER.get(current_scenario)
    if not prev_scenario:
        return {}

    at_var = to_decimal(row.get('at_var')) or Decimal(0)
    under_ops = row.get('under_ops_control', '').strip()

    # Build volume lookup dicts
    vol_prev = {}
    vol_curr = {}
    for scenario, cols in col_map['volume'].items():
        for col_name, period in cols:
            if scenario == prev_scenario:
                vol_prev[period] = to_decimal(row.get(col_name))
            elif scenario == current_scenario:
                vol_curr[period] = to_decimal(row.get(col_name))

    results = {}
    for col_name, period in spending_periods:
        spending_val = to_decimal(row.get(col_name))
        if spending_val is None:
            results[period] = None
            continue

        if under_ops != 'Y':
            results[period] = spending_val
        else:
            vp = vol_prev.get(period)
            vc = vol_curr.get(period)

            if vc is None or vc == 0:
                results[period] = spending_val
            elif vp is None or vp == 0:
                results[period] = spending_val * (1 - at_var)
            else:
                ratio = vp / vc
                results[period] = spending_val * ((1 - at_var) + at_var * ratio)

    return results


def calc_rebase_opsview(row, col_map):
    """Calculate rebase_opsview values for a row (section 3.4.6)."""
    WEIGHTS = [4, 4, 5]

    actual_periods = col_map['actual'][:3]
    vol_actual_periods = col_map['volume_actual'][:3]
    output_periods = col_map['rebase_opsview']

    if not actual_periods:
        return {}

    # Actual weighted average
    actual_vals = []
    for col_name, period in actual_periods:
        actual_vals.append(to_decimal(row.get(col_name)) or Decimal(0))

    weights = WEIGHTS[:len(actual_vals)]
    weight_sum = sum(weights)
    if weight_sum == 0:
        return {}

    actual_wavg = sum(v * w for v, w in zip(actual_vals, weights)) / weight_sum

    under_ops = row.get('under_ops_control', '').strip()
    at_var = to_decimal(row.get('at_var')) or Decimal(0)
    baseline_adj = to_decimal(row.get('baseline_adjustment')) or Decimal(0)

    if under_ops != 'Y':
        value = actual_wavg
    else:
        # Volume actual weighted average
        vol_vals = []
        for col_name, period in vol_actual_periods[:len(actual_vals)]:
            vol_vals.append(to_decimal(row.get(col_name)) or Decimal(0))

        vol_actual_wavg = sum(v * w for v, w in zip(vol_vals, weights)) / weight_sum

        adjusted_base = actual_wavg - baseline_adj
        fixed_part = (1 - at_var) * adjusted_base

        if vol_actual_wavg == 0:
            variable_part = Decimal(0)
        else:
            unit_cost = actual_wavg / vol_actual_wavg
            variable_part = at_var * unit_cost * adjusted_base

        value = fixed_part + variable_part

    return {period: value for _, period in output_periods}


def execute_import(headers, rows, user, file_name='', file_size=0):
    """Execute the actual data import within a transaction."""
    col_map = classify_columns(headers)
    version = rows[0].get('version', '') if rows else ''

    success_count = 0
    error_details = []

    with get_db() as session:
        for row_idx, row in enumerate(rows, start=2):
            try:
                # Create main record
                main = BsaMain(
                    version=row.get('version', ''),
                    data_type=row.get('data_type', ''),
                    under_ops_control=row.get('under_ops_control', ''),
                    ccgl=row.get('ccgl', ''),
                    glc=row.get('glc', ''),
                    cc=row.get('cc', ''),
                    non_controllable=row.get('non_controllable', ''),
                    area=row.get('area', ''),
                    dept=row.get('dept', ''),
                    dept_group=row.get('dept_group', ''),
                    dept_ppt=row.get('dept_ppt', ''),
                    category=row.get('category', ''),
                    discretionary=row.get('discretionary', ''),
                    at_var=to_decimal(row.get('at_var')),
                    self_study_var=to_decimal(row.get('self_study_var')),
                    spends_control=row.get('spends_control', ''),
                    iecs_view=row.get('iecs_view', ''),
                    levels=row.get('levels', ''),
                    accounts=row.get('accounts', ''),
                    budgeter=row.get('budgeter', ''),
                    baseline_adjustment=to_decimal(row.get('baseline_adjustment')),
                )
                session.add(main)
                session.flush()  # Get main.id

                # Volume Actual
                bulk = []
                for col_name, period in col_map['volume_actual']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaVolumeActual(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Volume (by scenario)
                bulk = []
                for scenario, cols in col_map['volume'].items():
                    for col_name, period in cols:
                        val = to_decimal(row.get(col_name))
                        bulk.append(BsaVolume(main_id=main.id, scenario=scenario, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Actual
                bulk = []
                for col_name, period in col_map['actual']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaActual(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Spending
                bulk = []
                for col_name, period in col_map['spending']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaSpending(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Calculate and store Rebase Finance View
                rebase_fv = calc_rebase_financeview(row, version, col_map['spending'], col_map)

                # Apply saving/newadd adjustments
                saving_by_period = {}
                for col_name, period in col_map['saving']:
                    saving_by_period[period] = to_decimal(row.get(col_name)) or Decimal(0)
                newadd_by_period = {}
                for col_name, period in col_map['newadd']:
                    newadd_by_period[period] = to_decimal(row.get(col_name)) or Decimal(0)

                bulk = []
                for period, val in rebase_fv.items():
                    if val is not None:
                        adjusted = val - saving_by_period.get(period, Decimal(0)) + newadd_by_period.get(period, Decimal(0))
                        bulk.append(BsaRebaseFinanceview(main_id=main.id, period=period, value=adjusted))
                    else:
                        bulk.append(BsaRebaseFinanceview(main_id=main.id, period=period, value=None))
                if bulk:
                    session.add_all(bulk)

                # Calculate and store Rebase Ops View
                rebase_ov = calc_rebase_opsview(row, col_map)
                bulk = []
                for period, val in rebase_ov.items():
                    bulk.append(BsaRebaseOpsview(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Saving
                bulk = []
                for col_name, period in col_map['saving']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaSaving(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # NewAdd
                bulk = []
                for col_name, period in col_map['newadd']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaNewadd(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # NewAdd Approved
                bulk = []
                for col_name, period in col_map['newadd_approved']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaNewaddApproved(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                # Final Budget
                bulk = []
                for col_name, period in col_map['final_budget']:
                    val = to_decimal(row.get(col_name))
                    bulk.append(BsaFinalBudget(main_id=main.id, period=period, value=val))
                if bulk:
                    session.add_all(bulk)

                success_count += 1

            except Exception as e:
                error_details.append(f'Row {row_idx}: {str(e)}')

    return {
        'version': version,
        'file_name': file_name,
        'total_rows': len(rows),
        'success_rows': success_count,
        'failed_rows': len(error_details),
        'error_details': error_details,
    }


def generate_csv_template(version_name):
    """Generate CSV template headers and a demo data row for a given version."""
    scenario = extract_scenario(version_name)
    prev_scenario = SCENARIO_ORDER.get(scenario, '')
    fy = version_name.split('-')[0] if '-' in version_name else 'fy26'
    fy_num = int(fy.replace('fy', ''))

    # Generate period strings
    fy_start_year = 2000 + fy_num - 1  # fy26 -> 2025
    fy_next_year = fy_start_year + 1

    actual_months = [
        (fy_start_year, m) for m in [9, 10, 11, 12]
    ]
    spending_months = [
        (fy_next_year, m) for m in range(1, 9)
    ] + [
        (fy_next_year, m) for m in range(9, 13)
    ] + [
        (fy_next_year + 1, m) for m in range(1, 9)
    ]

    def period_str(fy_label, year, month):
        return f'{fy_label}_{year}{month:02d}'

    def get_fy_label(year, month):
        if month >= 9:
            return f'fy{(year - 2000 + 1):02d}'
        else:
            return f'fy{(year - 2000):02d}'

    headers = list(DIMENSION_COLUMNS)

    # Volume actual
    vol_actual_count = 0
    for year, month in actual_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'volume_actual_{fy_label}_{year}{month:02d}')
        vol_actual_count += 1

    # Volume prev scenario
    vol_prev_count = 0
    if prev_scenario:
        for year, month in spending_months:
            fy_label = get_fy_label(year, month)
            headers.append(f'volume_{prev_scenario}_{fy_label}_{year}{month:02d}')
            vol_prev_count += 1

    # Volume current scenario
    vol_curr_count = 0
    for year, month in spending_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'volume_{scenario}_{fy_label}_{year}{month:02d}')
        vol_curr_count += 1

    # Actual
    actual_count = 0
    for year, month in actual_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'actual_{fy_label}_{year}{month:02d}')
        actual_count += 1

    # Spending
    spending_count = 0
    for year, month in spending_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'spending_{fy_label}_{year}{month:02d}')
        spending_count += 1

    # Rebase financeview
    rebase_months = [(actual_months[-1][0], actual_months[-1][1])] + spending_months
    rebase_count = 0
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'rebase_financeview_{fy_label}_{year}{month:02d}')
        rebase_count += 1

    # Rebase opsview
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'rebase_opsview_{fy_label}_{year}{month:02d}')

    # Saving
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'saving_{fy_label}_{year}{month:02d}')

    # NewAdd
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'newadd_{fy_label}_{year}{month:02d}')

    # NewAdd Approved
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'newadd_approved_{fy_label}_{year}{month:02d}')

    # Final Budget
    for year, month in rebase_months:
        fy_label = get_fy_label(year, month)
        headers.append(f'final_budget_{fy_label}_{year}{month:02d}')

    # --- Build demo row ---
    demo = {
        'version': version_name,
        'data_type': 'Data',
        'under_ops_control': 'Y',
        'ccgl': '692225515100',
        'glc': '515100',
        'cc': '692225',
        'non_controllable': '',
        'area': 'MOD',
        'dept': 'MFG',
        'dept_group': 'MFG',
        'dept_ppt': 'Mod MFG',
        'category': 'Indirect Labor',
        'discretionary': '',
        'at_var': '0.05',
        'self_study_var': '',
        'spends_control': 'Y',
        'iecs_view': 'Y',
        'levels': 'Level 3',
        'accounts': 'Indirect Labor - Regular',
        'budgeter': 'demo_user',
        'baseline_adjustment': '500',
    }
    demo_row = [demo.get(col, '') for col in DIMENSION_COLUMNS]

    demo_row += ['20000', '22000', '21000', '23000'][:vol_actual_count]
    demo_row += ['22000'] * vol_prev_count
    demo_row += ['24000'] * vol_curr_count
    demo_row += ['10000', '12000', '11000', '13000'][:actual_count]
    demo_row += ['9978.47'] * spending_count
    demo_row += ['0'] * rebase_count
    demo_row += ['0'] * rebase_count
    demo_row += ['500'] * rebase_count
    demo_row += ['0'] * rebase_count
    demo_row += ['0'] * rebase_count
    demo_row += ['0'] * rebase_count

    return headers, demo_row
