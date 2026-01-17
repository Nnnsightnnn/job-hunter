#!/bin/bash
#
# 🎯 Job Hunter - One-Click Setup & Launch
# 
# Just double-click this file! It will:
# 1. Install everything you need (first time only)
# 2. Start the app
# 3. Open it in your browser
#
# ============================================================

# Make the script work from any location
cd "$(dirname "$0")"
APP_DIR="$(pwd)"

# ============================================================
# AUTO-UPDATE (runs silently on every launch)
# ============================================================

if [[ "$1" != "--skip-update" ]]; then
    _GREEN='\033[0;32m'
    _YELLOW='\033[1;33m'
    _NC='\033[0m'

    SCRIPT_PATH="$APP_DIR/JobHunter.command"
    HASH_BEFORE=$(md5 -q "$SCRIPT_PATH" 2>/dev/null || echo "")

    echo -e "${_YELLOW}Checking for updates...${_NC}"

    # Stash local changes if any
    if [[ -n $(git status --porcelain 2>/dev/null) ]]; then
        git stash push -m "JobHunter auto-update $(date +%Y%m%d_%H%M%S)" --quiet 2>/dev/null
        STASHED=true
    else
        STASHED=false
    fi

    # Pull updates (10s timeout, silent failures)
    if timeout 10 git pull --quiet origin main 2>/dev/null; then
        echo -e "${_GREEN}Up to date${_NC}"
    elif git pull --quiet origin main 2>/dev/null; then
        echo -e "${_GREEN}Up to date${_NC}"
    else
        echo -e "${_YELLOW}Offline - continuing with current version${_NC}"
    fi

    # Restore stashed changes
    if [[ "$STASHED" == "true" ]]; then
        git stash pop --quiet 2>/dev/null || true
    fi

    # Re-exec if script itself was updated
    HASH_AFTER=$(md5 -q "$SCRIPT_PATH" 2>/dev/null || echo "")
    if [[ -n "$HASH_BEFORE" && "$HASH_BEFORE" != "$HASH_AFTER" ]]; then
        echo -e "${_GREEN}Updated! Restarting...${_NC}"
        exec "$SCRIPT_PATH" --skip-update
    fi

    echo ""
fi

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Pretty print functions
print_header() {
    echo ""
    echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}  🎯 Job Hunter${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "   $1"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================
# MAIN SETUP
# ============================================================

print_header

echo "This script will set up everything you need."
echo "First-time setup takes about 10-15 minutes."
echo "After that, it starts instantly!"
echo ""

# ------------------------------------------------------------
# Step 1: Xcode Command Line Tools (needed for everything)
# ------------------------------------------------------------
print_step "Checking for developer tools..."

if ! xcode-select -p &>/dev/null; then
    print_warning "Installing Xcode Command Line Tools..."
    print_info "A popup will appear - click 'Install' and wait for it to finish."
    print_info "Then run this script again."
    xcode-select --install
    echo ""
    echo "After the installation finishes, double-click this file again!"
    echo ""
    read -p "Press Enter to exit..."
    exit 0
else
    print_success "Developer tools ready"
fi

# ------------------------------------------------------------
# Step 2: Homebrew (Mac package manager)
# ------------------------------------------------------------
print_step "Checking for Homebrew..."

if ! command_exists brew; then
    print_warning "Installing Homebrew (this takes a few minutes)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    
    print_success "Homebrew installed"
else
    print_success "Homebrew ready"
fi

# Make sure brew is in PATH (for Apple Silicon)
if [[ -f "/opt/homebrew/bin/brew" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# ------------------------------------------------------------
# Step 3: Python 3
# ------------------------------------------------------------
print_step "Checking for Python..."

if ! command_exists python3; then
    print_warning "Installing Python..."
    brew install python3
    print_success "Python installed"
else
    print_success "Python ready ($(python3 --version))"
fi

# ------------------------------------------------------------
# Step 4: Ollama (Local AI)
# ------------------------------------------------------------
print_step "Checking for Ollama (the AI engine)..."

if ! command_exists ollama; then
    print_warning "Installing Ollama..."
    brew install ollama
    print_success "Ollama installed"
else
    print_success "Ollama ready"
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    print_step "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
    print_success "Ollama started"
fi

# Check if the AI model is downloaded
print_step "Checking for AI model..."

if ! ollama list 2>/dev/null | grep -q "llama3.1:8b"; then
    print_warning "Downloading AI model (about 5GB, one-time download)..."
    print_info "This will take 5-10 minutes depending on your internet speed."
    print_info "Go grab a coffee! ☕"
    echo ""
    ollama pull llama3.1:8b
    print_success "AI model ready"
else
    print_success "AI model ready"
fi

# ------------------------------------------------------------
# Step 5: LaTeX (for PDF generation)
# ------------------------------------------------------------
print_step "Checking for LaTeX (PDF generator)..."

if ! command_exists pdflatex; then
    print_warning "Installing LaTeX (this takes a few minutes)..."
    brew install --cask basictex
    
    # Add LaTeX to PATH
    export PATH="/Library/TeX/texbin:$PATH"
    echo 'export PATH="/Library/TeX/texbin:$PATH"' >> ~/.zprofile
    
    # Install required LaTeX packages
    print_info "Installing LaTeX packages..."
    sudo tlmgr update --self 2>/dev/null || true
    sudo tlmgr install collection-fontsrecommended titlesec enumitem 2>/dev/null || true
    
    print_success "LaTeX installed"
else
    print_success "LaTeX ready"
fi

# Make sure LaTeX is in PATH
export PATH="/Library/TeX/texbin:$PATH"

# ------------------------------------------------------------
# Step 6: Python Virtual Environment & Dependencies
# ------------------------------------------------------------
print_step "Setting up the app..."

cd "$APP_DIR"

if [ ! -d "venv" ]; then
    print_info "Creating Python environment..."
    python3 -m venv venv
    VENV_CREATED=true
else
    VENV_CREATED=false
fi

source venv/bin/activate

# Track if requirements have changed since last install
REQ_HASH_FILE="venv/.requirements_hash"
CURRENT_HASH=$(md5 -q requirements.txt 2>/dev/null || md5sum requirements.txt | cut -d' ' -f1)
STORED_HASH=$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")

if [[ "$VENV_CREATED" == "true" ]] || [[ "$CURRENT_HASH" != "$STORED_HASH" ]]; then
    print_info "Installing/updating Python packages..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
    print_success "Python packages updated"
else
    print_success "Python packages ready"
fi

print_success "App ready"

# ------------------------------------------------------------
# Step 7: Launch!
# ------------------------------------------------------------
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎉 All set! Starting Job Hunter...${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Opening in your browser: ${NC}${YELLOW}http://localhost:5050${NC}"
echo ""
echo -e "  ${PURPLE}To stop the app, close this window or press Ctrl+C${NC}"
echo ""

# Wait a moment then open browser
(sleep 2 && open "http://localhost:5050") &

# Start the app
python app.py
