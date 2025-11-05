# HashiCorp Branding Assets

This directory contains the HashiCorp branding assets used to customize the Open Web UI interface.

## Contents

### custom.css

Complete CSS theme file that applies HashiCorp branding:
- **Primary color**: HashiCorp Purple (#7B42BC - Terraform brand color)
- **Light purple**: #AC72F0 (for dark mode)
- **Surface colors**: #f9f2ff, #f4ecff
- **Border color**: #ebdbfc

The theme includes:
- Purple sidebar with light purple backgrounds
- Purple buttons and hover states
- Purple-themed links, inputs, and form elements
- Custom scrollbars with purple accents
- Purple message bubbles and containers
- Dark mode support (automatically adjusts colors)
- Accessibility features (reduced motion, proper contrast)

### favicons/

HashiCorp logo in various sizes for favicons and app icons:

| File | Size | Usage |
|------|------|-------|
| `hashicorp.svg` | Vector | Modern browsers, high-DPI displays |
| `favicon.png` | 128×128 | Standard favicon |
| `favicon-96x96.png` | 96×96 | Older browsers |
| `apple-touch-icon.png` | 180×180 | iOS home screen |
| `web-app-manifest-192x192.png` | 192×192 | PWA icon (small) |
| `web-app-manifest-512x512.png` | 512×512 | PWA icon (large) |

## Applying Branding

From the project root, run:

```bash
./apply_branding.sh
```

This copies all assets to the Open Web UI installation in your venv.

## Customization

### Changing Colors

Edit `custom.css` and modify the CSS variables in the `:root` section:

```css
:root {
  --hashicorp-purple: #7B42BC;        /* Primary purple */
  --hashicorp-purple-light: #AC72F0;  /* Light purple for dark mode */
  --hashicorp-surface: #f9f2ff;       /* Light background */
  /* ... other colors */
}
```

### Custom Logo

Replace the files in `favicons/` with your own:
1. Create your logo in SVG format (save as `hashicorp.svg`)
2. Generate PNG versions at different sizes
3. Run `./apply_branding.sh` to apply

### Logo Generation from SVG

If you have an SVG logo, you can generate PNGs using macOS `sips`:

```bash
sips -z 128 128 logo.svg --out favicon.png
sips -z 96 96 logo.svg --out favicon-96x96.png
sips -z 180 180 logo.svg --out apple-touch-icon.png
sips -z 192 192 logo.svg --out web-app-manifest-192x192.png
sips -z 512 512 logo.svg --out web-app-manifest-512x512.png
```

## Brand Colors Reference

From HashiCorp's Helios Design System:

### Product Colors
- **HashiCorp**: #000000 (Black)
- **Terraform**: #7B42BC (Purple) ← Used as primary
- **Vault**: #FFCF25 (Yellow)
- **Boundary**: #F24C53 (Red)
- **Consul**: #E03875 (Pink)
- **Nomad**: #06D092 (Green)
- **Packer**: #02A8EF (Blue)
- **Vagrant**: #1868F2 (Blue)

### Purple Scale
- **Purple-500**: #42215b (Dark)
- **Purple-400**: #7b00db
- **Purple-300**: #911ced
- **Purple-200**: #a737ff (Light)
- **Purple-100**: #ead2fe (Very light)
- **Purple-50**: #f9f2ff (Surface)

## Resources

- [HashiCorp Brand Guidelines](https://brand.hashicorp.com/)
- [Helios Design System](https://helios.hashicorp.design/)
- [HashiCorp Brand Colors](https://helios.hashicorp.design/foundations/colors)

## License Note

The HashiCorp logo and branding are trademarks of HashiCorp, Inc. This customization is for internal use and does not imply official endorsement by HashiCorp.
