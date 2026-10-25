// ReceiptIQ Core Frontend Application Script

function getAuthToken() {
  const token = sessionStorage.getItem('receiptiq_token') || localStorage.getItem('receiptiq_token');
  if (token) {
    sessionStorage.setItem('receiptiq_token', token);
    localStorage.setItem('receiptiq_token', token);
  }
  return token;
}

function setAuthToken(token) {
  if (token) {
    sessionStorage.setItem('receiptiq_token', token);
    localStorage.setItem('receiptiq_token', token);
  }
}

function clearAuthToken() {
  sessionStorage.removeItem('receiptiq_token');
  localStorage.removeItem('receiptiq_token');
}

// Sync Chart.js default colors with current theme
function updateChartThemeDefaults(theme) {
  if (typeof Chart !== 'undefined') {
    const isDark = theme === 'dark';
    Chart.defaults.color = isDark ? '#cbd5e1' : '#334155';
    Chart.defaults.borderColor = isDark ? '#3b3b58' : '#e2e8f0';
    if (Chart.defaults.plugins && Chart.defaults.plugins.legend) {
      Chart.defaults.plugins.legend.labels.color = isDark ? '#f8fafc' : '#0f172a';
    }
  }
}

function updateThemeButtonLabel(theme) {
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.innerHTML = theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
  }
}

(function () {
  // Capture token from URL query string if present
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  if (tokenFromUrl) {
    setAuthToken(tokenFromUrl);
    // Remove token from visible URL
    urlParams.delete('token');
    const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
    window.history.replaceState({}, document.title, newUrl);
  } else {
    getAuthToken();
  }

  // Theme Initialization
  const currentTheme = localStorage.getItem('receiptiq_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  updateChartThemeDefaults(currentTheme);
})();

document.addEventListener('DOMContentLoaded', () => {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  updateThemeButtonLabel(currentTheme);
});

// Helper function for authenticated API requests
async function apiRequest(url, options = {}) {
  const token = getAuthToken();
  if (!token && !url.includes('/api/auth/login')) {
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    return null;
  }

  const headers = options.headers || {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  options.headers = headers;

  try {
    const response = await fetch(url, options);
    if (response.status === 401 && !url.includes('/api/auth/login')) {
      clearAuthToken();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return null;
    }
    return response;
  } catch (err) {
    console.error('API Request Error:', err);
    throw err;
  }
}

// User Info Loader
async function loadCurrentUser() {
  const res = await apiRequest('/api/me');
  if (res && res.ok) {
    const data = await res.json();
    const user = data.user;
    const userLabel = document.getElementById('nav-user-label');
    if (userLabel) {
      userLabel.textContent = `${user.username} (${user.role})`;
    }
    if (user.role === 'admin') {
      const adminNav = document.getElementById('nav-admin-link');
      if (adminNav) adminNav.style.display = 'block';
    }
    return user;
  }
  return null;
}

// Logout Action
async function handleLogout() {
  try {
    await apiRequest('/api/auth/logout', { method: 'POST' });
  } catch (e) {}
  clearAuthToken();
  window.location.href = '/login';
}

// Theme Toggle Action
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', current);
  localStorage.setItem('receiptiq_theme', current);
  updateThemeButtonLabel(current);
  updateChartThemeDefaults(current);
  window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: current } }));
}
