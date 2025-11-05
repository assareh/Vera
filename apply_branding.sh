#!/bin/bash
#
# Apply HashiCorp branding to Open Web UI
# This script copies custom CSS and favicon files to the Open Web UI installation
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRANDING_DIR="$SCRIPT_DIR/branding"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🎨 Applying HashiCorp branding to Open Web UI..."
echo ""

# Find Open Web UI installation
OPENWEBUI_STATIC=""
if [ -d "$SCRIPT_DIR/venv/lib/python3.12/site-packages/open_webui/static" ]; then
    OPENWEBUI_STATIC="$SCRIPT_DIR/venv/lib/python3.12/site-packages/open_webui/static"
elif [ -d "$SCRIPT_DIR/venv/lib/python3.11/site-packages/open_webui/static" ]; then
    OPENWEBUI_STATIC="$SCRIPT_DIR/venv/lib/python3.11/site-packages/open_webui/static"
else
    # Try to find it dynamically
    OPENWEBUI_STATIC=$(find "$SCRIPT_DIR/venv/lib" -type d -path "*/open_webui/static" 2>/dev/null | head -1)
fi

OPENWEBUI_FRONTEND_STATIC=""
if [ -d "$SCRIPT_DIR/venv/lib/python3.12/site-packages/open_webui/frontend/static" ]; then
    OPENWEBUI_FRONTEND_STATIC="$SCRIPT_DIR/venv/lib/python3.12/site-packages/open_webui/frontend/static"
elif [ -d "$SCRIPT_DIR/venv/lib/python3.11/site-packages/open_webui/frontend/static" ]; then
    OPENWEBUI_FRONTEND_STATIC="$SCRIPT_DIR/venv/lib/python3.11/site-packages/open_webui/frontend/static"
else
    # Try to find it dynamically
    OPENWEBUI_FRONTEND_STATIC=$(find "$SCRIPT_DIR/venv/lib" -type d -path "*/open_webui/frontend/static" 2>/dev/null | head -1)
fi

# Check if Open Web UI is installed
if [ -z "$OPENWEBUI_STATIC" ] || [ ! -d "$OPENWEBUI_STATIC" ]; then
    echo -e "${RED}✗ Error: Open Web UI not found in venv${NC}"
    echo "  Please install it first with: pip install open-webui"
    exit 1
fi

echo -e "${GREEN}✓ Found Open Web UI installation${NC}"
echo "  Main static: $OPENWEBUI_STATIC"
if [ -n "$OPENWEBUI_FRONTEND_STATIC" ]; then
    echo "  Frontend static: $OPENWEBUI_FRONTEND_STATIC"
fi
echo ""

# Apply custom CSS
echo "📝 Applying custom HashiCorp CSS theme..."
if [ -f "$BRANDING_DIR/custom.css" ]; then
    cp "$BRANDING_DIR/custom.css" "$OPENWEBUI_STATIC/custom.css"
    [ -n "$OPENWEBUI_FRONTEND_STATIC" ] && cp "$BRANDING_DIR/custom.css" "$OPENWEBUI_FRONTEND_STATIC/custom.css"
    echo -e "${GREEN}✓ Custom CSS applied${NC}"
else
    echo -e "${RED}✗ custom.css not found in branding directory${NC}"
    exit 1
fi

# Apply favicons
echo "🖼️  Applying HashiCorp favicons and logos..."

FAVICON_FILES=(
    "hashicorp.svg:favicon.svg"
    "favicon.png:favicon.png"
    "favicon.png:favicon.ico"
    "favicon.png:favicon-dark.png"
    "favicon-96x96.png:favicon-96x96.png"
    "apple-touch-icon.png:apple-touch-icon.png"
    "favicon.png:logo.png"
    "web-app-manifest-192x192.png:web-app-manifest-192x192.png"
    "web-app-manifest-512x512.png:web-app-manifest-512x512.png"
)

for mapping in "${FAVICON_FILES[@]}"; do
    source_file="${mapping%%:*}"
    dest_file="${mapping##*:}"

    if [ -f "$BRANDING_DIR/favicons/$source_file" ]; then
        cp "$BRANDING_DIR/favicons/$source_file" "$OPENWEBUI_STATIC/$dest_file"
        [ -n "$OPENWEBUI_FRONTEND_STATIC" ] && cp "$BRANDING_DIR/favicons/$source_file" "$OPENWEBUI_FRONTEND_STATIC/$dest_file"
    else
        echo -e "${YELLOW}⚠ Warning: $source_file not found, skipping${NC}"
    fi
done

