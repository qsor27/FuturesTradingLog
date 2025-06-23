#!/bin/bash
set -euo pipefail

# GitHub Self-Hosted Runner Setup Script
# This sets up a GitHub Actions runner on your server for automated deployment

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
   exit 1
fi

log "Setting up GitHub Actions self-hosted runner..."

# Create runner directory
RUNNER_DIR="$HOME/actions-runner"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download the latest runner
log "Downloading GitHub Actions runner..."
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/' | sed 's/v//')
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"

if [[ ! -f "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" ]]; then
    curl -o "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" -L "$RUNNER_URL"
    tar xzf "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
fi

# Install dependencies
log "Installing runner dependencies..."
sudo ./bin/installdependencies.sh

# Get repository information
REPO_OWNER=$(git config --get remote.origin.url | sed 's/.*github\.com[/:]//g' | sed 's/\.git$//g' | cut -d'/' -f1)
REPO_NAME=$(git config --get remote.origin.url | sed 's/.*github\.com[/:]//g' | sed 's/\.git$//g' | cut -d'/' -f2)

info "Repository: $REPO_OWNER/$REPO_NAME"

# Instructions for user
echo ""
echo "=============================================="
echo "         GITHUB RUNNER SETUP INSTRUCTIONS"
echo "=============================================="
echo ""
echo "To complete the setup, you need to:"
echo ""
echo "1. Go to your GitHub repository:"
echo "   https://github.com/$REPO_OWNER/$REPO_NAME"
echo ""
echo "2. Navigate to Settings → Actions → Runners"
echo ""
echo "3. Click 'New self-hosted runner'"
echo ""
echo "4. Select 'Linux' and copy the configuration token"
echo ""
echo "5. Run the configuration command:"
echo "   ./config.sh --url https://github.com/$REPO_OWNER/$REPO_NAME --token YOUR_TOKEN"
echo ""
echo "6. When prompted for runner name, use: $(hostname)-runner"
echo ""
echo "7. When prompted for labels, use: self-hosted,linux,production"
echo ""
echo "8. Accept defaults for work folder"
echo ""
echo "9. Start the runner service:"
echo "   sudo ./svc.sh install"
echo "   sudo ./svc.sh start"
echo ""
echo "=============================================="
echo ""

# Create service management script
cat > "$RUNNER_DIR/manage-runner.sh" << 'EOF'
#!/bin/bash

case "$1" in
    start)
        echo "Starting GitHub Actions runner..."
        sudo ./svc.sh start
        ;;
    stop)
        echo "Stopping GitHub Actions runner..."
        sudo ./svc.sh stop
        ;;
    status)
        echo "GitHub Actions runner status:"
        sudo ./svc.sh status
        ;;
    restart)
        echo "Restarting GitHub Actions runner..."
        sudo ./svc.sh stop
        sleep 5
        sudo ./svc.sh start
        ;;
    logs)
        echo "Viewing runner logs..."
        sudo journalctl -u actions.runner.* -f
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart|logs}"
        exit 1
        ;;
esac
EOF

chmod +x "$RUNNER_DIR/manage-runner.sh"

log "Runner setup prepared. Follow the instructions above to complete configuration."
log "After configuration, use $RUNNER_DIR/manage-runner.sh to manage the runner service."

# Create helpful aliases
echo ""
info "Adding helpful aliases to ~/.bashrc..."
cat >> ~/.bashrc << EOF

# GitHub Actions Runner aliases
alias runner-status='$RUNNER_DIR/manage-runner.sh status'
alias runner-start='$RUNNER_DIR/manage-runner.sh start'
alias runner-stop='$RUNNER_DIR/manage-runner.sh stop'
alias runner-restart='$RUNNER_DIR/manage-runner.sh restart'
alias runner-logs='$RUNNER_DIR/manage-runner.sh logs'
EOF

info "Aliases added. Run 'source ~/.bashrc' or restart your terminal to use them."

echo ""
echo "=============================================="
echo "         SETUP COMPLETE"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Follow the GitHub configuration steps above"
echo "2. Test deployment with: git push origin main"
echo "3. Monitor with: runner-logs"
echo ""
echo "Your automated deployment will be ready!"
echo ""