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
  } else if (request.action === 'callVera') {
    // Handle Vera API call in background
    handleVeraCall(request.endpoint, request.messages);
  }

  return true;
});

// Handle Vera API call
async function handleVeraCall(endpoint, messages) {
  try {
    console.log('Background: Calling Vera API...');

    const response = await fetch(`${endpoint}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: messages,
        temperature: 0.7,
        stream: false
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const assistantMessage = data.choices[0].message.content;

    console.log('Background: Vera response received');

    // Store the response in chrome.storage for persistence
    chrome.storage.local.get(['conversationHistory'], (result) => {
      const history = result.conversationHistory || [];
      history.push({
        role: 'assistant',
        content: assistantMessage
      });

      chrome.storage.local.set({ conversationHistory: history }, () => {
        console.log('Background: Response saved to storage');
      });
    });

    // Try to send to popup if it's open
    chrome.runtime.sendMessage({
      action: 'veraResponse',
      content: assistantMessage
    }).catch(() => {
      // Popup not open, that's okay - message is stored
      console.log('Background: Popup not open, response stored for later');
    });

  } catch (error) {
    console.error('Background: Error calling Vera:', error);

    // Try to send error to popup if it's open
    chrome.runtime.sendMessage({
      action: 'veraError',
      error: `Error: ${error.message}. Make sure Vera is running on ${endpoint}`
    }).catch(() => {
      // Popup not open
      console.log('Background: Error occurred but popup not open');
    });
  }
}
