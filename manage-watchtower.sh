#!/bin/bash

# Watchtower Management Script for FuturesTradingLog
# This script helps manage the Watchtower auto-update service

set -e

ACTION=${1:-status}

case $ACTION in
    "start")
        echo "🚀 Starting Watchtower auto-update service..."
        docker-compose -f docker-compose.prod.yml up -d
        echo "✅ Services started successfully"
        ;;
    
    "stop")
        echo "🛑 Stopping Watchtower and application..."
        docker-compose -f docker-compose.prod.yml down
        echo "✅ Services stopped"
        ;;
    
    "restart")
        echo "🔄 Restarting services..."
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up -d
        echo "✅ Services restarted"
        ;;
    
    "status")
        echo "📊 Service Status:"
        echo "=================="
        docker-compose -f docker-compose.prod.yml ps
        echo ""
        echo "🔍 Watchtower Logs (last 10 lines):"
        echo "===================================="
        docker logs watchtower --tail 10 2>/dev/null || echo "Watchtower not running"
        echo ""
        echo "🏥 Application Health:"
        echo "====================="
        curl -s http://localhost:5000/health | jq '.status' 2>/dev/null || echo "Application not accessible"
        ;;
    
    "logs")
        SERVICE=${2:-watchtower}
        echo "📋 Showing logs for $SERVICE..."
        docker logs -f $SERVICE
        ;;
    
    "update-now")
        echo "🔄 Forcing immediate update check..."
        docker exec watchtower watchtower --run-once --cleanup || echo "Failed to trigger update"
        ;;
    
    "health")
        echo "🏥 Checking application health..."
        if curl -s http://localhost:5000/health >/dev/null; then
            echo "✅ Application is healthy"
            exit 0
        else
            echo "❌ Application is not responding"
            exit 1
        fi
        ;;
    
    *)
        echo "🤖 Watchtower Management Script"
        echo "==============================="
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start       - Start Watchtower and application services"
        echo "  stop        - Stop all services"
        echo "  restart     - Restart all services"
        echo "  status      - Show status of services (default)"
        echo "  logs [svc]  - Show logs (watchtower or futurestradinglog)"
        echo "  update-now  - Force immediate update check"
        echo "  health      - Check application health"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  $0 logs watchtower"
        echo "  $0 logs futurestradinglog"
        echo "  $0 update-now"
        ;;
esac