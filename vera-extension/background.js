// Background service worker for Vera Assistant

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('Vera Assistant installed');

  // Set default settings
  chrome.storage.sync.get(['veraEndpoint'], (result) => {
    if (!result.veraEndpoint) {
      chrome.storage.sync.set({
        veraEndpoint: 'http://localhost:8000'
      });
    }
  });
});

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fieldSelected') {
    console.log('Field selected:', request.fieldInfo);
    // Could store this in chrome.storage if needed
  } else if (request.action === 'selectionCancelled') {
    console.log('Field selection cancelled');
  }

  return true;
});
