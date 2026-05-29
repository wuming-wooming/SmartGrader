import axios from 'axios';

export const baseURL = '/api';

const api = axios.create({
  baseURL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use((response) => {
  return response.data;
}, (error) => {
  if (error.response && error.response.status === 401) {
    // 触发一个自定义事件或者重新加载页面来让用户重新登录
    localStorage.removeItem('token');
    window.dispatchEvent(new Event('auth-expired'));
  }
  return Promise.reject(error);
});

export default api;
