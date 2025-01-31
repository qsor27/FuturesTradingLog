const StatisticsChart = React.memo(({ period = 'daily', stats = [] }) => {
    console.log('StatisticsChart rendering with:', { period, stats });
    
    // Get Recharts from window
    const Recharts = window.Recharts || {};
    console.log('Recharts object:', Recharts);
    
    const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = Recharts;
    
    if (!LineChart) {
        console.error('Required Recharts components not found');
        return React.createElement('div', { 
            className: 'flex items-center justify-center h-64 bg-gray-100 rounded-lg'
        }, 'Error: Chart library not loaded');
    }

    const [chartData, setChartData] = React.useState([]);

    React.useEffect(() => {
        if (stats && stats.length > 0) {
            console.log('Processing stats data:', stats);
            const transformedData = stats.map(stat => ({
                period: stat.period_display,
                'Net Profit': parseFloat(stat.net_profit),
                'Win Rate': parseFloat(stat.win_rate),
                'Total Trades': parseInt(stat.total_trades)
            }));
            console.log('Transformed data:', transformedData);
            setChartData(transformedData);
        }
    }, [stats]);

    if (!chartData.length) {
        return React.createElement('div', {
            className: 'flex items-center justify-center h-64 bg-gray-100 rounded-lg'
        }, React.createElement('p', {
            className: 'text-gray-500 italic'
        }, 'No data available for the selected period'));
    }

    return React.createElement('div', {
        className: 'w-full h-full'
    }, React.createElement(ResponsiveContainer, {
        width: '100%',
        height: '100%'
    }, React.createElement(LineChart, {
        data: chartData,
        margin: { top: 20, right: 30, left: 20, bottom: 10 }
    }, [
        React.createElement(CartesianGrid, {
            strokeDasharray: '3 3',
            key: 'grid'
        }),
        React.createElement(XAxis, {
            dataKey: 'period',
            height: 60,
            tick: { angle: -45, textAnchor: 'end' },
            key: 'xAxis'
        }),
        React.createElement(YAxis, {
            yAxisId: 'left',
            key: 'leftYAxis'
        }),
        React.createElement(YAxis, {
            yAxisId: 'right',
            orientation: 'right',
            key: 'rightYAxis'
        }),
        React.createElement(Tooltip, {
            key: 'tooltip'
        }),
        React.createElement(Legend, {
            key: 'legend'
        }),
        React.createElement(Line, {
            yAxisId: 'left',
            type: 'monotone',
            dataKey: 'Net Profit',
            stroke: '#2563eb',
            strokeWidth: 2,
            dot: { r: 4 },
            key: 'profit'
        }),
        React.createElement(Line, {
            yAxisId: 'right',
            type: 'monotone',
            dataKey: 'Win Rate',
            stroke: '#16a34a',
            strokeWidth: 2,
            dot: { r: 4 },
            key: 'winRate'
        })
    ])));
});