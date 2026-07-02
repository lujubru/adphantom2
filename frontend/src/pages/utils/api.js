import axios from 'axios';

// Ensure HTTPS in production
let API_URL = process.env.REACT_APP_BACKEND_URL || '';
if (API_URL && API_URL.startsWith('http://') && !API_URL.includes('localhost')) {
  API_URL = API_URL.replace('http://', 'https://');
}
const API = `${API_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;