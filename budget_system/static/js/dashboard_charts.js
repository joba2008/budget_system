/**
 * BSA Budget System - Dashboard Charts
 */
var spendTrendChart = null;
var waterfallChart = null;

function initDashboard() {
    'use strict';

    var config = window.DASHBOARD_CONFIG || {};

    // Initialize charts
    var trendEl = document.getElementById('spend-trend-chart');
    var waterfallEl = document.getElementById('waterfall-chart');

    if (trendEl) {
        spendTrendChart = echarts.init(trendEl, 'neo');
    }
    if (waterfallEl) {
        waterfallChart = echarts.init(waterfallEl, 'neo');
    }

    // Load initial data
    loadChartData();

    // Dept filter change handler
    document.querySelectorAll('.dept-checkbox').forEach(function(cb) {
        cb.addEventListener('change', function() {
            loadChartData();
        });
    });

    // Resize handling
    window.addEventListener('resize', function() {
        if (spendTrendChart) spendTrendChart.resize();
        if (waterfallChart) waterfallChart.resize();
    });
}

function getSelectedDepts() {
    var selected = [];
    document.querySelectorAll('.dept-checkbox:checked').forEach(function(cb) {
        selected.push(cb.value);
    });
    return selected;
}

function loadChartData() {
    var config = window.DASHBOARD_CONFIG || {};
    var depts = getSelectedDepts();

    var params = new URLSearchParams();
    params.set('version', config.version);
    depts.forEach(function(d) { params.append('dept_ppt', d); });

    // Load spend trend
    params.set('chart', 'spend_trend');
    fetch(config.chartDataUrl + '?' + params.toString())
        .then(function(r) { return r.json(); })
        .then(function(data) { renderSpendTrend(data); });

    // Load waterfall
    params.set('chart', 'waterfall');
    fetch(config.chartDataUrl + '?' + params.toString())
        .then(function(r) { return r.json(); })
        .then(function(data) { renderWaterfall(data); });
}

function formatMoney(val) {
    if (Math.abs(val) >= 1000000) {
        return '$' + (val / 1000000).toFixed(2) + 'M';
    } else if (Math.abs(val) >= 1000) {
        return '$' + (val / 1000).toFixed(0) + 'K';
    }
    return '$' + val.toFixed(0);
}

function renderSpendTrend(data) {
    if (!spendTrendChart || !data.periods) return;

    var option = {
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['Volume', 'Spending', 'Rebase'],
            top: 0
        },
        grid: { left: 60, right: 60, top: 50, bottom: 40 },
        xAxis: {
            type: 'category',
            data: data.periods,
            axisLabel: { fontSize: 11, fontWeight: 700 }
        },
        yAxis: [
            {
                type: 'value',
                name: 'Volume',
                position: 'left',
                axisLabel: { formatter: function(v) { return formatMoney(v); } }
            },
            {
                type: 'value',
                name: 'Spending',
                position: 'right',
                axisLabel: { formatter: function(v) { return formatMoney(v); } }
            }
        ],
        series: [
            {
                name: 'Volume',
                type: 'bar',
                yAxisIndex: 0,
                data: data.volume,
                itemStyle: { color: '#CED4DA', borderColor: '#000', borderWidth: 1 }
            },
            {
                name: 'Spending',
                type: 'line',
                yAxisIndex: 1,
                data: data.spending,
                lineStyle: { color: '#845EF7', width: 3 },
                itemStyle: { color: '#845EF7' }
            },
            {
                name: 'Rebase',
                type: 'line',
                yAxisIndex: 1,
                data: data.rebase,
                lineStyle: { color: '#51CF66', width: 3 },
                itemStyle: { color: '#51CF66' }
            }
        ]
    };

    spendTrendChart.setOption(option);
}

function renderWaterfall(data) {
    if (!waterfallChart || !data.categories) return;

    // Build waterfall data
    var values = data.values;
    var types = data.types;
    var categories = data.categories;

    // Calculate placeholder (invisible base), increase, decrease, total
    var placeholder = [];
    var increase = [];
    var decrease = [];
    var total = [];
    var running = 0;

    for (var i = 0; i < values.length; i++) {
        if (types[i] === 'total') {
            placeholder.push(0);
            increase.push(0);
            decrease.push(0);
            total.push(values[i]);
            running = values[i];
        } else if (types[i] === 'increase') {
            placeholder.push(running);
            increase.push(values[i]);
            decrease.push(0);
            total.push(0);
            running += values[i];
        } else {
            var absVal = Math.abs(values[i]);
            placeholder.push(running - absVal);
            increase.push(0);
            decrease.push(absVal);
            total.push(0);
            running -= absVal;
        }
    }

    var option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                var name = params[0].axisValue;
                var val = 0;
                params.forEach(function(p) { if (p.value > 0) val = p.value; });
                return name + ': ' + formatMoney(val);
            }
        },
        grid: { left: 60, right: 20, top: 30, bottom: 40 },
        xAxis: {
            type: 'category',
            data: categories,
            axisLabel: { fontWeight: 700 }
        },
        yAxis: {
            type: 'value',
            axisLabel: { formatter: function(v) { return formatMoney(v); } }
        },
        series: [
            {
                name: 'Placeholder',
                type: 'bar',
                stack: 'waterfall',
                data: placeholder,
                itemStyle: { color: 'transparent', borderWidth: 0 },
                emphasis: { itemStyle: { color: 'transparent' } }
            },
            {
                name: 'Increase',
                type: 'bar',
                stack: 'waterfall',
                data: increase,
                itemStyle: { color: '#FF922B', borderColor: '#000', borderWidth: 2 },
                label: {
                    show: true, position: 'top', fontWeight: 700, fontSize: 11,
                    formatter: function(p) { return p.value > 0 ? '+' + formatMoney(p.value) : ''; }
                }
            },
            {
                name: 'Decrease',
                type: 'bar',
                stack: 'waterfall',
                data: decrease,
                itemStyle: { color: '#51CF66', borderColor: '#000', borderWidth: 2 },
                label: {
                    show: true, position: 'bottom', fontWeight: 700, fontSize: 11,
                    formatter: function(p) { return p.value > 0 ? '-' + formatMoney(p.value) : ''; }
                }
            },
            {
                name: 'Total',
                type: 'bar',
                stack: 'waterfall',
                data: total,
                itemStyle: { color: '#845EF7', borderColor: '#000', borderWidth: 2 },
                label: {
                    show: true, position: 'top', fontWeight: 700, fontSize: 11,
                    formatter: function(p) { return p.value > 0 ? formatMoney(p.value) : ''; }
                }
            }
        ]
    };

    waterfallChart.setOption(option);
}
