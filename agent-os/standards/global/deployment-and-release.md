# Deployment and Release Standards

## Release Strategy

This project uses **tag-based releases**. Regular commits to `main` do NOT automatically build and deploy. New releases are created only when version tags are pushed.

## Creating a Release

### 1. Commit Your Changes

Follow standard git workflow:

```bash
# Stage your changes
git add <files>

# Commit with clear message
git commit -m "Description of changes"

# Push to main branch
git push origin main
```

**Note:** This will NOT trigger a build or deployment.

### 2. Create and Push a Version Tag

When ready to release:

```bash
# Create an annotated tag with semantic versioning
git tag -a v1.0.1 -m "Brief description of release"

# Push the tag to GitHub (this triggers the build)
git push origin v1.0.1
```

### 3. What Happens Automatically

The `.github/workflows/release.yml` workflow will:

1. **Run Tests**: Execute full test suite with Redis service
2. **Build Docker Image**: Build multi-platform image (amd64/arm64)
3. **Push to Registry**: Publish to `ghcr.io/qsor27/futurestradinglog:v1.0.1` and `:latest`
4. **Build Windows Installer**: Create native Windows installer with all services
5. **Create GitHub Release**: Generate release notes with download links and checksums

## Version Numbering (Semantic Versioning)

Use semantic versioning: `vMAJOR.MINOR.PATCH`

- **MAJOR** (v2.0.0): Breaking changes, incompatible API changes
- **MINOR** (v1.1.0): New features, backwards-compatible
- **PATCH** (v1.0.1): Bug fixes, no new features

### Examples

```bash
# Bug fix for production issue
git tag -a v1.0.1 -m "Fix Redis connection in Docker deployment"
git push origin v1.0.1

# New feature added
git tag -a v1.1.0 -m "Add automatic CSV file archival"
git push origin v1.1.0

# Breaking change
git tag -a v2.0.0 -m "Redesign position tracking with new schema"
git push origin v2.0.0
```

## Deployment Targets

### Docker (Primary)

Docker images are automatically published to GitHub Container Registry:

```bash
# Pull latest release
docker pull ghcr.io/qsor27/futurestradinglog:latest

# Pull specific version
docker pull ghcr.io/qsor27/futurestradinglog:v1.0.1

# Run with docker-compose
docker-compose up -d
```

### Windows Installer (Secondary)

Native Windows installer available from GitHub Releases:
- Includes Flask app, Redis, Celery workers, file watcher
- All services run as Windows Services
- Accessible at http://localhost:5555

## Environment Variables

Critical environment variables for Docker deployment:

```bash
# Redis connection (REQUIRED for deduplication)
REDIS_URL=redis://redis:6379/0

# Data directory
DATA_DIR=/app/data

# Flask settings
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_SECRET_KEY=<your-secret-key>

# Optional
CACHE_ENABLED=true
```

## Pre-Release Checklist

Before creating a release tag:

- [ ] All tests passing locally
- [ ] Changes committed and pushed to main
- [ ] CHANGELOG.md updated (if maintained)
- [ ] Version number decided (MAJOR.MINOR.PATCH)
- [ ] Critical bug fixes tested in production-like environment
- [ ] Database migrations documented (if any)
- [ ] Breaking changes documented in release notes

## Hotfix Process

For urgent production fixes:

```bash
# 1. Create fix on main branch
git checkout main
git pull origin main

# 2. Make changes and commit
git add <files>
git commit -m "Fix critical bug in Redis connection"
git push origin main

# 3. Immediately tag as patch release
git tag -a v1.0.2 -m "Hotfix: Redis connection failure in Docker"
git push origin v1.0.2

# 4. Monitor GitHub Actions for successful build
# 5. Deploy new version to production
```

## Rollback Procedure

If a release has issues:

```bash
# Docker: Deploy previous version
docker pull ghcr.io/qsor27/futurestradinglog:v1.0.0
docker-compose down
docker-compose up -d

# Create new patch release with fix
git revert <bad-commit>
git tag -a v1.0.3 -m "Rollback: Revert problematic changes"
git push origin v1.0.3
```

## CI/CD Pipeline Details

### Workflow Trigger

```yaml
on:
  push:
    tags:
      - 'v*'  # Only version tags trigger builds
```

### Build Stages

1. **Test Job**: Runs pytest with Redis service
2. **Docker Build Job**: Multi-platform Docker image
3. **Windows Installer Job**: Native Windows installer with Inno Setup
4. **Release Creation**: Combines all artifacts into GitHub Release

### Artifacts Produced

- Docker image: `ghcr.io/qsor27/futurestradinglog:vX.Y.Z`
- Docker image: `ghcr.io/qsor27/futurestradinglog:latest`
- Windows installer: `FuturesTradingLog-Setup-vX.Y.Z.exe`
- Checksum file: `SHA256SUMS.txt`

## Monitoring Releases

### Check Build Status

1. Visit: https://github.com/qsor27/FuturesTradingLog/actions
2. Find workflow run for your tag
3. Monitor test execution and build progress

### Verify Deployment

```bash
# Pull new image
docker pull ghcr.io/qsor27/futurestradinglog:latest

# Check image tag
docker images | grep futurestradinglog

# Verify running container
docker ps | grep futurestradinglog

# Check logs for Redis connection
docker logs futurestradinglog | grep "Redis connection established"
```

## Common Issues

### Tag Already Exists

```bash
# Delete local tag
git tag -d v1.0.1

# Delete remote tag
git push origin :refs/tags/v1.0.1

# Recreate with correct commit
git tag -a v1.0.1 -m "Description"
git push origin v1.0.1
```

### Build Failed

1. Check GitHub Actions logs
2. Fix issues on main branch
3. Create new patch version tag
4. Previous version remains available

### Docker Image Not Updating

```bash
# Force pull latest
docker pull ghcr.io/qsor27/futurestradinglog:latest --no-cache

# Remove old container and image
docker-compose down
docker rmi ghcr.io/qsor27/futurestradinglog:latest
docker-compose up -d
```

## References

- **Semantic Versioning**: https://semver.org/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Docker Registry**: https://github.com/qsor27/FuturesTradingLog/pkgs/container/futurestradinglog
- **Release Workflow**: `.github/workflows/release.yml`
