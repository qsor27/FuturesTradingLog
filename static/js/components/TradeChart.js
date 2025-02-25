import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

const TradeChart = ({ tradeId }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  
  useEffect(() => {
    if (!chartContainerRef.current) return;
    
    // Create chart instance
    const chart = createChart(chartContainerRef.current, {
      width: 800,
      height: 400,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });
    
    chartRef.current = chart;
    
    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350'
    });
    
    // Fetch and load data
    const fetchData = async () => {
      try {
        const response = await fetch(`/api/chart-data/${tradeId}`);
        const result = await response.json();
        
        if (result.status === 'success') {
          // Set candlestick data
          candlestickSeries.setData(result.data);
          
          // Add entry marker
          candlestickSeries.createPriceLine({
            price: result.trade.entry_price,
            color: '#2962FF',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'Entry'
          });
          
          // Add exit marker if exists
          if (result.trade.exit_price) {
            candlestickSeries.createPriceLine({
              price: result.trade.exit_price,
              color: '#FF2962',
              lineWidth: 2,
              lineStyle: 2,
              axisLabelVisible: true,
              title: 'Exit'
            });
          }
          
          // Fit content to view
          chart.timeScale().fitContent();
        }
      } catch (error) {
        console.error('Error fetching chart data:', error);
      }
    };
    
    fetchData();
    
    // Cleanup
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [tradeId]);
  
  return (
    <div className="flex flex-col w-full">
      <div ref={chartContainerRef} className="w-full h-96" />
    </div>
  );
};

export default TradeChart;