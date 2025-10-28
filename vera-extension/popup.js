// Popup script for Vera Assistant

let veraEndpoint = 'http://localhost:8000';
let conversationHistory = [];
let userInitials = null;
let latestCompleteUpdate = null;
let seWeeklyUpdateAvailable = false;
let seCurrentValue = '';
let currentPageUrl = '';

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Get current tab URL
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentPageUrl = tab.url;

  // Load settings
  await loadSettings();

  // Restore conversation state (will check URL match)
  await restoreState();

  // Set up event listeners
  setupEventListeners();

  // Check if SE Weekly Update field exists on the page
  await checkSEWeeklyUpdate();

  // Focus on chat input
  document.getElementById('chatInput').focus();

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'veraResponse') {
      // Response arrived from background
      handleVeraResponse(message.content);
      hideStatus();
    } else if (message.action === 'veraError') {
      showStatus(message.error, 'error');
    }
  });
});

// Load settings from storage
async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['veraEndpoint'], (result) => {
      if (result.veraEndpoint) {
        veraEndpoint = result.veraEndpoint;
        document.getElementById('veraEndpoint').value = veraEndpoint;
      }
      resolve();
    });
  });
}

// Save settings to storage
async function saveSettings() {
  const endpoint = document.getElementById('veraEndpoint').value;
  return new Promise((resolve) => {
    chrome.storage.sync.set({ veraEndpoint: endpoint }, () => {
      veraEndpoint = endpoint;
      resolve();
    });
  });
}

// Save conversation state to storage
async function saveState() {
  return new Promise((resolve) => {
    chrome.storage.local.set({
      conversationHistory: conversationHistory,
      latestCompleteUpdate: latestCompleteUpdate,
      userInitials: userInitials,
      pageUrl: currentPageUrl
    }, resolve);
  });
}

// Restore conversation state from storage
async function restoreState() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['conversationHistory', 'latestCompleteUpdate', 'userInitials', 'pageUrl'], (result) => {
      // Check if we're on a different page
      if (result.pageUrl && result.pageUrl !== currentPageUrl) {
        console.log('Page changed, clearing conversation state');
        clearState();
        resolve();
        return;
      }

      // Same page, restore state
      if (result.conversationHistory) {
        conversationHistory = result.conversationHistory;
        // Rebuild chat UI
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = ''; // Clear existing
        conversationHistory.forEach(msg => {
          if (msg.role === 'user' || msg.role === 'assistant') {
            addChatMessage(msg.role, msg.content, false); // Don't save again
          }
        });
      }
      if (result.latestCompleteUpdate) {
        latestCompleteUpdate = result.latestCompleteUpdate;
        // Show commit button if we have a complete update
        if (latestCompleteUpdate) {
          document.getElementById('commitBtn').classList.remove('hidden');
        }
      }
      if (result.userInitials) {
        userInitials = result.userInitials;
      }
      resolve();
    });
  });
}

// Clear conversation state
function clearState() {
  conversationHistory = [];
  latestCompleteUpdate = null;
  userInitials = null;

  // Clear UI
  const chatMessages = document.getElementById('chatMessages');
  chatMessages.innerHTML = '';
  document.getElementById('commitBtn').classList.add('hidden');

  // Clear storage
  chrome.storage.local.remove(['conversationHistory', 'latestCompleteUpdate', 'userInitials', 'pageUrl']);
}

// Set up event listeners
function setupEventListeners() {
  // Clear button
  document.getElementById('clearBtn').addEventListener('click', () => {
    if (confirm('Clear conversation and start fresh?')) {
      clearState();
      showStatus('Conversation cleared', 'success');
      setTimeout(hideStatus, 2000);
    }
  });

  // Settings
  document.getElementById('settingsBtn').addEventListener('click', toggleSettings);
  document.getElementById('saveSettings').addEventListener('click', async () => {
    await saveSettings();
    showStatus('Settings saved', 'success');
    toggleSettings();
  });
  document.getElementById('cancelSettings').addEventListener('click', () => {
    document.getElementById('veraEndpoint').value = veraEndpoint;
    toggleSettings();
  });

  // SE Weekly Update
  document.getElementById('seWeeklyBtn').addEventListener('click', completeSEWeeklyUpdate);

  // Chat
  document.getElementById('sendChatBtn').addEventListener('click', sendChatMessage);
  document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
  document.getElementById('commitBtn').addEventListener('click', commitUpdate);
}

// Toggle settings panel
function toggleSettings() {
  const settingsPanel = document.getElementById('settingsPanel');
  const mainPanel = document.getElementById('mainPanel');

  if (settingsPanel.classList.contains('hidden')) {
    settingsPanel.classList.remove('hidden');
    mainPanel.classList.add('hidden');
  } else {
    settingsPanel.classList.add('hidden');
    mainPanel.classList.remove('hidden');
  }
}


// Show status message
function showStatus(message, type) {
  const statusSection = document.getElementById('statusSection');
  const statusText = document.getElementById('statusText');

  statusText.textContent = message;
  statusText.className = `status ${type}`;
  statusSection.classList.remove('hidden');
}

// Hide status message
function hideStatus() {
  const statusSection = document.getElementById('statusSection');
  statusSection.classList.add('hidden');
}

