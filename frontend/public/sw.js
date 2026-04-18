/* AdPhantom CRM — Service Worker: Web Push + PWA installable
 * Runs in background even when Chrome tabs are closed.
 * Receives push from the backend and displays native OS notifications.
 * Also enables "Install as App" prompt on Android/desktop.
 */

const CACHE_NAME = 'adphantom-v2';

self.addEventListener('install', (event) => {
  // Activate immediately, don't wait for previous SW to close
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

// Required for "installable PWA" — must handle fetch events even as pass-through
self.addEventListener('fetch', (event) => {
  // Network-first, no aggressive caching (app must always be fresh).
  // This minimal handler is enough for the browser to treat us as a valid PWA.
  return;
});

self.addEventListener('push', (event) => {
  let payload = { title: 'CRM Leads', body: 'Nuevo mensaje', data: {} };
  try {
    if (event.data) payload = event.data.json();
  } catch (e) {
    try { payload = { title: 'CRM Leads', body: event.data.text(), data: {} }; }
    catch { /* silent */ }
  }

  const title = payload.title || 'CRM Leads';
  const options = {
    body: payload.body || 'Nuevo mensaje',
    icon: '/logo.png',
    badge: '/logo.png',
    tag: payload.data?.lead_id ? `lead-${payload.data.lead_id}` : 'crm-generic',
    renotify: true,
    requireInteraction: false,
    data: payload.data || {},
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const targetUrl = data.url || '/leads';
  const leadId = data.lead_id || '';

  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    });
    // Try to find an existing CRM tab and focus it
    for (const client of allClients) {
      const url = new URL(client.url);
      if (url.pathname.startsWith('/leads') || url.pathname.startsWith('/crm')) {
        await client.focus();
        // Post message so the page opens the specific lead
        if (leadId) client.postMessage({ type: 'OPEN_LEAD', leadId });
        return;
      }
    }
    // No existing tab — open a new one
    const openUrl = leadId ? `${targetUrl}?openLead=${encodeURIComponent(leadId)}` : targetUrl;
    await self.clients.openWindow(openUrl);
  })());
});
