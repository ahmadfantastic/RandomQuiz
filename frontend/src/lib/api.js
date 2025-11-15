import axios from 'axios';

const api = axios.create({
  withCredentials: true,
});

function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
  return null;
}

const csrftoken = getCookie('csrftoken');
if (csrftoken) {
  api.defaults.headers.common['X-CSRFToken'] = csrftoken;
}

export default api;
