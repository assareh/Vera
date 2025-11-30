#!/bin/bash
set -e

echo "=== Ivan Setup Script ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo -e "${GREEN}✓${NC} uv installed successfully"
    echo ""
    echo -e "${YELLOW}Please run this script again or add uv to your PATH:${NC}"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    exit 0
fi

echo -e "${GREEN}✓${NC} uv is installed"
echo ""

# Install Python and dependencies
echo -e "${YELLOW}Installing Python 3.12.0 and dependencies...${NC}"
uv sync --extra webui

echo ""
echo -e "${GREEN}✓${NC} Dependencies installed"
echo ""

# Create .env if it doesn't exist
echo -e "${YELLOW}Setting up configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} Created .env from .env.example"
        echo -e "  ${YELLOW}Please edit .env to configure your backend settings${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} .env already exists"
fi

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
echo "To start Ivan, run:"
echo "  uv run python ivan.py"
echo ""
echo "Or without the WebUI:"
echo "  uv run python ivan.py --no-webui"
echo ""
echo "Note: Before running, make sure you have:"
echo "  1. Configured .env with your backend settings (LM Studio or Ollama)"
echo "  2. LM Studio or Ollama running with a model loaded"
echo "  3. (Optional) Customer_Notes directory symlinked"
echo ""
