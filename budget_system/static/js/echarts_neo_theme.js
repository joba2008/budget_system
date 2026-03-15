/**
 * BSA Budget System - ECharts Neo Brutalism Theme
 */
(function() {
    'use strict';

    var NEO_THEME = {
        color: ['#845EF7', '#FF922B', '#20C997', '#FF6B6B', '#74C0FC',
                '#FFD43B', '#E64980', '#51CF66'],
        backgroundColor: '#FFFFFF',
        textStyle: {
            fontFamily: 'Inter, Segoe UI, system-ui, sans-serif'
        },
        title: {
            textStyle: { fontWeight: 900, fontSize: 16, color: '#000' }
        },
        legend: {
            textStyle: { fontWeight: 700, color: '#000', fontSize: 12 }
        },
        categoryAxis: {
            axisLine: { lineStyle: { color: '#000', width: 2 } },
            axisTick: { lineStyle: { color: '#000', width: 2 } },
            axisLabel: { fontWeight: 700, color: '#000', fontSize: 11 }
        },
        valueAxis: {
            axisLine: { lineStyle: { color: '#000', width: 2 } },
            splitLine: { lineStyle: { color: '#E9ECEF', width: 1 } },
            axisLabel: { fontWeight: 600, color: '#000' }
        },
        bar: {
            itemStyle: { borderColor: '#000', borderWidth: 2 }
        },
        line: {
            lineStyle: { width: 3 },
            symbol: 'rect',
            symbolSize: 8
        },
        tooltip: {
            backgroundColor: '#000',
            borderWidth: 0,
            textStyle: { color: '#FFD43B', fontWeight: 700 },
            extraCssText: 'box-shadow: 4px 4px 0px rgba(0,0,0,0.3);'
        }
    };

    if (typeof echarts !== 'undefined') {
        echarts.registerTheme('neo', NEO_THEME);
    }
})();
