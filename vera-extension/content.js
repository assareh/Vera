// Content script for SE Weekly Update auto-fill

// Initialize the extension
function init() {
  console.log('Vera Assistant content script loaded');

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'checkSEWeeklyUpdate') {
      // Check if SE Weekly Update field exists
      const seField = document.getElementById('SE_Weekly_Update__c');
      if (seField) {
        // Try to get user initials from the avatar bubble
        const userInitials = getUserInitials();

        // Try to get opportunity title from modal
        const opportunityTitle = getOpportunityTitle();

        sendResponse({
          exists: true,
          currentValue: seField.value || '',
          userInitials: userInitials,
          opportunityTitle: opportunityTitle
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

// Get user initials from the avatar bubble
function getUserInitials() {
  try {
    // Look for element with both classes
    const avatarBubble = document.querySelector('.member-names__bubble.avatar-bg-2');
    if (avatarBubble && avatarBubble.textContent) {
      return avatarBubble.textContent.trim();
    }
    return null;
  } catch (error) {
    console.error('Error getting user initials:', error);
    return null;
  }
}

// Get opportunity title from modal
function getOpportunityTitle() {
  try {
    // Look for modal title element with class _modal_title__lviZX
    const modalTitle = document.querySelector('._modal_title__lviZX');
    if (modalTitle && modalTitle.textContent) {
      return modalTitle.textContent.trim();
    }
    return null;
  } catch (error) {
    console.error('Error getting opportunity title:', error);
    return null;
  }
}

// Insert text into a field
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
