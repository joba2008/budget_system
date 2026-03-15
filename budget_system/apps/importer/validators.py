"""CSV/Excel import validation logic."""
from decimal import Decimal, InvalidOperation

SCENARIO_ORDER = {'B1': 'A1', 'C1': 'B1', 'D1': 'C1', 'A1': 'D1'}

REQUIRED_FIELDS = ['version', 'area', 'dept', 'cc', 'glc', 'accounts', 'budgeter']

DIMENSION_COLUMNS = [
    'version', 'data_type', 'under_ops_control', 'ccgl', 'glc', 'cc',
    'non_controllable', 'area', 'dept', 'dept_group', 'dept_ppt', 'category',
    'discretionary', 'at_var', 'self_study_var', 'spends_control', 'iecs_view',
    'levels', 'accounts', 'budgeter', 'baseline_adjustment'
]


def extract_scenario(version):
    """Extract scenario from version string e.g. 'fy26-B1' -> 'B1'."""
    parts = version.split('-')
    if len(parts) >= 2:
        return parts[-1].upper()
    return ''


def validate_csv_headers(headers):
    """Validate that all required dimension columns are present."""
    errors = []
    for col in DIMENSION_COLUMNS:
        if col not in headers:
            errors.append(f'Missing required column: {col}')
    return errors


def validate_required_fields(row_idx, row_dict):
    """Validate required fields are not empty for a data row."""
    errors = []
    for field in REQUIRED_FIELDS:
        val = row_dict.get(field, '').strip()
        if not val:
            errors.append(f'Row {row_idx}: {field} is empty')
    return errors


def validate_at_var(row_idx, value_str):
    """Validate at_var is a decimal between 0 and 1."""
    if not value_str or value_str.strip() == '':
        return []
    try:
        val = Decimal(value_str.strip())
    except (InvalidOperation, ValueError):
        return [f'Row {row_idx}: at_var value "{value_str}" is not a valid number, must be a decimal between 0 and 1 (e.g. 0.05)']
    if val < 0 or val > 1:
        return [f'Row {row_idx}: at_var value "{value_str}" must be between 0 and 1 (e.g. 0.05)']
    return []


def validate_numeric_value(row_idx, col_name, value_str):
    """Validate that a value column contains a valid number or is empty."""
    if not value_str or value_str.strip() == '':
        return []
    try:
        Decimal(value_str.strip())
    except (InvalidOperation, ValueError):
        return [f'Row {row_idx}: {col_name} value "{value_str}" is not a valid number']
    return []


def validate_volume_columns(headers, version):
    """Validate volume column ordering: prev scenario before current scenario."""
    errors = []
    current_scenario = extract_scenario(version)
    if current_scenario not in SCENARIO_ORDER:
        errors.append(f'Unknown scenario in version "{version}": {current_scenario}')
        return errors

    prev_scenario = SCENARIO_ORDER[current_scenario]

    vol_cols = [h for h in headers if h.startswith('volume_') and not h.startswith('volume_actual_')]

    prev_cols = [h for h in vol_cols if h.startswith(f'volume_{prev_scenario}_')]
    curr_cols = [h for h in vol_cols if h.startswith(f'volume_{current_scenario}_')]

    if not prev_cols:
        errors.append(f'Missing previous scenario volume_{prev_scenario}_* columns')
    if not curr_cols:
        errors.append(f'Missing current scenario volume_{current_scenario}_* columns')

    if prev_cols and curr_cols:
        last_prev_idx = max(headers.index(c) for c in prev_cols)
        first_curr_idx = min(headers.index(c) for c in curr_cols)
        if last_prev_idx >= first_curr_idx:
            errors.append(
                f'volume_{prev_scenario}_* columns must all appear before volume_{current_scenario}_* columns'
            )

    # Check for disallowed scenario columns
    allowed_prefixes = {f'volume_{prev_scenario}_', f'volume_{current_scenario}_', 'volume_actual_'}
    for h in headers:
        if h.startswith('volume_') and not any(h.startswith(p) for p in allowed_prefixes):
            errors.append(f'Unexpected volume column: {h} (only {prev_scenario} and {current_scenario} allowed)')

    return errors


def validate_column_count_match(headers):
    """Validate that each volume scenario has the same number of columns as spending."""
    errors = []
    spending_cols = [h for h in headers if h.startswith('spending_')]
    vol_cols = [h for h in headers if h.startswith('volume_') and not h.startswith('volume_actual_')]

    scenarios = set()
    for h in vol_cols:
        parts = h.split('_')
        if len(parts) >= 2:
            scenarios.add(parts[1])

    for scenario in scenarios:
        scenario_cols = [h for h in vol_cols if h.startswith(f'volume_{scenario}_')]
        if len(scenario_cols) != len(spending_cols):
            errors.append(
                f'volume_{scenario}_* column count ({len(scenario_cols)}) '
                f'does not match spending_* column count ({len(spending_cols)})'
            )

    return errors


def validate_duplicate_rows(rows):
    """Check for duplicate rows (same version + cc + glc)."""
    errors = []
    seen = {}
    for idx, row in enumerate(rows, start=2):
        key = (row.get('version', ''), row.get('cc', ''), row.get('glc', ''))
        if key in seen:
            errors.append(
                f'Row {idx}: duplicate entry (version={key[0]}, cc={key[1]}, glc={key[2]}) '
                f'- same as row {seen[key]}'
            )
        else:
            seen[key] = idx
    return errors


def validate_import_data(headers, rows, version=None):
    """Run all validations on import data. Returns list of error strings."""
    errors = []

    # Header validation
    errors.extend(validate_csv_headers(headers))
    if errors:
        return errors  # Can't continue without proper headers

    # Get version from first row if not provided
    if version is None and rows:
        version = rows[0].get('version', '')

    if version:
        errors.extend(validate_volume_columns(headers, version))
        errors.extend(validate_column_count_match(headers))

    # Row-level validation
    value_cols = [h for h in headers if h not in DIMENSION_COLUMNS]
    for idx, row in enumerate(rows, start=2):
        errors.extend(validate_required_fields(idx, row))
        errors.extend(validate_at_var(idx, row.get('at_var', '')))
        for col in value_cols:
            errors.extend(validate_numeric_value(idx, col, row.get(col, '')))

    return errors
