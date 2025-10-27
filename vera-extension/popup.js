// Popup script for Vera Assistant

let selectedFieldInfo = null;
let currentResponse = null;
let veraEndpoint = 'http://localhost:8000';

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Load settings
  await loadSettings();

  // Set up event listeners
  setupEventListeners();

  // Check if SE Weekly Update field exists on the page
  await checkSEWeeklyUpdate();

  // Check if a field is already selected
  await checkSelectedField();
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

  // Field selection
  document.getElementById('selectFieldBtn').addEventListener('click', selectField);

  // Prompt
  document.getElementById('promptInput').addEventListener('input', updateSendButton);
  document.getElementById('sendBtn').addEventListener('click', sendToVera);

  // Response actions
  document.getElementById('copyBtn').addEventListener('click', copyResponse);
  document.getElementById('insertBtn').addEventListener('click', insertResponse);

  // Listen for field selection messages
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'fieldSelected') {
      handleFieldSelected(request.fieldInfo);
    } else if (request.action === 'selectionCancelled') {
      showStatus('Field selection cancelled', 'error');
    }
  });
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

// Check if a field is already selected
async function checkSelectedField() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      { action: 'getSelectedField' },
      (response) => {
        if (chrome.runtime.lastError) {
          console.log('Content script not ready yet');
          return;
        }

        if (response && response.hasSelection) {
          handleFieldSelected(response.fieldInfo);
        }
      }
    );
  } catch (error) {
    console.error('Error checking selected field:', error);
  }
}

// Select a field
async function selectField() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      { action: 'selectField' },
      (response) => {
        if (chrome.runtime.lastError) {
          showStatus('Error: Content script not loaded. Please refresh the page.', 'error');
          return;
        }

        if (response && response.success) {
          showStatus('Click on a field in the page...', 'loading');
          // The popup will be closed, so the user will see the field selection overlay
        }
      }
    );
  } catch (error) {
    showStatus('Error selecting field: ' + error.message, 'error');
  }
}

// Handle field selected
function handleFieldSelected(fieldInfo) {
  selectedFieldInfo = fieldInfo;

  // Update UI
  document.getElementById('selectedFieldInfo').classList.remove('hidden');
  document.getElementById('fieldLabel').textContent = fieldInfo.label || 'Unnamed field';

  if (fieldInfo.currentValue) {
    document.getElementById('fieldValue').textContent = fieldInfo.currentValue;
    document.getElementById('fieldValue').classList.remove('hidden');
  } else {
    document.getElementById('fieldValue').classList.add('hidden');
  }

  // Update send button state
  updateSendButton();

  // Hide status
  hideStatus();
}

// Update send button state
function updateSendButton() {
  const promptInput = document.getElementById('promptInput');
  const sendBtn = document.getElementById('sendBtn');

  if (selectedFieldInfo && promptInput.value.trim()) {
    sendBtn.disabled = false;
  } else {
    sendBtn.disabled = true;
  }
}

// Send prompt to Vera
async function sendToVera() {
  const prompt = document.getElementById('promptInput').value.trim();

  if (!prompt || !selectedFieldInfo) {
    return;
  }

  // Build the message
  let message = prompt;

  if (selectedFieldInfo.currentValue) {
    message += `\n\nCurrent field value:\n${selectedFieldInfo.currentValue}`;
  }

  // Show loading status
  showStatus('Sending to Vera...', 'loading');

  try {
    // Call Vera API
    const response = await fetch(`${veraEndpoint}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [
          {
            role: 'user',
            content: message
          }
        ],
        temperature: 0.7,
        stream: false
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const assistantMessage = data.choices[0].message.content;

    // Display response
    currentResponse = assistantMessage;
    document.getElementById('responseText').textContent = assistantMessage;
    document.getElementById('responseSection').classList.remove('hidden');

    // Hide status
    hideStatus();

  } catch (error) {
    showStatus(`Error: ${error.message}. Make sure Vera is running on ${veraEndpoint}`, 'error');
    console.error('Error calling Vera:', error);
  }
}

// Copy response to clipboard
async function copyResponse() {
  if (!currentResponse) return;

  try {
    await navigator.clipboard.writeText(currentResponse);
    showStatus('Copied to clipboard!', 'success');
    setTimeout(hideStatus, 2000);
  } catch (error) {
    showStatus('Failed to copy to clipboard', 'error');
  }
}

// Insert response into field
async function insertResponse() {
  if (!currentResponse || !selectedFieldInfo) return;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(
      tab.id,
      {
        action: 'insertText',
        text: currentResponse
      },
      (response) => {
        if (chrome.runtime.lastError) {
          showStatus('Error: Could not insert text', 'error');
          return;
        }

        if (response && response.success) {
          showStatus('Text inserted successfully!', 'success');
          setTimeout(() => {
            window.close();
          }, 1000);
        } else {
          showStatus('Failed to insert text', 'error');
        }
      }
    );
  } catch (error) {
    showStatus('Error inserting text: ' + error.message, 'error');
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

        // Build the prompt
        let prompt = 'Please complete my SE weekly update.';
        if (currentValue) {
          prompt += `\n\nCurrent content:\n${currentValue}`;
        }

        showStatus('Sending to Vera...', 'loading');

        try {
          // Call Vera API
          const veraResponse = await fetch(`${veraEndpoint}/v1/chat/completions`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              messages: [
                {
                  role: 'user',
                  content: prompt
                }
              ],
              temperature: 0.7,
              stream: false
            })
          });

          if (!veraResponse.ok) {
            throw new Error(`HTTP error! status: ${veraResponse.status}`);
          }

          const data = await veraResponse.json();
          const completedUpdate = data.choices[0].message.content;

          showStatus('Inserting into field...', 'loading');

          // Insert into the field
          chrome.tabs.sendMessage(
            tab.id,
            {
              action: 'fillSEWeeklyUpdate',
              text: completedUpdate
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
          showStatus(`Error: ${error.message}. Make sure Vera is running on ${veraEndpoint}`, 'error');
          console.error('Error calling Vera:', error);
        }
      }
    );
  } catch (error) {
    showStatus('Error: ' + error.message, 'error');
  }
}
