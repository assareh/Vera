#!/usr/bin/env python3
"""Generate placeholder icons for the Vera extension."""

from PIL import Image, ImageDraw, ImageFont

def create_icon(size):
    """Create a simple icon with 'V' letter."""
    # Create a new image with a gradient background
    image = Image.new('RGB', (size, size), '#764ba2')
    draw = ImageDraw.Draw(image)

    # Draw a circle background
    padding = size // 8
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill='#667eea'
    )

    # Try to use a font, fall back to default if not available
    try:
        # Adjust font size based on icon size
        font_size = int(size * 0.6)
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        font = ImageFont.load_default()

    # Draw 'V' in the center
    text = "V"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1]

    draw.text((x, y), text, fill='white', font=font)

    return image

# Create icons in different sizes
sizes = [16, 48, 128]
for size in sizes:
    icon = create_icon(size)
    icon.save(f'icon{size}.png')
    print(f'Created icon{size}.png')

print('All icons created successfully!')
