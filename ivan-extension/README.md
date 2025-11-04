# Ivan Assistant Chrome Extension

A Chrome extension that integrates with your Ivan AI assistant to fill form fields intelligently, eliminating the copy-paste workflow.

## Features

- **Smart Field Selection**: Click on any text input, textarea, or contenteditable element
- **Context-Aware**: Automatically includes current field values as context
- **Direct Integration**: Communicates directly with your local Ivan instance
- **Seamless Workflow**: Generate and insert text without leaving your browser

## Prerequisites

1. Ivan must be running locally (default: `http://localhost:8000`)
2. Chrome or Chromium-based browser (Edge, Brave, etc.)

## Installation

### 1. Start Ivan

Make sure Ivan is running:

```bash
cd /path/to/Ivan
source venv/bin/activate
python ivan.py
```

### 2. Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right corner)
3. Click "Load unpacked"
4. Select the `ivan-extension` folder
5. The Ivan Assistant icon should appear in your extensions toolbar

## Usage

### Basic Workflow

1. **Navigate to any webpage** with a form or text field
2. **Click the Ivan Assistant icon** in your Chrome toolbar
3. **Click "Select Field on Page"** button
4. **Click on the input field** you want to fill (it will highlight on hover)
5. **Enter your prompt** describing what you want Ivan to write
6. **Click "Send to Ivan"** and wait for the response
7. **Click "Insert into Field"** to fill the selected field

### Example Use Cases

#### Email Drafting
- Select the email body field
- Prompt: "Draft a professional follow-up email after yesterday's meeting"
- Insert the generated response

#### Form Filling
- Select a description field
- Prompt: "Write a brief professional bio for a software engineer"
- Insert the generated text

#### Content Creation
- Select a comment or post field
- Prompt: "Write a thoughtful comment about this article, focusing on the AI implications"
- Insert the generated comment

## Settings

Click the ⚙️ icon to configure:

- **Ivan Endpoint**: Change if Ivan is running on a different port (default: `http://localhost:8000`)

## How It Works

1. **Content Script** (`content.js`): Runs on all web pages, detects and highlights input fields
2. **Popup UI** (`popup.html/js`): Provides the interface for interacting with Ivan
3. **Background Service** (`background.js`): Manages extension lifecycle and settings
4. **Ivan API**: Extension sends requests to `/v1/chat/completions` endpoint

## Troubleshooting

### "Content script not loaded" error
- **Solution**: Refresh the webpage and try again. The extension needs to initialize on the page.

### "Error calling Ivan" message
- **Check**: Is Ivan running? Try accessing `http://localhost:8000/health` in your browser
- **Check**: Is the correct endpoint configured in extension settings?
- **Check**: Are you using the correct port? (default is 8000)

### Field won't highlight
- **Try**: Refreshing the page
- **Note**: Some fields may be protected or use custom implementations that aren't detected

### Text not inserting
- **Try**: Clicking the field manually first, then using the extension
- **Note**: Some sites use complex form frameworks that may interfere

## Privacy & Security

- All data stays local - communication is only between your browser and local Ivan instance
- No external servers or third-party services are contacted
- The extension requires minimal permissions (activeTab, storage)

## Development

### File Structure

```
ivan-extension/
├── manifest.json       # Extension configuration
├── background.js       # Background service worker
├── content.js          # Page interaction script
├── content.css         # Field highlighting styles
├── popup.html          # Extension popup UI
├── popup.js            # Popup logic
├── popup.css           # Popup styles
├── icon*.png           # Extension icons
└── README.md          # This file
```

### Modifying the Extension

After making changes:
1. Go to `chrome://extensions/`
2. Click the refresh icon on the Ivan Assistant card
3. Reload any open tabs to see changes

## Future Enhancements

Potential features for future versions:
- Template library for common prompts
- Keyboard shortcuts for quick access
- Multi-field filling
- Context extraction from surrounding page content
- Streaming responses for faster feedback
- History of generated responses
- Custom field detection rules

## License

Same as Ivan project

## Support

For issues or questions:
1. Check the Ivan main project documentation
2. Ensure Ivan is running and accessible
3. Check browser console for detailed error messages (F12 → Console)
