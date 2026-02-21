// DarkGPT Background Service Worker

// Context menu setup
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'darkgpt-ask',
    title: 'Ask DarkGPT about "%s"',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'darkgpt-explain',
    title: 'Explain with DarkGPT',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'darkgpt-summarize',
    title: 'Summarize this page',
    contexts: ['page']
  });

  chrome.contextMenus.create({
    id: 'darkgpt-analyze-link',
    title: 'Analyze this link',
    contexts: ['link']
  });

  chrome.contextMenus.create({
    id: 'darkgpt-analyze-image',
    title: 'Describe this image',
    contexts: ['image']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const stored = await chrome.storage.local.get(['darkgpt_config']);
  const config = stored.darkgpt_config;

  if (!config || !config.apiKey) {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'DarkGPT',
      message: 'Please configure your API key first.'
    });
    return;
  }

  let query = '';

  switch (info.menuItemId) {
    case 'darkgpt-ask':
      query = `Regarding the following text, answer any questions or provide analysis:\n\n"${info.selectionText}"`;
      break;
    case 'darkgpt-explain':
      query = `Explain the following in detail:\n\n"${info.selectionText}"`;
      break;
    case 'darkgpt-summarize':
      // Extract page content first
      try {
        const [result] = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const body = document.body.cloneNode(true);
            body.querySelectorAll('script, style, nav, footer, iframe, noscript').forEach(el => el.remove());
            return {
              title: document.title,
              text: body.innerText.replace(/\n{3,}/g, '\n\n').trim().substring(0, 12000)
            };
          }
        });
        if (result && result.result) {
          query = `Summarize this page concisely:\n\nTitle: ${result.result.title}\n\n${result.result.text}`;
        }
      } catch (e) {
        query = `Summarize the page at: ${info.pageUrl}`;
      }
      break;
    case 'darkgpt-analyze-link':
      query = `What can you tell me about this link: ${info.linkUrl}`;
      break;
    case 'darkgpt-analyze-image':
      query = `Describe what this image might contain based on the URL: ${info.srcUrl}`;
      break;
  }

  if (query) {
    // Store the query for the popup/sidepanel to pick up
    await chrome.storage.local.set({
      darkgpt_pending_query: query,
      darkgpt_pending_timestamp: Date.now()
    });

    // Open side panel if supported
    try {
      await chrome.sidePanel.open({ tabId: tab.id });
    } catch {
      // Fall back to notification
      chrome.action.openPopup().catch(() => {
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'DarkGPT',
          message: 'Query queued. Click the extension icon to see the response.'
        });
      });
    }
  }
});

// Handle messages from popup/content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'openSidePanel') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.sidePanel.open({ tabId: tabs[0].id }).catch(() => {
          // Side panel may not be available
        });
      }
    });
    return true;
  }

  if (message.action === 'getPendingQuery') {
    chrome.storage.local.get(['darkgpt_pending_query', 'darkgpt_pending_timestamp'], (data) => {
      if (data.darkgpt_pending_query && (Date.now() - data.darkgpt_pending_timestamp) < 30000) {
        sendResponse({ query: data.darkgpt_pending_query });
        chrome.storage.local.remove(['darkgpt_pending_query', 'darkgpt_pending_timestamp']);
      } else {
        sendResponse({ query: null });
      }
    });
    return true;
  }

  if (message.action === 'extractPageContent') {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (!tabs[0]) {
        sendResponse({ error: 'No active tab' });
        return;
      }
      try {
        const [result] = await chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          func: () => {
            const body = document.body.cloneNode(true);
            body.querySelectorAll('script, style, nav, footer, iframe, noscript').forEach(el => el.remove());
            return {
              title: document.title,
              url: window.location.href,
              text: body.innerText.replace(/\n{3,}/g, '\n\n').trim().substring(0, 15000)
            };
          }
        });
        sendResponse({ content: result.result });
      } catch (err) {
        sendResponse({ error: err.message });
      }
    });
    return true;
  }
});

// Keyboard shortcut handler
chrome.commands?.onCommand?.addListener((command) => {
  if (command === 'toggle-sidepanel') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.sidePanel.open({ tabId: tabs[0].id }).catch(() => {});
      }
    });
  }
});
