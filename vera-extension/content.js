// Content script for detecting and interacting with form fields

let selectedField = null;
let overlay = null;

// Initialize the extension
function init() {
  console.log('Vera Assistant content script loaded');

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'selectField') {
      enableFieldSelection();
      sendResponse({ success: true });
    } else if (request.action === 'getSelectedField') {
      sendResponse({
        hasSelection: selectedField !== null,
        fieldInfo: selectedField ? getFieldInfo(selectedField) : null
      });
    } else if (request.action === 'insertText') {
      if (selectedField) {
        insertTextIntoField(selectedField, request.text);
        sendResponse({ success: true });
      } else {
        sendResponse({ success: false, error: 'No field selected' });
      }
    } else if (request.action === 'cancelSelection') {
      cancelFieldSelection();
      sendResponse({ success: true });
    } else if (request.action === 'checkSEWeeklyUpdate') {
      // Check if SE Weekly Update field exists
      const seField = document.getElementById('SE_Weekly_Update__c');
      if (seField) {
        sendResponse({
          exists: true,
          currentValue: seField.value || ''
        });
      } else {
        sendResponse({ exists: false });
      }
    } else if (request.action === 'fillSEWeeklyUpdate') {
      // Fill the SE Weekly Update field
      const seField = document.getElementById('SE_Weekly_Update__c');
      if (seField) {
        insertTextIntoField(seField, request.text);
        sendResponse({ success: true });
      } else {
        sendResponse({ success: false, error: 'SE Weekly Update field not found' });
      }
    }
    return true; // Keep channel open for async response
  });
}

// Get information about a field
function getFieldInfo(field) {
  const tagName = field.tagName.toLowerCase();
  const type = field.type || 'text';
  const placeholder = field.placeholder || '';
  const label = findFieldLabel(field);
  const currentValue = field.value || field.textContent || '';

  return {
    tagName,
    type,
    placeholder,
    label,
    currentValue,
    isContentEditable: field.isContentEditable
  };
}

// Find the label associated with a field
function findFieldLabel(field) {
  // Try to find label by for attribute
  if (field.id) {
    const label = document.querySelector(`label[for="${field.id}"]`);
    if (label) return label.textContent.trim();
  }

  // Try to find parent label
  const parentLabel = field.closest('label');
  if (parentLabel) {
    return parentLabel.textContent.replace(field.value, '').trim();
  }

  // Try aria-label
  if (field.getAttribute('aria-label')) {
    return field.getAttribute('aria-label');
  }

  // Try nearby text
  const prev = field.previousElementSibling;
  if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'DIV')) {
    return prev.textContent.trim();
  }

  return field.name || field.id || 'Unnamed field';
}

// Enable field selection mode
function enableFieldSelection() {
  // Create overlay
  overlay = document.createElement('div');
  overlay.id = 'vera-overlay';
  overlay.innerHTML = `
    <div class="vera-overlay-message">
      Click on a text field to select it, or press ESC to cancel
    </div>
  `;
  document.body.appendChild(overlay);

  // Add event listeners for field detection
  document.addEventListener('mouseover', highlightField, true);
  document.addEventListener('mouseout', unhighlightField, true);
  document.addEventListener('click', selectField, true);
  document.addEventListener('keydown', handleEscape, true);
}

// Cancel field selection
function cancelFieldSelection() {
  document.removeEventListener('mouseover', highlightField, true);
  document.removeEventListener('mouseout', unhighlightField, true);
  document.removeEventListener('click', selectField, true);
  document.removeEventListener('keydown', handleEscape, true);

  if (overlay) {
    overlay.remove();
    overlay = null;
  }

  // Remove any highlight
  document.querySelectorAll('.vera-highlight').forEach(el => {
    el.classList.remove('vera-highlight');
  });
}

// Check if element is a valid input field
function isValidField(element) {
  const tagName = element.tagName.toLowerCase();

  // Text inputs
  if (tagName === 'input') {
    const type = element.type.toLowerCase();
    return ['text', 'email', 'search', 'url', 'tel', 'password'].includes(type);
  }

  // Textareas
  if (tagName === 'textarea') {
    return true;
  }

  // Content editable elements
  if (element.isContentEditable) {
    return true;
  }

  return false;
}

// Highlight field on hover
function highlightField(event) {
  if (isValidField(event.target)) {
    event.target.classList.add('vera-highlight');
  }
}

// Remove highlight on mouse out
function unhighlightField(event) {
  if (isValidField(event.target)) {
    event.target.classList.remove('vera-highlight');
  }
}

// Select field on click
function selectField(event) {
  if (isValidField(event.target)) {
    event.preventDefault();
    event.stopPropagation();

    selectedField = event.target;
    selectedField.classList.add('vera-selected');

    // Clean up selection mode
    cancelFieldSelection();

    // Notify popup
    chrome.runtime.sendMessage({
      action: 'fieldSelected',
      fieldInfo: getFieldInfo(selectedField)
    });
  }
}

// Handle escape key
function handleEscape(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    cancelFieldSelection();
    chrome.runtime.sendMessage({ action: 'selectionCancelled' });
  }
}

// Insert text into the selected field
function insertTextIntoField(field, text) {
  if (field.isContentEditable) {
    // For content editable elements
    field.textContent = text;

    // Trigger input event
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  } else {
    // For input/textarea elements
    field.value = text;
    field.focus();

    // Trigger events to ensure the page reacts
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Visual feedback
  field.style.backgroundColor = '#d4edda';
  setTimeout(() => {
    field.style.backgroundColor = '';
  }, 1000);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
