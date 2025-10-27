// Popup script for Vera Assistant

let veraEndpoint = 'http://localhost:8000';
let conversationHistory = [];
let userInitials = null;
let latestCompleteUpdate = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Load settings
  await loadSettings();

  // Set up event listeners
  setupEventListeners();

  // Check if SE Weekly Update field exists on the page
  await checkSEWeeklyUpdate();
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

// Set up event listeners
function setupEventListeners() {
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
          // Show the SE Weekly Update section
          document.getElementById('seWeeklySection').classList.remove('hidden');

          // Show the context section
          document.getElementById('contextSection').classList.remove('hidden');

          // Show current value if it exists
          if (response.currentValue) {
            const seCurrentValue = document.getElementById('seCurrentValue');
            seCurrentValue.textContent = 'Current: ' + response.currentValue.substring(0, 100) + (response.currentValue.length > 100 ? '...' : '');
            seCurrentValue.classList.remove('hidden');
          }
        }
      }
    );
  } catch (error) {
    console.error('Error checking SE Weekly Update field:', error);
  }
}

// Complete SE Weekly Update
async function completeSEWeeklyUpdate() {
  try {
    // Show loading status
    showStatus('Getting current SE update...', 'loading');

    // Get current field value
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      { action: 'checkSEWeeklyUpdate' },
      async (response) => {
        if (chrome.runtime.lastError || !response || !response.exists) {
          showStatus('SE Weekly Update field not found', 'error');
          return;
        }

        const currentValue = response.currentValue || '';
        const additionalContext = document.getElementById('promptInput').value.trim();
        userInitials = response.userInitials;

        // Build the initial prompt
        let prompt = 'Please complete my SE weekly update.';

        if (userInitials) {
          prompt += `\n\nMy initials are: ${userInitials}`;
        }

        if (additionalContext) {
          prompt += `\n\nAdditional context:\n${additionalContext}`;
        }

        if (currentValue) {
          prompt += `\n\nCurrent content:\n${currentValue}`;
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
      }
    );
  } catch (error) {
    showStatus('Error: ' + error.message, 'error');
  }
}

// Call Vera API with current conversation history
async function callVera() {
  try {
    showStatus('Sending to Vera...', 'loading');

    const veraResponse = await fetch(`${veraEndpoint}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: conversationHistory,
        temperature: 0.7,
        stream: false
      })
    });

    if (!veraResponse.ok) {
      throw new Error(`HTTP error! status: ${veraResponse.status}`);
    }

    const data = await veraResponse.json();
    const assistantMessage = data.choices[0].message.content;

    // Add assistant response to history
    conversationHistory.push({
      role: 'assistant',
      content: assistantMessage
    });

    hideStatus();
    return assistantMessage;

  } catch (error) {
    showStatus(`Error: ${error.message}. Make sure Vera is running on ${veraEndpoint}`, 'error');
    console.error('Error calling Vera:', error);
    return null;
  }
}

// Handle Vera's response (smart logic)
function handleVeraResponse(response) {
  // Check if response starts with [Summary of Opportunity]
  if (response.trim().startsWith('[Summary of Opportunity]')) {
    latestCompleteUpdate = response;

    // If we're already in chat mode, show the commit button
    if (!document.getElementById('chatSection').classList.contains('hidden')) {
      addChatMessage('assistant', response);
      document.getElementById('commitBtn').classList.remove('hidden');
    } else {
      // First response and it's complete - insert directly into page
      insertUpdateIntoPage(response);
    }
  } else {
    // Follow-up question - show chat interface
    showChatInterface();
    addChatMessage('assistant', response);
  }
}

// Show chat interface
function showChatInterface() {
  document.getElementById('seWeeklySection').classList.add('hidden');
  document.getElementById('contextSection').classList.add('hidden');
  document.getElementById('chatSection').classList.remove('hidden');
}

// Add a message to the chat
function addChatMessage(role, content) {
  const chatMessages = document.getElementById('chatMessages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;

  const label = document.createElement('div');
  label.className = 'chat-label';
  label.textContent = role === 'user' ? 'You' : 'Vera';

  const text = document.createElement('div');
  text.className = 'chat-text';
  text.textContent = content;

  messageDiv.appendChild(label);
  messageDiv.appendChild(text);
  chatMessages.appendChild(messageDiv);

  // Scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
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
