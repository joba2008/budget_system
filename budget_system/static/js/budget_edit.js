/**
 * BSA Budget System - Budget Edit Page Interaction
 * Handles inline cell editing, AJAX save, and cascade updates.
 */
(function() {
    'use strict';

    const config = window.BSA_CONFIG || {};
    const saveStatusEl = document.getElementById('save-status');

    function formatNumber(val) {
        if (val === null || val === undefined || val === '') return '';
        const num = parseFloat(val);
        if (isNaN(num)) return val;
        return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function parseNumber(str) {
        if (!str || str.trim() === '') return null;
        const cleaned = str.replace(/,/g, '').trim();
        const num = parseFloat(cleaned);
        return isNaN(num) ? null : num;
    }

    function showStatus(msg, type) {
        if (!saveStatusEl) return;
        saveStatusEl.textContent = msg;
        saveStatusEl.className = 'save-status ' + type;
        if (type === 'saved') {
            setTimeout(function() { saveStatusEl.textContent = ''; }, 2000);
        }
    }

    function updateRowTotal(tr) {
        let total = 0;
        let hasValue = false;
        tr.querySelectorAll('td[data-period]').forEach(function(td) {
            const val = parseNumber(td.textContent);
            if (val !== null) {
                total += val;
                hasValue = true;
            }
        });
        const totalCell = tr.querySelector('td[data-role="row-total"]');
        if (totalCell) {
            totalCell.textContent = hasValue ? formatNumber(total) : '—';
        }
    }

    function initCellEditing() {
        if (!config.isEditable) return;

        document.querySelectorAll('.cell-editable').forEach(function(td) {
            td.addEventListener('click', function() {
                if (td.querySelector('input')) return;

                const currentValue = td.getAttribute('data-value') || td.textContent.trim();
                const rawValue = currentValue.replace(/,/g, '').trim();

                td.classList.add('cell-editing');
                const input = document.createElement('input');
                input.type = 'text';
                input.value = rawValue === '—' ? '' : rawValue;
                input.setAttribute('data-original', rawValue);

                td.textContent = '';
                td.appendChild(input);
                input.focus();
                input.select();

                input.addEventListener('blur', function() {
                    commitEdit(td, input);
                });

                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        input.blur();
                    } else if (e.key === 'Escape') {
                        td.classList.remove('cell-editing');
                        td.textContent = formatNumber(rawValue);
                        td.setAttribute('data-value', rawValue);
                    } else if (e.key === 'Tab') {
                        e.preventDefault();
                        input.blur();
                        // Move to next editable cell
                        const nextTd = td.nextElementSibling;
                        if (nextTd && nextTd.classList.contains('cell-editable')) {
                            nextTd.click();
                        }
                    }
                });
            });
        });
    }

    function commitEdit(td, input) {
        const newValue = input.value.trim();
        const originalValue = input.getAttribute('data-original');

        td.classList.remove('cell-editing');

        // Validate numeric
        if (newValue !== '' && parseNumber(newValue) === null) {
            td.classList.add('cell-error');
            td.textContent = originalValue ? formatNumber(originalValue) : '';
            td.setAttribute('data-value', originalValue || '');
            showStatus('Invalid number', 'error');
            setTimeout(function() { td.classList.remove('cell-error'); }, 2000);
            return;
        }

        // No change
        const cleanNew = newValue.replace(/,/g, '').trim();
        const cleanOrig = (originalValue || '').replace(/,/g, '').trim();
        if (cleanNew === cleanOrig) {
            td.textContent = originalValue ? formatNumber(originalValue) : '';
            td.setAttribute('data-value', originalValue || '');
            return;
        }

        // Display new value immediately
        td.textContent = newValue ? formatNumber(newValue) : '';
        td.setAttribute('data-value', cleanNew);
        td.classList.add('cell-modified');

        // Update row total
        updateRowTotal(td.closest('tr'));

        // Save via AJAX
        saveCellValue(td, cleanNew || null);
    }

    function saveCellValue(td, value) {
        const tableName = td.getAttribute('data-table');
        const mainId = td.getAttribute('data-main-id');
        const period = td.getAttribute('data-period');

        showStatus('Saving...', 'saving');

        fetch(config.cellSaveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrfToken,
            },
            body: JSON.stringify({
                table: tableName,
                main_id: parseInt(mainId),
                period: period,
                value: value,
            }),
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            if (data.status === 'ok') {
                showStatus('Saved', 'saved');

                // Update rebase cell if cascade happened
                if (data.updated_rebase !== undefined) {
                    updateRebaseCell(mainId, period, data.updated_rebase);
                }
                // Update final_budget cell if cascade happened
                if (data.updated_final_budget !== undefined) {
                    updateFinalBudgetCell(mainId, period, data.updated_final_budget);
                }
            } else {
                showStatus('Error: ' + (data.message || 'Unknown'), 'error');
                td.classList.add('cell-error');
            }
        })
        .catch(function(err) {
            showStatus('Network error', 'error');
            console.error('Save failed:', err);
        });
    }

    function updateRebaseCell(mainId, period, value) {
        // Find the rebase cell in the same row if visible
        const selector = `td[data-table="bsa_rebase_financeview"][data-main-id="${mainId}"][data-period="${period}"]`;
        const rebaseCell = document.querySelector(selector);
        if (rebaseCell) {
            rebaseCell.textContent = value ? formatNumber(value) : '';
            rebaseCell.setAttribute('data-value', value || '');
            rebaseCell.classList.add('cell-modified');
        }
    }

    function updateFinalBudgetCell(mainId, period, value) {
        const selector = `td[data-table="bsa_final_budget"][data-main-id="${mainId}"][data-period="${period}"]`;
        const cell = document.querySelector(selector);
        if (cell) {
            cell.textContent = value ? formatNumber(value) : '';
            cell.setAttribute('data-value', value || '');
            cell.classList.add('cell-modified');
        }
    }

    // Initialize all row totals
    function initRowTotals() {
        document.querySelectorAll('#budget-table tbody tr').forEach(function(tr) {
            updateRowTotal(tr);
        });
    }

    // Init
    document.addEventListener('DOMContentLoaded', function() {
        initCellEditing();
        initRowTotals();
    });
})();
