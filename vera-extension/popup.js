// Popup script for Vera Assistant

let veraEndpoint = 'http://localhost:8000';

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

        // Build the prompt
        let prompt = 'Please complete my SE weekly update.';

        if (additionalContext) {
          prompt += `\n\nAdditional context:\n${additionalContext}`;
        }

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
