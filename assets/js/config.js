export const CONFIG = {
  API_URL: '/api'
};

export const API_URL = CONFIG.API_URL;

export function getToken() {
  return localStorage.getItem('nexus_token');
}

export function setSession(token, usuario) {
  localStorage.setItem('nexus_token', token);
  localStorage.setItem('nexus_user', JSON.stringify(usuario));
}

export function clearSession() {
  localStorage.removeItem('nexus_token');
  localStorage.removeItem('nexus_user');
}

export async function apiRequest(path, options = {}) {
  const token = getToken();
  const isForm = options.body instanceof FormData;
  const headers = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

  const response = await fetch(`${CONFIG.API_URL}${path}`, {
    ...options,
    headers
  });

  if (response.status === 401) {
    clearSession();
    throw new Error('Sessão expirada. Faça login novamente para continuar.');
  }

  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((d) => d.msg).join(', ')
      : data?.detail || data?.message || 'Não foi possível processar a requisição no momento.';
    throw new Error(detail);
  }

  return data;
}
