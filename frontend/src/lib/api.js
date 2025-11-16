import axios from 'axios';
import { clearAuthFlag } from './auth';

const api = axios.create({
  withCredentials: true,
});

const SAFE_METHODS = ['get', 'head', 'options'];
let csrfToken = null;
let csrfPromise = null;

async function fetchCsrfToken() {
  if (csrfToken) return csrfToken;
  if (!csrfPromise) {
    csrfPromise = fetch('/api/auth/csrf/', {
      credentials: 'include',
    })
      .then((res) => res.json())
      .then((data) => {
        csrfToken = data?.csrfToken ?? null;
        return csrfToken;
      })
      .catch(() => null)
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

const shouldRefreshCsrf = (url = '') => {
  if (typeof url !== 'string') return false;
  return url.includes('/api/auth/login/') || url.includes('/api/auth/logout/');
};

const invalidateCsrfToken = () => {
  csrfToken = null;
  csrfPromise = null;
};

api.interceptors.request.use(async (config) => {
  const method = config.method ? config.method.toLowerCase() : 'get';
  if (!SAFE_METHODS.includes(method)) {
    const token = await fetchCsrfToken();
    if (token) {
      config.headers = {
        ...config.headers,
        'X-CSRFToken': token,
      };
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    const url = response.config?.url;
    if (shouldRefreshCsrf(url)) {
      invalidateCsrfToken();
      fetchCsrfToken();
    }
    return response;
  },
  (error) => {
    const url = error.config?.url;
    if (shouldRefreshCsrf(url)) {
      invalidateCsrfToken();
    }
    if (
      error.response?.status === 403 &&
      typeof error.response?.data?.detail === 'string' &&
      error.response.data.detail.toLowerCase().includes('credentials')
    ) {
      clearAuthFlag();
    }
    return Promise.reject(error);
  }
);

export default api;
