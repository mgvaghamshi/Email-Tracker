#!/bin/bash

# Docker Management Script for EmailTracker API
# Usage: ./docker-manage.sh [command]

set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="emailtracker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Show usage
show_usage() {
    echo "🐳 EmailTracker Docker Management Script"
    echo "========================================"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev        Start development environment"
    echo "  prod       Start production environment"
    echo "  nginx      Start with Nginx reverse proxy"
    echo "  stop       Stop all services"
    echo "  restart    Restart all services"
    echo "  logs       Show service logs"
    echo "  status     Show service status"
    echo "  clean      Clean up containers and volumes"
    echo "  reset      Complete reset (removes all data)"
    echo "  backup     Backup database"
    echo "  restore    Restore database from backup"
    echo "  shell      Access API container shell"
    echo "  db-shell   Access database shell"
    echo "  test       Run API tests"
    echo "  build      Rebuild all images"
    echo "  health     Check service health"
    echo ""
    echo "Examples:"
    echo "  $0 dev                    # Start development environment"
    echo "  $0 prod                   # Start production environment"
    echo "  $0 logs api               # Show API service logs"
    echo "  $0 backup backup.sql      # Backup database to file"
}

# Development environment
start_dev() {
    log_info "Starting development environment..."
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    log_success "Development environment started!"
    echo ""
    log_info "API: http://localhost:8001"
    log_info "Docs: http://localhost:8001/docs"
    log_info "Database: localhost:5433"
    log_info "Redis: localhost:6380"
}

# Production environment
start_prod() {
    log_info "Starting production environment..."
    if [ ! -f ".env.docker" ]; then
        log_warning "No .env.docker file found. Creating from production template..."
        cp .env.production .env.docker
    fi
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    log_success "Production environment started!"
    echo ""
    log_info "API: http://localhost:8001"
    log_info "Health: http://localhost:8001/health"
}

# Start with Nginx
start_nginx() {
    log_info "Starting with Nginx reverse proxy..."
    docker-compose --profile with-nginx up -d
    log_success "Environment with Nginx started!"
    echo ""
    log_info "API via Nginx: http://localhost"
    log_info "Direct API: http://localhost:8001"
    log_info "Nginx health: http://localhost/nginx-health"
}

# Stop services
stop_services() {
    log_info "Stopping all services..."
    docker-compose down
    log_success "All services stopped!"
}

# Restart services
restart_services() {
    log_info "Restarting all services..."
    docker-compose restart
    log_success "All services restarted!"
}

# Show logs
show_logs() {
    local service=${1:-}
    if [ -n "$service" ]; then
        log_info "Showing logs for $service..."
        docker-compose logs -f "$service"
    else
        log_info "Showing logs for all services..."
        docker-compose logs -f
    fi
}

# Show status
show_status() {
    log_info "Service status:"
    docker-compose ps
}

# Clean up
clean_up() {
    log_warning "This will remove all containers but keep volumes. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning up containers..."
        docker-compose down --remove-orphans
        docker system prune -f
        log_success "Cleanup completed!"
    else
        log_info "Cleanup cancelled."
    fi
}

# Complete reset
reset_all() {
    log_error "This will remove ALL containers, volumes, and data. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Performing complete reset..."
        docker-compose down -v --remove-orphans
        docker system prune -a -f
        log_success "Complete reset performed!"
    else
        log_info "Reset cancelled."
    fi
}

# Backup database
backup_db() {
    local backup_file=${1:-"backup_$(date +%Y%m%d_%H%M%S).sql"}
    log_info "Backing up database to $backup_file..."
    docker-compose exec db pg_dump -U postgres email_tracker > "$backup_file"
    log_success "Database backed up to $backup_file"
}

# Restore database
restore_db() {
    local backup_file=${1:-}
    if [ -z "$backup_file" ]; then
        log_error "Please specify backup file: $0 restore backup.sql"
        exit 1
    fi
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file $backup_file not found!"
        exit 1
    fi
    log_warning "This will replace the current database. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Restoring database from $backup_file..."
        docker-compose exec -T db psql -U postgres email_tracker < "$backup_file"
        log_success "Database restored from $backup_file"
    else
        log_info "Restore cancelled."
    fi
}

# Access container shell
container_shell() {
    log_info "Accessing API container shell..."
    docker-compose exec api bash
}

# Access database shell
db_shell() {
    log_info "Accessing database shell..."
    docker-compose exec db psql -U postgres email_tracker
}

# Run tests
run_tests() {
    log_info "Running API tests..."
    docker-compose exec api python3 -m pytest tests/ -v
}

# Build images
build_images() {
    log_info "Building all images..."
    docker-compose build --no-cache
    log_success "Images built successfully!"
}

# Health check
health_check() {
    log_info "Checking service health..."
    echo ""
    
    # API Health
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        log_success "API: Healthy"
    else
        log_error "API: Unhealthy"
    fi
    
    # Database Health
    if docker-compose exec db pg_isready -U postgres > /dev/null 2>&1; then
        log_success "Database: Healthy"
    else
        log_error "Database: Unhealthy"
    fi
    
    # Redis Health
    if docker-compose exec redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis: Healthy"
    else
        log_error "Redis: Unhealthy"
    fi
}

# Main script
main() {
    check_docker

    case "${1:-}" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "nginx")
            start_nginx
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        "logs")
            show_logs "$2"
            ;;
        "status")
            show_status
            ;;
        "clean")
            clean_up
            ;;
        "reset")
            reset_all
            ;;
        "backup")
            backup_db "$2"
            ;;
        "restore")
            restore_db "$2"
            ;;
        "shell")
            container_shell
            ;;
        "db-shell")
            db_shell
            ;;
        "test")
            run_tests
            ;;
        "build")
            build_images
            ;;
        "health")
            health_check
            ;;
        "help"|"-h"|"--help"|"")
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