echo -e "${GREEN}✓ Favicons and logos applied${NC}"

# Apply text changes (page title and sign-in text)
echo "📝 Applying Ivan branding to text..."

# Change page title
sed -i.bak 's/<title>Open WebUI<\/title>/<title>Ivan<\/title>/g' "$OPENWEBUI_STATIC/../index.html" 2>/dev/null || true
[ -n "$OPENWEBUI_FRONTEND_STATIC" ] && sed -i.bak 's/<title>Open WebUI<\/title>/<title>Ivan<\/title>/g' "$OPENWEBUI_FRONTEND_STATIC/../index.html" 2>/dev/null || true

# Replace "Open WebUI" with "Ivan" in all JavaScript files
echo "📝 Replacing 'Open WebUI' with 'Ivan' in JavaScript bundles..."
APP_DIR=""
if [ -n "$OPENWEBUI_FRONTEND_STATIC" ]; then
    APP_DIR="$OPENWEBUI_FRONTEND_STATIC/../_app"
elif [ -d "$OPENWEBUI_STATIC/../_app" ]; then
    APP_DIR="$OPENWEBUI_STATIC/../_app"
fi

if [ -n "$APP_DIR" ] && [ -d "$APP_DIR" ]; then
    # Find all .js files and replace "Open WebUI" with "Ivan"
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Open WebUI/Ivan/g' {} \;
    echo -e "${GREEN}✓ JavaScript text replacements applied${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not find _app directory${NC}"
fi

# Change authentication page text (additional specific replacements)
# Look for the auth JavaScript file in both possible locations
AUTH_JS=""
if [ -n "$OPENWEBUI_FRONTEND_STATIC" ]; then
    AUTH_JS=$(find "$OPENWEBUI_FRONTEND_STATIC/../_app/immutable/nodes" -name "*.js" -exec grep -l "Sign in to.*WEBUI_NAME\|Sign in to Ivan" {} \; 2>/dev/null | head -1)
fi
if [ -z "$AUTH_JS" ]; then
    AUTH_JS=$(find "$OPENWEBUI_STATIC/../_app/immutable/nodes" -name "*.js" -exec grep -l "Sign in to.*WEBUI_NAME\|Sign in to Ivan" {} \; 2>/dev/null | head -1)
fi

if [ -n "$AUTH_JS" ]; then
    # Replace Open WebUI branding with Ivan
    sed -i.bak 's/Sign in to {{WEBUI_NAME}}/Sign in to Ivan/g' "$AUTH_JS"
    sed -i.bak 's/Sign up to {{WEBUI_NAME}}/Sign up to Ivan/g' "$AUTH_JS"
    sed -i.bak 's/Signing in to {{WEBUI_NAME}}/Signing in to Ivan/g' "$AUTH_JS"
    sed -i.bak 's/Sign in to {{WEBUI_NAME}} with LDAP/Sign in to Ivan with LDAP/g' "$AUTH_JS"
    sed -i.bak 's/Get started with {{WEBUI_NAME}}/Get started with Ivan/g' "$AUTH_JS"
    echo -e "${GREEN}✓ Authentication text branding applied${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not find authentication JavaScript file (this is normal if already applied)${NC}"
fi

# Update backend WEBUI_NAME configuration
echo "📝 Updating backend WEBUI_NAME configuration..."
ENV_PY=""
if [ -n "$OPENWEBUI_FRONTEND_STATIC" ]; then
    ENV_PY="$OPENWEBUI_FRONTEND_STATIC/../../env.py"
elif [ -f "$OPENWEBUI_STATIC/../env.py" ]; then
    ENV_PY="$OPENWEBUI_STATIC/../env.py"
fi

if [ -n "$ENV_PY" ] && [ -f "$ENV_PY" ]; then
    # Change default WEBUI_NAME from "Open WebUI" to "Ivan"
    sed -i.bak 's/WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")/WEBUI_NAME = os.environ.get("WEBUI_NAME", "Ivan")/g' "$ENV_PY"
    # Remove the line that appends " (Open WebUI)"
    sed -i.bak '/if WEBUI_NAME != "Open WebUI":/,+1d' "$ENV_PY"
    echo -e "${GREEN}✓ Backend WEBUI_NAME updated${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not find env.py${NC}"
fi

echo ""
echo -e "${GREEN}✅ HashiCorp branding applied successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Start Ivan: venv/bin/python3 ivan.py"
echo "  2. Visit http://localhost:8001"
echo "  3. Hard refresh your browser (Cmd+Shift+R) to see the new branding"
echo ""
