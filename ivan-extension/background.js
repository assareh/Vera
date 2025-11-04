// Background service worker for Ivan Assistant

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('Ivan Assistant installed');

  // Set default settings
  chrome.storage.sync.get(['ivanEndpoint'], (result) => {
    if (!result.ivanEndpoint) {
      chrome.storage.sync.set({
        ivanEndpoint: 'http://localhost:8000'
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
  } else if (request.action === 'callIvan') {
    // Handle Ivan API call in background
    handleIvanCall(request.endpoint, request.messages);
  }

  return true;
});

// Handle Ivan API call
async function handleIvanCall(endpoint, messages) {
  try {
    console.log('Background: Calling Ivan API...');

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

    console.log('Background: Ivan response received');

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
      action: 'ivanResponse',
      content: assistantMessage
    }).catch(() => {
      // Popup not open, that's okay - message is stored
      console.log('Background: Popup not open, response stored for later');
    });

  } catch (error) {
    console.error('Background: Error calling Ivan:', error);

    // Try to send error to popup if it's open
    chrome.runtime.sendMessage({
      action: 'ivanError',
      error: `Error: ${error.message}. Make sure Ivan is running on ${endpoint}`
    }).catch(() => {
      // Popup not open
      console.log('Background: Error occurred but popup not open');
    });
  }
}
