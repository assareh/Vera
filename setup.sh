#!/bin/bash
set -e

echo "=== Ivan Setup Script ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REQUIRED_PYTHON="3.12.0"

# Initialize pyenv if it exists
if command -v pyenv &> /dev/null; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo -e "${RED}Error: pyenv is not installed${NC}"
    echo ""
    echo "Please install pyenv first:"
    echo "  macOS: brew install pyenv"
    echo "  Linux: curl https://pyenv.run | bash"
    echo ""
    echo "Then add to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo '  export PYENV_ROOT="$HOME/.pyenv"'
    echo '  export PATH="$PYENV_ROOT/bin:$PATH"'
    echo '  eval "$(pyenv init -)"'
    exit 1
fi

echo -e "${GREEN}✓${NC} pyenv is installed"

# Check if required Python version is installed
if ! pyenv versions --bare | grep -q "^${REQUIRED_PYTHON}$"; then
    echo -e "${YELLOW}Installing Python ${REQUIRED_PYTHON}...${NC}"
    pyenv install ${REQUIRED_PYTHON}
else
    echo -e "${GREEN}✓${NC} Python ${REQUIRED_PYTHON} is installed"
fi

# Set local Python version
echo -e "${YELLOW}Setting local Python version to ${REQUIRED_PYTHON}...${NC}"
pyenv local ${REQUIRED_PYTHON}

# Verify Python version
CURRENT_PYTHON=$(python --version 2>&1 | awk '{print $2}')
if [ "$CURRENT_PYTHON" != "$REQUIRED_PYTHON" ]; then
    echo -e "${RED}Error: Python version mismatch${NC}"
    echo "Expected: ${REQUIRED_PYTHON}"
    echo "Got: ${CURRENT_PYTHON}"
    echo ""
    echo "Try running: eval \"\$(pyenv init -)\" and then run this script again"
    exit 1
fi

echo -e "${GREEN}✓${NC} Using Python ${CURRENT_PYTHON}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python -m venv venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Apply HashiCorp branding to Open Web UI
echo ""
echo -e "${YELLOW}Applying HashiCorp branding...${NC}"
if [ -f "./apply_branding.sh" ]; then
    ./apply_branding.sh
else
    echo -e "${YELLOW}⚠ Warning: apply_branding.sh not found, skipping branding${NC}"
fi

echo ""
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To start Ivan, run:"
echo "  python ivan.py"
echo ""
