# AI Collaboration Guide

This document provides a comprehensive guide for AI collaboration on the FuturesTradingLog project. It outlines the project overview, architecture, development workflow, and best practices to ensure effective and consistent contributions from AI assistants like Claude and Gemini.

## 1. Project Overview

Flask web application for futures traders - processes NinjaTrader executions into position-based trading analytics.

### Key Features
- **Position-Based Architecture**: Aggregates executions into meaningful positions with comprehensive overlap prevention
- **TradingView Charts**: Interactive charts with enhanced OHLC hover display and real-time validation status
- **High Performance**: 15-50ms chart loads with aggressive database indexing and adaptive resolution
- **Redis Caching**: 14-day data retention for faster performance with graceful fallback
- **Docker Deployment**: Container-based production deployment with health monitoring
- **Validation System**: Real-time position overlap detection with automated prevention and UI integration
- **User Preferences**: Persistent chart settings with localStorage caching and API synchronization

## 2. Critical Information

### 2.1. Position Building Algorithm

**LOCATION**: `domain/services/position_builder.py` - Contains the position building logic

**⚠️ Critical Warning**: PRESERVE ALGORITHM INTEGRITY
- Always test with `/positions/rebuild` after any changes
- Improper modifications break ALL historical P&L calculations

### 2.2. Detailed Documentation

**All detailed documentation has been moved to Obsidian vault for better organization. Key knowledge areas:**

- **Architecture Overview** - Repository pattern and core algorithm details
- **Development Guidelines** - AI instructions and coding standards  
- **Technology Stack** - Complete technology overview
- **Validation System** - Real-time monitoring and overlap prevention
- **Deployment and Operations** - Docker workflow and monitoring
- **Implementation Notes** - Key features and patterns

## 3. Architecture

See **[docs/ai-context/project-structure.md](docs/ai-context/project-structure.md)** for complete project structure and technology stack.

### Core Components

#### **Modern Architecture (Repository Pattern)**
- **Domain Layer** (`domain/`):
  - `models/`: Core business entities (Position, Trade, Execution, PnL)
  - `services/`: Pure business logic (PositionBuilder, PnLCalculator, QuantityFlowAnalyzer)
  - `interfaces/`: Service and repository contracts
- **Application Services** (`services/`):
  - `position_engine/`: Position building orchestration
  - `trade_management/`: Trade operations and filtering
  - `chart_data/`: Chart data with performance optimization
  - `file_processing/`: CSV processing and validation
  - `position_management/`: Position dashboard and statistics
- **Repository Layer** (`repositories/`):
  - `trade_repository.py`: Trade data operations
  - `position_repository.py`: Position data operations
  - `ohlc_repository.py`: Market data operations
  - `settings_repository.py`: Configuration data operations
  - `profile_repository.py`: User profile operations
  - `statistics_repository.py`: Analytics and reporting operations

#### **Key Components**
- **`position_service.py`**: Position building algorithm (extracted to domain services)
- **`enhanced_position_service.py`**: Enhanced position service with comprehensive overlap prevention  
- **`database_manager.py`**: Repository pattern coordinator (replaces TradingLog_db.py)
- **`data_service.py`**: yfinance integration with repository pattern
- **`app.py`**: Flask application with repository pattern
- **`routes/`**: All route blueprints use repository pattern

### Database Schema
- **Trades**: Individual executions with P&L, linking via `link_group_id`
- **Positions**: Aggregated position data with lifecycle tracking
- **OHLC_Data**: Market data with 8 performance indexes (15-50ms queries)
- **Chart_Settings**: User preferences for timeframes and display options
- **User_Profiles**: Named configuration profiles with settings snapshots

## 4. Development & Deployment

### Development (Docker-First)
```bash
# Standard development workflow
./dev.sh                                     # Start development environment

# Alternative
docker-compose -f docker-compose.dev.yml up --build

# Benefits:
# - Matches production environment exactly
# - Live code reloading (edit files normally) 
# - Debug mode enabled
# - No Python virtual environment needed
# - No dependency version conflicts
```

### Production Deployment
```bash
# Production (automatic via GitHub Actions)
git push origin main                          # Auto-deploy via GitHub Actions

# Production (manual)
docker-compose up --build                    # Production deployment

# Health checks
curl http://localhost:5000/health            # Basic health check
pytest tests/ -v                             # Run tests
```

### GitHub Actions Workflow
The deployment pipeline consists of 3 jobs:
1. **Test**: Code quality validation and basic functionality tests
2. **Build-and-Push**: Creates Docker image and pushes to GitHub Container Registry
3. **Security-Scan**: Vulnerability scanning with Trivy (optional but recommended)

## 5. Configuration

See **[docs/CONFIGURATION_HIERARCHY.md](docs/CONFIGURATION_HIERARCHY.md)** for complete configuration management details.

### Key Environment Variables
- `DATA_DIR`: Data storage directory (default: `~/FuturesTradingLog/data`)
- `REDIS_URL`: Redis connection (default: `redis://localhost:6379/0`)
- `CACHE_TTL_DAYS`: Cache retention (default: `14`)

### Data Directory Structure
```
data/
├── db/              # SQLite database (persistent)
├── config/          # instrument_multipliers.json
├── logs/            # Application logs (rotating)
└── archive/         # Processed CSV files
```

### Storage Strategy
- **SQLite**: Primary storage - all data persists permanently
- **Redis**: Performance layer - 14-day TTL, 20-60x faster queries
- **Graceful fallback**: Redis unavailable → automatic SQLite fallback

## 6. AI Collaboration Recommendations

### 6.1. Content & Structure

*   **Create a "Single Source of Truth":** For each piece of information, there should be one and only one place where it is documented. For example, all API documentation should be in one place, and all deployment documentation should be in another.
*   **Improve the Documentation Index:** Use the Dataview plugin to automatically generate a table of all documentation files. This will ensure that the index is always up-to-date.

### 6.2. Tooling & Integration

*   **Leverage Powerful Plugins:**
    *   **Dataview:** For creating dynamic tables and lists.
    *   **Templater:** For creating powerful documentation templates.
    *   **PlantUML:** For creating diagrams directly in your notes.
    *   **Editor Syntax Highlight:** For improving the readability of code blocks.
    *   **OpenAPI Renderer:** For rendering OpenAPI/Swagger specifications.
*   **Create Documentation Templates:** Use the Templater plugin to create templates for new feature documentation, API endpoints, ADRs, and meeting notes.

### 6.3. Workflow & Automation

*   **Automate Documentation Tasks:** Use Templater to automate repetitive tasks and Dataview to track open issues.
*   **Integrate with Your Development Workflow:** Link to documentation from your code and use Obsidian's URI scheme to create links from your IDE.

## 7. Implementation Roadmap

### Week 1: Foundation

*   [ ] Install and configure recommended plugins (Dataview, Templater, PlantUML).
*   [ ] Consolidate `CLAUDE.md` and `GEMINI_IDEAS.md`.
*   [ ] Archive outdated documents.
*   [ ] Create a basic documentation index with Dataview.

### Week 2: Templates & Structure

*   [ ] Create documentation templates for new features and API endpoints.
*   [ ] Refactor existing documentation to use the new templates.
*   [ ] Organize the documentation index by category.

### Week 3: Automation & Integration

*   [ ] Create Templater scripts to automate repetitive tasks.
*   [ ] Create a "Hotlist" of open issues with Dataview.
*   [ ] Start linking to documentation from your code.
