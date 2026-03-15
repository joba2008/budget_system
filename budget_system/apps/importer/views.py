import csv
import io
import json
import os
import tempfile

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings

from apps.budget.models import BsaMain, get_all_versions
from apps.importer.services import (
    parse_csv_file, parse_excel_file, get_import_preview,
    execute_import, generate_csv_template,
)
from apps.importer.validators import validate_import_data

# Directory for storing temporary import data (avoids session cookie overflow)
IMPORT_TEMP_DIR = os.path.join(getattr(settings, 'MEDIA_ROOT', tempfile.gettempdir()), 'import_temp')
os.makedirs(IMPORT_TEMP_DIR, exist_ok=True)


def _check_import_permission(request):
    role = request.session.get('user_role', '')
    return role in ('admin', 'budgeter')


@login_required
def sample_csv_download(request):
    """Download a sample.csv template based on the latest version in the system."""
    versions = get_all_versions()
    version_name = versions[-1] if versions else 'fy26-B1'

    headers, demo_row = generate_csv_template(version_name)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerow(demo_row)
    return response


@login_required
def template_download(request):
    """Download CSV template for a given version."""
    versions = get_all_versions()
    if request.method == 'POST':
        version_name = request.POST.get('version', '')
        if not version_name:
            messages.error(request, 'Please select a version.')
            return render(request, 'importer/template_download.html', {'versions': versions})

        headers, demo_row = generate_csv_template(version_name)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bsa_template_{version_name}.csv"'
        writer = csv.writer(response)
        writer.writerow(headers)
        writer.writerow(demo_row)
        return response

    return render(request, 'importer/template_download.html', {'versions': versions})


@login_required
def upload_view(request):
    """CSV/Excel upload page."""
    if not _check_import_permission(request):
        messages.error(request, 'You do not have import permission.')
        return redirect('dashboard:index')

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
            return render(request, 'importer/upload.html')

        file_name = uploaded_file.name
        file_size = uploaded_file.size

        try:
            if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
                headers, rows = parse_excel_file(uploaded_file)
            else:
                headers, rows = parse_csv_file(uploaded_file)
        except Exception as e:
            messages.error(request, f'Failed to parse file: {e}')
            return render(request, 'importer/upload.html')

        if not rows:
            messages.error(request, 'File contains no data rows.')
            return render(request, 'importer/upload.html')

        # Run validation
        version = rows[0].get('version', '')
        errors = validate_import_data(headers, rows, version)

        if errors:
            return render(request, 'importer/preview.html', {
                'errors': errors,
                'file_name': file_name,
                'has_errors': True,
            })

        # Store in temp file for confirmation (session cookies have 4KB limit)
        preview = get_import_preview(headers, rows, version)
        import_id = f'{request.user.username}_{os.getpid()}_{id(request)}'
        temp_path = os.path.join(IMPORT_TEMP_DIR, f'{import_id}.json')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump({
                'headers': headers,
                'rows': rows,
                'file_name': file_name,
                'file_size': file_size,
            }, f, ensure_ascii=False)
        request.session['import_temp_path'] = temp_path

        return render(request, 'importer/preview.html', {
            'preview': preview,
            'file_name': file_name,
            'has_errors': False,
        })

    return render(request, 'importer/upload.html')


@login_required
def confirm_import(request):
    """Confirm and execute the import."""
    if request.method != 'POST':
        return redirect('importer:upload')

    if not _check_import_permission(request):
        messages.error(request, 'You do not have import permission.')
        return redirect('dashboard:index')

    temp_path = request.session.pop('import_temp_path', None)
    if not temp_path or not os.path.exists(temp_path):
        messages.error(request, 'No import data found. Please upload again.')
        return redirect('importer:upload')

    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
    finally:
        # Clean up temp file
        try:
            os.remove(temp_path)
        except OSError:
            pass

    if not import_data:
        messages.error(request, 'No import data found. Please upload again.')
        return redirect('importer:upload')

    try:
        result = execute_import(
            headers=import_data['headers'],
            rows=import_data['rows'],
            user=request.user.username,
            file_name=import_data['file_name'],
            file_size=import_data['file_size'],
        )
        messages.success(
            request,
            f'Import complete: {result["success_rows"]} rows imported successfully'
            f'{f", {result["failed_rows"]} rows failed" if result["failed_rows"] else ""}.'
        )
    except Exception as e:
        messages.error(request, f'Import failed: {e}')

    return redirect('importer:upload')
