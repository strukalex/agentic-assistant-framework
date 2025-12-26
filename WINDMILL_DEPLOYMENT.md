# Windmill Deployment Guide

## Architecture Overview

This project uses a **custom Windmill worker image** with the `paias` package pre-installed. This eliminates code duplication and provides clean, direct imports in Windmill scripts.

### Key Components

1. **Custom Docker Image** ([Dockerfile.windmill](Dockerfile.windmill))
   - Based on `ghcr.io/windmill-labs/windmill:main`
   - Pre-installs `paias` package via `pip install -e /app`
   - All dependencies from `pyproject.toml` are available

2. **Windmill Scripts** (`f/research/`)
   - Entry point: `f/research/run_research.py`
   - Imports directly from `paias` package (e.g., `from paias.workflows.research_graph import ...`)
   - No code duplication - source of truth is `src/`

3. **Sync Process** ([scripts/sync_windmill.sh](scripts/sync_windmill.sh))
   - Only syncs Windmill scripts (`f/**`)
   - No longer copies `src/` to `u/admin/research_lib/`
   - Cleans up old workspace modules if they exist

## Deployment Workflow

### 1. Initial Setup

```bash
# Build the custom Windmill worker image
docker compose build windmill_worker

# Start all services (including Windmill)
docker compose up -d

# Wait for Windmill to be ready
# Check http://localhost:8100/api/version
```

### 2. Deploy Scripts to Windmill

```bash
# Sync scripts to Windmill workspace
npm run sync:windmill

# Or manually:
bash scripts/sync_windmill.sh
```

### 3. Verify Deployment

1. Open Windmill UI: http://localhost:8100
2. Navigate to Scripts → `f/research/run_research`
3. Test with sample input:
   ```json
   {
     "topic": "Latest developments in AI agents",
     "user_id": "550e8400-e29b-41d4-a716-446655440000"
   }
   ```

## Making Code Changes

### Updating Application Code (`src/`)

When you modify code in `src/`, you need to rebuild the Docker image:

```bash
# 1. Rebuild the Windmill worker image
docker compose build windmill_worker

# 2. Restart the worker
docker compose restart windmill_worker

# 3. Resync scripts (in case Windmill needs metadata updates)
npm run sync:windmill
```

### Updating Windmill Scripts (`f/research/`)

When you modify Windmill scripts, just sync:

```bash
npm run sync:windmill
```

No Docker rebuild needed - scripts are uploaded to Windmill's database.

## Environment Variables

The custom worker image requires these environment variables (set in `.env`):

```env
# Azure AI Foundry
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/paias

# Telemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

These are automatically passed through via `docker-compose.yml`.

## Directory Structure

```
/
├── Dockerfile.windmill          # Custom worker image definition
├── docker-compose.yml            # Uses custom image for workers
├── src/                          # Source code (installed as paias package)
├── f/research/                   # Windmill entry points
│   ├── run_research.py          # Main workflow script
│   ├── run_research.script.yaml # Metadata
│   ├── run_research.script.lock # Dependency lockfile
│   └── requirements.txt         # Dependencies
├── scripts/
│   └── sync_windmill.sh         # Deployment script
└── wmill.yaml                    # Windmill configuration
```

## Benefits of This Approach

### ✅ No Code Duplication
- **Before**: 748KB copied from `src/` to `u/admin/research_lib/`
- **After**: Zero duplication - `paias` installed once in Docker image

### ✅ Clean Imports
- **Before**: `from u.admin.research_lib.workflows.research_graph import ...`
- **After**: `from paias.workflows.research_graph import ...`

### ✅ True Source of Truth
- All code lives in `src/`
- No sync/copy confusion
- Standard Python package structure

### ✅ Easier Development
- Modify code in `src/`, rebuild Docker image
- No manual file copying
- Standard Python development workflow

## Troubleshooting

### Import Errors in Windmill

**Symptom**: `ModuleNotFoundError: No module named 'paias'`

**Solution**:
```bash
# Rebuild the worker image
docker compose build windmill_worker
docker compose restart windmill_worker

# Verify paias is installed
docker compose exec windmill_worker python -c "import paias; print(paias.__file__)"
```

### Dependency Issues

**Symptom**: Missing Python packages

**Solution**:
1. Add dependencies to `pyproject.toml`
2. Update `f/research/requirements.txt` if needed
3. Rebuild: `docker compose build windmill_worker`
4. Restart: `docker compose restart windmill_worker`

### Stale Code

**Symptom**: Code changes not reflected in Windmill

**Solution**:
```bash
# For src/ changes:
docker compose build windmill_worker
docker compose restart windmill_worker

# For f/research/ changes:
npm run sync:windmill
```

## Advanced: Production Deployment

For production, push the custom image to a registry:

```bash
# Tag the image
docker tag paias-windmill-worker:latest your-registry/paias-windmill-worker:v1.0.0

# Push to registry
docker push your-registry/paias-windmill-worker:v1.0.0

# Update docker-compose.yml to use the registry image
# windmill_worker:
#   image: your-registry/paias-windmill-worker:v1.0.0
```

## Git Sync (Optional)

To enable automatic version control in Windmill:

1. Go to Windmill UI → Workspace Settings → Git Sync
2. Connect your Git repository
3. Choose "Sync Mode" for automatic commits
4. Configure branch in `wmill.yaml`:
   ```yaml
   gitBranches:
     main:
       remote: origin
       path: ./
   ```

## Reset Development Environment

To completely reset:

```bash
# Full reset (rebuilds everything)
npm run reset

# This will:
# 1. Stop and remove all containers
# 2. Remove volumes
# 3. Start fresh containers
# 4. Build custom Windmill worker
# 5. Apply database migrations
# 6. Sync scripts to Windmill
```
