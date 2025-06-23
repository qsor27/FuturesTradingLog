# GitHub Actions Auto-Deploy Setup Guide

**Complete setup for automated safe deployment with GitHub Actions**

## 🎯 **Overview**

This setup gives you **automated deployment** with **all safety features**:
- ✅ **Familiar workflow**: `git push origin main` = automatic deployment
- ✅ **Safety built-in**: Backup, health checks, rollback on failure
- ✅ **Market hours protection**: Blocks deployment during trading hours
- ✅ **Zero manual intervention**: Everything happens automatically
- ✅ **Full monitoring**: See exactly what happened in GitHub Actions

## 🚀 **Quick Setup (5 minutes)**

### **Step 1: Set Up GitHub Runner**
```bash
# Run the setup script
./scripts/setup-github-runner.sh

# Follow the instructions to configure with your GitHub repository
# This creates a connection between your server and GitHub Actions
```

### **Step 2: Configure Repository Secrets (Optional)**
If you want email alerts, add these to your GitHub repository secrets:
- Go to your repo → Settings → Secrets and variables → Actions
- Add these secrets (all optional):
  - `SMTP_SERVER` (e.g., smtp.gmail.com)
  - `SMTP_USERNAME` (your email)
  - `SMTP_PASSWORD` (your app password)
  - `ALERT_RECIPIENTS` (comma-separated emails)

### **Step 3: Test the System**
```bash
# Make a small change and push
echo "# Test auto-deploy" >> README.md
git add README.md
git commit -m "Test automated deployment"
git push origin main

# Watch it deploy automatically in GitHub Actions!
```

## 🛡️ **How Safe Auto-Deploy Works**

### **When You Push to Main:**
```
1. 🔍 GitHub Actions triggers automatically
2. 🏗️ Builds new Docker image
3. 🏥 Runs pre-deployment health check
4. ⏰ Checks if it's market hours (blocks if trading time)
5. 💾 Creates automatic backup
6. 🚀 Deploys new version with health validation
7. ✅ Verifies deployment succeeded
8. 🧪 Runs integration tests
9. 📧 Sends success notification
```

### **If Anything Goes Wrong:**
```
1. 🚨 Detects failure immediately
2. 🔄 Automatic rollback to previous version
3. 🏥 Verifies rollback health
4. 📧 Sends failure alert with details
5. ⚡ Your app stays running (zero downtime)
```

## ⏰ **Market Hours Protection**

### **Automatic Blocking:**
- **Blocked**: Monday-Friday 9:30AM-4:00PM EST (market hours)
- **Allowed**: Nights, weekends, holidays
- **Override**: Manual deployment if urgent during market hours

### **To Force Deploy During Market Hours:**
1. Go to your GitHub repository
2. Actions → Safe Auto Deploy to Production
3. Click "Run workflow"
4. Check "Force deployment even during market hours"
5. Click "Run workflow"

## 📊 **Monitoring Your Deployments**

### **GitHub Actions Dashboard:**
- Go to your repo → Actions tab
- See all deployments with status (✅ success, ❌ failed)
- Click any run to see detailed logs
- Download deployment artifacts if needed

### **Health Monitoring:**
```bash
# Check current system health
./scripts/health-check.sh

# View deployment logs
docker logs futurestradinglog --tail 50

# Emergency rollback if needed
./scripts/emergency-rollback.sh
```

## 🔧 **Workflow Files Explained**

### **`.github/workflows/safe-auto-deploy.yml`**
- **Triggers**: Push to main branch
- **Safety**: Market hours check, backup, health validation
- **Deployment**: Blue-green deployment with rollback
- **Testing**: Integration tests after deployment

### **`.github/workflows/build-only.yml`**
- **Triggers**: Push to other branches, pull requests
- **Purpose**: Test and build without deploying
- **Safety**: Ensures code quality before merge

## 🚨 **Emergency Procedures**

### **If Deployment Fails:**
1. **Automatic**: System will rollback automatically
2. **Manual**: Run `./scripts/emergency-rollback.sh`
3. **Check**: Use `./scripts/health-check.sh` to verify

### **If Runner Goes Down:**
```bash
# Check runner status
runner-status

# Restart runner
runner-restart

# View runner logs
runner-logs
```

### **If You Need to Deploy Immediately:**
```bash
# Bypass GitHub Actions and deploy manually
./scripts/deploy-production.sh latest
```

## 🎯 **Your New Workflow**

### **Daily Development:**
```bash
# Same as always!
git add .
git commit -m "Add new trading feature"
git push origin main

# GitHub automatically:
# - Builds your code
# - Deploys safely with all checks
# - Rolls back if any issues
# - Sends you status updates
```

### **Feature Development:**
```bash
# Work on feature branch (won't auto-deploy)
git checkout -b new-feature
git add .
git commit -m "WIP: New feature"
git push origin new-feature

# When ready, merge to main for auto-deploy
git checkout main
git merge new-feature
git push origin main  # ← This triggers safe auto-deploy
```

## ✅ **Benefits You Get**

### **Automation:**
- ✅ Push to main = automatic deployment
- ✅ No manual scripts to remember
- ✅ No SSH into server required

### **Safety:**
- ✅ Automatic backup before every deployment
- ✅ Health checks prevent broken deployments
- ✅ Instant rollback on any failure
- ✅ Market hours protection

### **Visibility:**
- ✅ See deployment status in GitHub
- ✅ Complete logs of what happened
- ✅ Email alerts on success/failure
- ✅ Integration test results

### **Reliability:**
- ✅ Zero downtime deployments
- ✅ Automatic recovery from failures
- ✅ Professional deployment practices
- ✅ Enterprise-grade reliability

## 🔍 **Troubleshooting**

### **Runner Setup Issues:**
```bash
# Check if runner is configured
cd ~/actions-runner
./run.sh --help

# Reinstall if needed
./scripts/setup-github-runner.sh
```

### **Deployment Not Triggering:**
1. Check if runner is online in GitHub repo settings
2. Verify you pushed to `main` branch
3. Check Actions tab for any errors

### **Market Hours Override:**
1. Go to GitHub repo → Actions
2. Find "Safe Auto Deploy to Production"
3. Click "Run workflow" → Check force deploy → Run

## 📚 **Documentation Links**

- **Complete Infrastructure Guide**: `INFRASTRUCTURE_IMPLEMENTATION_COMPLETE.md`
- **Daily Operations**: `DEPLOYMENT_RUNBOOK.md`
- **Security Setup**: `SECURITY_SETUP.md`
- **Backup Procedures**: `BACKUP_SYSTEM.md`

---

## 🎉 **You're All Set!**

Your GitHub Actions auto-deploy is now configured with:
- **Automated deployment** on every push to main
- **Enterprise-grade safety** with backup and rollback
- **Market hours protection** for trading applications
- **Zero downtime** deployment process
- **Complete monitoring** and alerting

**Just push your code and let GitHub Actions handle the rest safely!**