// Check if SE Weekly Update field exists on the page
async function checkSEWeeklyUpdate() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      { action: 'checkSEWeeklyUpdate' },
      (response) => {
        if (chrome.runtime.lastError) {
          console.log('Content script not ready or SE field not found');
          return;
        }

        if (response && response.exists) {
          // Mark as available
          seWeeklyUpdateAvailable = true;
          seCurrentValue = response.currentValue || '';
          userInitials = response.userInitials;

          // Show the quick actions section and SE button
          document.getElementById('quickActionsSection').classList.remove('hidden');
          document.getElementById('seWeeklyBtn').classList.remove('hidden');
        }
      }
    );
  } catch (error) {
    console.error('Error checking SE Weekly Update field:', error);
  }
}

// Complete SE Weekly Update (quick action)
async function completeSEWeeklyUpdate() {
  try {
    // Build the initial prompt
    let prompt = 'Please complete my SE weekly update.';

    if (userInitials) {
      prompt += `\n\nMy initials are: ${userInitials}`;
    }

    if (seCurrentValue) {
      prompt += `\n\nCurrent content:\n${seCurrentValue}`;
    }

    // Initialize conversation with this first message
    conversationHistory = [
      {
        role: 'user',
        content: prompt
      }
    ];

    // Get response from Vera
    const assistantMessage = await callVera();

    if (assistantMessage) {
      handleVeraResponse(assistantMessage);
    }
  } catch (error) {
    showStatus('Error: ' + error.message, 'error');
  }
}

// Call Vera API via background script (persists even if popup closes)
async function callVera() {
  try {
    showStatus('Sending to Vera...', 'loading');

    // Save state before making the call
    await saveState();

    // Send message to background script to handle the API call
    chrome.runtime.sendMessage({
      action: 'callVera',
      endpoint: veraEndpoint,
      messages: conversationHistory
    });

    // Note: Response will come back via chrome.runtime.onMessage listener
    // even if popup closes and reopens
    return null;

  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error');
    console.error('Error calling Vera:', error);
    return null;
  }
}

// Handle Vera's response (smart logic)
function handleVeraResponse(response) {
  // Add assistant response to conversation history
  conversationHistory.push({
    role: 'assistant',
    content: response
  });

  // Add to chat
  addChatMessage('assistant', response);

  // Check if response starts with [Summary of Opportunity] and SE field is available
  if (response.trim().startsWith('[Summary of Opportunity]') && seWeeklyUpdateAvailable) {
    latestCompleteUpdate = response;
    // Show commit button for SE updates
    document.getElementById('commitBtn').classList.remove('hidden');
    // Save updated state
    saveState();
  }
}

// Add a message to the chat
function addChatMessage(role, content, save = true) {
  const chatMessages = document.getElementById('chatMessages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;

  const header = document.createElement('div');
  header.className = 'chat-header';

  const label = document.createElement('div');
  label.className = 'chat-label';
  label.textContent = role === 'user' ? 'You' : 'Vera';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn';
  copyBtn.textContent = '📋';
  copyBtn.title = 'Copy to clipboard';
  copyBtn.onclick = () => copyToClipboard(content, copyBtn);

  header.appendChild(label);
  header.appendChild(copyBtn);

  const text = document.createElement('div');
  text.className = 'chat-text';
  text.textContent = content;

  messageDiv.appendChild(header);
  messageDiv.appendChild(text);
  chatMessages.appendChild(messageDiv);

  // Scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Save state if requested
  if (save) {
    saveState();
  }
}

// Copy text to clipboard
async function copyToClipboard(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    const originalText = button.textContent;
    button.textContent = '✓';
    button.classList.add('copied');
    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove('copied');
    }, 2000);
  } catch (error) {
    console.error('Failed to copy:', error);
    button.textContent = '✗';
    setTimeout(() => {
      button.textContent = '📋';
    }, 2000);
  }
}

// Send chat message
async function sendChatMessage() {
  const chatInput = document.getElementById('chatInput');
  const message = chatInput.value.trim();

  if (!message) return;

  // Add user message to chat
  addChatMessage('user', message);
  chatInput.value = '';

  // Add to conversation history
  conversationHistory.push({
    role: 'user',
    content: message
  });

  // Get response from Vera
  const assistantMessage = await callVera();

  if (assistantMessage) {
    handleVeraResponse(assistantMessage);
  }
}

// Commit update to page
async function commitUpdate() {
  if (!latestCompleteUpdate) {
    showStatus('No complete update to commit', 'error');
    return;
  }

  insertUpdateIntoPage(latestCompleteUpdate);
}

// Insert update into the page
async function insertUpdateIntoPage(text) {
  try {
    showStatus('Inserting into field...', 'loading');

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      {
        action: 'fillSEWeeklyUpdate',
        text: text
      },
      (fillResponse) => {
        if (chrome.runtime.lastError || !fillResponse || !fillResponse.success) {
          showStatus('Failed to insert text', 'error');
          return;
        }

        showStatus('SE Weekly Update completed successfully!', 'success');
        setTimeout(() => {
          window.close();
        }, 1500);
      }
    );
  } catch (error) {
    showStatus('Error inserting text: ' + error.message, 'error');
  }
}
