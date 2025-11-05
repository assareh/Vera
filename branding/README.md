# HashiCorp Branding Assets

This directory contains the HashiCorp branding assets used to customize the Open Web UI interface for Ivan.

## Contents

### custom.css

Minimal custom CSS file for future styling if needed. Currently contains no color customizations - all branding is done through images/icons and text replacements.

### favicons/

HashiCorp logo in various sizes for favicons, app icons, and splash screens:

| File | Size | Usage |
|------|------|-------|
| `hashicorp.svg` | Vector | Modern browsers, high-DPI displays |
| `favicon.png` | 128×128 | Standard favicon |
| `favicon-96x96.png` | 96×96 | Older browsers |
| `apple-touch-icon.png` | 180×180 | iOS home screen |
| `web-app-manifest-192x192.png` | 192×192 | PWA icon (small) |
| `web-app-manifest-512x512.png` | 512×512 | PWA icon (large) |
| `splash.png` | 256×256 | Loading screen (light mode) |
| `splash-dark.png` | 256×256 | Loading screen (dark mode) |
| `hashicorp-logo-notext.png` | Source | HashiCorp logo without text |

### carousel_images/

Background images for the first-run onboarding splash screen carousel. These images cycle in the background of the "Accelerate innovation with Ivan AI" splash screen:

| File | Description |
|------|-------------|
| `image1.jpg` | First carousel image (replaces adam.jpg) |
| `image2.jpg` | Second carousel image (replaces galaxy.jpg) |
| `image3.jpg` | Third carousel image (replaces earth.jpg) |
| `image4.jpg` | Fourth carousel image (replaces space.jpg) |

**Default:** Currently uses HashiCorp logo/branding images. You can replace these with any JPG images (recommended size: 1920×1080 or larger for best quality on high-DPI displays).

## Applying Branding

From the project root, run:

```bash
./apply_branding.sh
```

This script:
- Copies all favicon/logo assets to the Open Web UI installation
- Replaces all "Open WebUI" text with "Ivan" in HTML and JavaScript files
- Replaces onboarding splash screen background images with HashiCorp branding
- Replaces splash screen text with HashiCorp/Ivan-themed phrases
- Updates the backend WEBUI_NAME configuration
- Applies minimal custom CSS

**Note**: Run this script whenever you reinstall or upgrade Open Web UI to reapply the branding.

## What Gets Branded

The branding script customizes:
1. **Page title**: "Open WebUI" → "Ivan"
2. **All UI text**: "Open WebUI" → "Ivan" throughout the interface
3. **Favicon**: HashiCorp hexagon logo
4. **Splash screen images**: HashiCorp-branded carousel backgrounds for first-run onboarding
5. **Splash screen text**: Enterprise-focused phrases like "Accelerate innovation with Ivan AI"
6. **PWA icons**: HashiCorp branding for installed web app

## Customization

### Custom Logo

Replace the files in `favicons/` with your own:
1. Create your logo in SVG format (save as `hashicorp.svg`)
2. Generate PNG versions at different sizes
3. Run `./apply_branding.sh` to apply

### Logo Generation from Image

If you have a source logo image, you can generate the required sizes using macOS `sips`:

```bash
# Standard favicons
sips -z 128 128 logo.png --out favicon.png
sips -z 96 96 logo.png --out favicon-96x96.png
sips -z 180 180 logo.png --out apple-touch-icon.png

# PWA icons
sips -z 192 192 logo.png --out web-app-manifest-192x192.png
sips -z 512 512 logo.png --out web-app-manifest-512x512.png

# Splash screens
sips -z 256 256 logo.png --out splash.png
sips -z 256 256 logo.png --out splash-dark.png
```

## Resources

- [HashiCorp Brand Guidelines](https://brand.hashicorp.com/)
- [Helios Design System](https://helios.hashicorp.design/)
- [HashiCorp Logos](https://www.hashicorp.com/brand)

## License Note

The HashiCorp logo and branding are trademarks of HashiCorp, Inc. This customization is for internal use and does not imply official endorsement by HashiCorp.
