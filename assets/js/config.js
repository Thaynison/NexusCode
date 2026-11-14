export const CONFIG = {
  API_URL: '/api'
};

export const API_URL = CONFIG.API_URL;

export function getTenantSlug() {
  try {
    const params = new URLSearchParams(window.location.search);
    const qTenant = (params.get('tenant') || '').trim().toLowerCase();
    if (qTenant) {
      sessionStorage.setItem('nexus_tenant_slug', qTenant);
      return qTenant;
    }

    const host = (window.location.hostname || '').toLowerCase();
    if (host.endsWith('.nexuscodebrasil.com.br')) {
      const sub = host.slice(0, -'.nexuscodebrasil.com.br'.length);
      if (sub && !['www', 'app', 'api'].includes(sub)) {
        return sub;
      }
    } else if (host.endsWith('.localhost')) {
      const sub = host.slice(0, -'.localhost'.length);
      if (sub && !['www', 'app', 'api'].includes(sub)) {
        return sub;
      }
    } else if (
      host &&
      host !== 'localhost' &&
      host !== '127.0.0.1' &&
      host !== 'nexuscodebrasil.com.br' &&
      host !== 'www.nexuscodebrasil.com.br' &&
      !host.endsWith('.vercel.app')
    ) {
      return host;
    }

    return sessionStorage.getItem('nexus_tenant_slug') || '';
  } catch {
    return '';
  }
}

export function getToken() {
  return localStorage.getItem('nexus_token');
}

export function setSession(token, usuario, tenantSlug = '') {
  localStorage.setItem('nexus_token', token);
  localStorage.setItem('nexus_user', JSON.stringify(usuario));
  if (tenantSlug) {
    sessionStorage.setItem('nexus_tenant_slug', tenantSlug);
  }
}

export function clearSession() {
  localStorage.removeItem('nexus_token');
  localStorage.removeItem('nexus_user');
  sessionStorage.removeItem('nexus_tenant_slug');
}

export async function apiRequest(path, options = {}) {
  const token = getToken();
  const tenantSlug = getTenantSlug();
  const isForm = options.body instanceof FormData;
  const headers = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(tenantSlug ? { 'X-Tenant-Slug': tenantSlug } : {}),
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

export function applyWhiteLabelBranding(orgData) {
  if (!orgData) return;
  const brand = orgData.branding || {};
  const root = document.documentElement;

  if (brand.cor_primaria) {
    root.style.setProperty('--primary', brand.cor_primaria);
  }
  if (brand.cor_secundaria) {
    root.style.setProperty('--primary-hover', brand.cor_secundaria);
  }
  if (brand.cor_sidebar) {
    root.style.setProperty('--sidebar-bg', brand.cor_sidebar);
  }

  const platName = (brand.nome_plataforma || orgData.nome || 'NEXUS CODE').trim();
  const platSub = (brand.subtitulo_plataforma || '').trim();
  document.title = `${platName}${platSub ? ' • ' + platSub : ''} | Gestão Empresarial`;

  if (brand.favicon_url) {
    const iconLink = document.querySelector('link[rel="icon"]');
    if (iconLink) iconLink.href = brand.favicon_url;
  }

  const sideBrand = document.querySelector('.side .brand');
  if (sideBrand) {
    const safeName = platName.replace(/[<>&"']/g, '');
    if (brand.logo_url) {
      sideBrand.innerHTML = `
        <img src="${brand.logo_url}" alt="${safeName}" style="max-height:32px; max-width:150px; object-fit:contain; border-radius:6px;">
        <span style="letter-spacing:0.02em; font-weight:800; font-size:15px;">${safeName}</span>
      `;
    } else if (!orgData.is_master) {
      const abbr = safeName.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() || '').join('') || 'ERP';
      sideBrand.innerHTML = `
        <div style="width:30px; height:30px; border-radius:8px; background:${brand.cor_primaria || '#0096B4'}; color:#ffffff; font-weight:900; font-size:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">${abbr}</div>
        <span style="letter-spacing:0.02em; font-weight:800;">${safeName}</span>
      `;
    }
  }

  if (brand.tema_padrao === 'dark' && !localStorage.getItem('nc_theme')) {
    const shell = document.getElementById('app-shell');
    shell?.classList.add('app-dark');
    document.body.classList.add('dark');
  }
}
