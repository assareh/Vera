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
    "splash.png:splash.png"
    "splash-dark.png:splash-dark.png"
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

# Also copy favicon.png to the frontend root directory (outside static/)
if [ -n "$OPENWEBUI_FRONTEND_STATIC" ] && [ -f "$BRANDING_DIR/favicons/favicon.png" ]; then
    cp "$BRANDING_DIR/favicons/favicon.png" "$OPENWEBUI_FRONTEND_STATIC/../favicon.png"
fi

echo -e "${GREEN}✓ Favicons and logos applied${NC}"

# Apply carousel/splash screen images
echo "🖼️  Applying HashiCorp carousel images for onboarding splash screen..."

CAROUSEL_SOURCE_DIR="$BRANDING_DIR/carousel_images"
if [ -d "$CAROUSEL_SOURCE_DIR" ]; then
    CAROUSEL_TARGET=""
    if [ -n "$OPENWEBUI_FRONTEND_STATIC" ] && [ -d "$OPENWEBUI_FRONTEND_STATIC/../assets/images" ]; then
        CAROUSEL_TARGET="$OPENWEBUI_FRONTEND_STATIC/../assets/images"
    elif [ -d "$OPENWEBUI_STATIC/../assets/images" ]; then
        CAROUSEL_TARGET="$OPENWEBUI_STATIC/../assets/images"
    fi

    if [ -n "$CAROUSEL_TARGET" ]; then
        # Replace default carousel images with HashiCorp-branded ones
        [ -f "$CAROUSEL_SOURCE_DIR/image1.jpg" ] && cp "$CAROUSEL_SOURCE_DIR/image1.jpg" "$CAROUSEL_TARGET/adam.jpg"
        [ -f "$CAROUSEL_SOURCE_DIR/image2.jpg" ] && cp "$CAROUSEL_SOURCE_DIR/image2.jpg" "$CAROUSEL_TARGET/galaxy.jpg"
        [ -f "$CAROUSEL_SOURCE_DIR/image3.jpg" ] && cp "$CAROUSEL_SOURCE_DIR/image3.jpg" "$CAROUSEL_TARGET/earth.jpg"
        [ -f "$CAROUSEL_SOURCE_DIR/image4.jpg" ] && cp "$CAROUSEL_SOURCE_DIR/image4.jpg" "$CAROUSEL_TARGET/space.jpg"
        echo -e "${GREEN}✓ Carousel images applied${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: Could not find carousel images directory${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Warning: Carousel images not found in branding directory${NC}"
fi

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

    # Replace splash screen text with HashiCorp/Ivan branding
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Discover wonders/Accelerate innovation/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/wherever you are/with Ivan AI/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Explore the cosmos/Simplify complexity/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Unlock mysteries/Unlock potential/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Chart new frontiers/Drive efficiency/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Dive into knowledge/Transform workflows/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Ignite curiosity/Empower teams/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Forge new paths/Optimize solutions/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Unravel secrets/Streamline processes/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Pioneer insights/Deliver value/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/Embark on adventures/Scale success/g' {} \;

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

    # Disable "What's New" changelog modal by default
    if grep -q "SHOW_ADMIN_DETAILS =" "$ENV_PY"; then
        # Add CHANGELOG setting after SHOW_ADMIN_DETAILS
        if ! grep -q "CHANGELOG_ENABLED" "$ENV_PY"; then
            sed -i.bak '/SHOW_ADMIN_DETAILS = /a\
CHANGELOG_ENABLED = os.environ.get("CHANGELOG_ENABLED", "False").lower() == "true"
' "$ENV_PY"
        fi
    fi

    echo -e "${GREEN}✓ Backend WEBUI_NAME updated${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not find env.py${NC}"
fi

# Disable "What's New" modal in JavaScript (set default to false)
echo "📝 Disabling \"What's New\" changelog modal..."
if [ -n "$APP_DIR" ] && [ -d "$APP_DIR" ]; then
    # Find and modify the JavaScript that controls the "What's New" setting
    # The setting is typically stored as showChangelog or whatsNewModal
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/showChangelog:!0/showChangelog:!1/g' {} \;
    find "$APP_DIR" -name "*.js" -type f -exec sed -i.bak 's/"whatsNew":true/"whatsNew":false/g' {} \;
    echo -e "${GREEN}✓ Changelog modal disabled${NC}"
fi

echo ""
echo -e "${GREEN}✅ HashiCorp branding applied successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Start Ivan: venv/bin/python3 ivan.py"
echo "  2. Visit http://localhost:8001"
echo "  3. Hard refresh your browser (Cmd+Shift+R) to see the new branding"
echo ""
