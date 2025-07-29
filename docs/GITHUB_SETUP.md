# GitHub Setup - Quick Reference

Essential commands for GitHub repository management and deployment.

## Repository Setup
```bash
# Create and push to GitHub
gh repo create FuturesTradingLog --public --clone
git add .
git commit -m "Initial commit"
git push origin main
```

## GitHub Actions (Auto-Deploy)
- **Location**: `.github/workflows/docker-build.yml`
- **Trigger**: Push to main branch
- **Output**: Docker image at `ghcr.io/qsor27/futurestradinglog:main`

## Container Registry
```bash
# Manual image pull
docker pull ghcr.io/qsor27/futurestradinglog:main

# Run latest version
docker run -p 5000:5000 ghcr.io/qsor27/futurestradinglog:main
```

## Repository Secrets
Required secrets for GitHub Actions:
- `GITHUB_TOKEN` (auto-generated)
- Additional secrets configured for container registry access

## Workflow Status
- **Build Status**: Check GitHub Actions tab
- **Image Registry**: Available at GitHub Container Registry
- **Auto-Deploy**: Watchtower integration (see deployment docs)

**Note**: Repository is configured for automated Docker builds on every push to main branch.