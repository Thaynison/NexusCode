import { apiRequest, clearSession, getToken } from './config.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const shell = $('#app-shell');
const side = $('#app-side');
const backdrop = $('#sidebar-backdrop');
const view = $('#app-view');
const recordDialog = $('#record-dialog');
const recordForm = $('#record-form');

let page = 'dashboard';
let user = null;
let editingId = null;
let searchTerm = '';
let statusFilter = 'todos';
let cache = { kpi: null, clientes: [], usuarios: [], projetos: [], orcamentos: [], tarefas: [], loadedAt: 0 };
const CACHE_TTL_MS = 30000;

function invalidateCache() {
  cache.loadedAt = 0;
}

async function loadBootstrap(force = false) {
  const now = Date.now();
  if (!force && cache.loadedAt && (now - cache.loadedAt) < CACHE_TTL_MS) {
    return cache;
  }
  const data = await apiRequest('/bootstrap');
  cache = {
    kpi: data.kpi,
    clientes: data.clientes || [],
    usuarios: data.usuarios || [],
    projetos: data.projetos || [],
    orcamentos: data.orcamentos || [],
    tarefas: data.tarefas || [],
    loadedAt: Date.now()
  };
  updateQuotesBadge();
  return cache;
}

const esc = (v) =>
  String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

const initials = (name) =>
  String(name || 'NC')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('');

const formatMoney = (v) =>
  Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

const formatDate = (v) => {
  if (!v) return '-';
  const d = new Date(v.length === 10 ? v + 'T00:00:00' : v);
  return isNaN(d) ? v : d.toLocaleDateString('pt-BR');
};

const formatDateTime = (v) => {
  if (!v) return '-';
  const d = new Date(v);
  return isNaN(d) ? v : d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const ICONS = {
  plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
  users: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
  inbox: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
  folder: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path></svg>',
  check: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>',
  dollar: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>',
  arrowRight: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>',
  reply: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>',
  sun: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>',
  moon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path></svg>'
};

// ==================== CONTROLE DO MENU LATERAL ====================
function closeMobileDrawer() {
  side?.classList.remove('open');
  backdrop?.classList.remove('open');
}

function toggleSidebar() {
  if (window.innerWidth <= 900) {
    const isOpen = side.classList.toggle('open');
    backdrop?.classList.toggle('open', isOpen);
  } else {
    const isCollapsed = shell.classList.toggle('sidebar-collapsed');
    localStorage.setItem('nc_sidebar_collapsed', isCollapsed ? '1' : '0');
  }
}

$('#app-menu')?.addEventListener('click', toggleSidebar);
backdrop?.addEventListener('click', closeMobileDrawer);

if (localStorage.getItem('nc_sidebar_collapsed') === '1' && window.innerWidth > 900) {
  shell?.classList.add('sidebar-collapsed');
}

// ==================== TEMA CLARO / ESCURO ====================
function applyTheme(dark) {
  shell?.classList.toggle('app-dark', dark);
  document.body.classList.toggle('dark', dark);
  const iconEl = $('#theme-icon');
  if (iconEl) {
    iconEl.outerHTML = dark
      ? ICONS.sun.replace('<svg ', '<svg id="theme-icon" ')
      : ICONS.moon.replace('<svg ', '<svg id="theme-icon" ');
  }
}

if (localStorage.getItem('nc_theme') === 'dark') {
  applyTheme(true);
}

$('#app-theme')?.addEventListener('click', () => {
  const nextDark = !shell.classList.contains('app-dark');
  localStorage.setItem('nc_theme', nextDark ? 'dark' : 'light');
  applyTheme(nextDark);
});

// ==================== CARREGAMENTO & FILTROS ====================
const internalRoles = new Set(['admin', 'colaborador']);

async function preloadRefs(force = false) {
  if (!internalRoles.has(user?.perfil)) return;
  try {
    await loadBootstrap(force);
  } catch (_) {}
}

function updateQuotesBadge() {
  const badge = $('#quotes-nav-badge');
  if (!badge) return;
  const pendentes = (cache.orcamentos || []).filter((o) => o.status === 'novo').length;
  badge.textContent = pendentes;
  badge.style.display = pendentes > 0 ? 'inline-block' : 'none';
}

function matchSearch(texts) {
  if (!searchTerm) return true;
  const q = searchTerm.toLowerCase();
  return texts.some((t) => String(t ?? '').toLowerCase().includes(q));
}

// ==================== TELAS DO SISTEMA ====================
async function renderDashboard() {
  const { kpi, projetos, orcamentos } = await loadBootstrap();

  return `
    <div class="toolbar">
      <div>
        <h1>Dashboard Executivo</h1>
        <span class="muted">Visão consolidada de atendimento, projetos e faturamento</span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button class="btn secondary" onclick="window.nexusGo('quotes')">${ICONS.inbox}<span>Solicitações (${kpi.solicitacoes_novas})</span></button>
        <button class="btn" onclick="window.nexusGo('projects', true)">${ICONS.plus}<span>Novo Projeto</span></button>
      </div>
    </div>

    <div class="grid">
      <div class="card metric" style="cursor:pointer;" onclick="window.nexusGo('quotes')">
        <div class="metric-head">
          <span class="title">Solicitações Pendentes</span>
          <span class="metric-icon">${ICONS.inbox}</span>
        </div>
        <strong>${kpi.solicitacoes_novas}</strong>
        <span class="pill-info">${orcamentos.length} solicitações registradas</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Clientes &amp; Leads</span>
          <span class="metric-icon">${ICONS.users}</span>
        </div>
        <strong>${kpi.total_clientes}</strong>
        <span class="pill-info">${kpi.leads_abertos} oportunidades em andamento</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Projetos Ativos</span>
          <span class="metric-icon">${ICONS.folder}</span>
        </div>
        <strong>${kpi.projetos_ativos}</strong>
        <span class="pill-info">Em execução e homologação</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Receita Paga</span>
          <span class="metric-icon">${ICONS.dollar}</span>
        </div>
        <strong>${formatMoney(kpi.receita_paga)}</strong>
        <span class="pill-info">A receber: ${formatMoney(kpi.receita_pendente)}</span>
      </div>
    </div>

    <div class="dashboard-panels">
      <div class="card">
        <div class="toolbar" style="margin-bottom:12px;">
          <h3 style="margin:0; font-size:16px;">Solicitações Recentes</h3>
          <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusGo('quotes')">Ver todas</button>
        </div>
        ${orcamentos.slice(0, 5).map((o) => `
          <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px; cursor:pointer;" onclick="window.nexusReplyQuote(${o.id})">
            <div style="min-width:0;">
              <b>${esc(o.nome)}</b> <span class="muted" style="font-size:12px;">• ${esc(o.tipo_projeto || 'Orçamento')}</span>
              <div class="muted" style="font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(o.mensagem)}</div>
            </div>
            <span class="badge ${esc(o.status)}">${esc(o.status).replace('_', ' ')}</span>
          </div>
        `).join('') || '<p class="muted">Nenhuma solicitação pendente no momento.</p>'}
      </div>

      <div class="card">
        <div class="toolbar" style="margin-bottom:12px;">
          <h3 style="margin:0; font-size:16px;">Projetos em Andamento</h3>
          <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusGo('projects')">Ver todos</button>
        </div>
        ${projetos.slice(0, 5).map((p) => `
          <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px; cursor:default;">
            <div>
              <b>${esc(p.titulo)}</b>
              <div class="muted" style="font-size:12px;">Progresso: ${p.progresso}% • ${formatMoney(p.valor_total)}</div>
            </div>
            <span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span>
          </div>
        `).join('') || '<p class="muted">Nenhum projeto em andamento.</p>'}
      </div>
    </div>`;
}

async function renderQuotes() {
  const allItems = await apiRequest('/orcamentos');
  cache.orcamentos = allItems;
  updateQuotesBadge();

  const items = allItems.filter((o) => {
    const okStatus = statusFilter === 'todos' || o.status === statusFilter;
    const okSearch = matchSearch([o.nome, o.empresa, o.email, o.telefone, o.tipo_projeto, o.mensagem, o.resposta]);
    return okStatus && okSearch;
  });

  const rows = items.map((o) => `
    <tr>
      <td>
        <div class="row-entity">
          <div class="row-avatar">${initials(o.nome)}</div>
          <div>
            <b>${esc(o.nome)}</b>
            <div class="muted" style="font-size:12px;">${esc(o.empresa || 'Pessoa Física')}</div>
          </div>
        </div>
      </td>
      <td>
        <div style="color:var(--primary); font-weight:500;">${esc(o.email)}</div>
        <div class="muted" style="font-size:12px;">${esc(o.telefone || '-')}</div>
      </td>
      <td><span class="badge">${esc(o.tipo_projeto || 'Geral')}</span></td>
      <td style="min-width:220px; max-width:360px;">
        <div style="font-size:13px; line-height:1.5; color:var(--text); white-space:normal;">
          ${esc(o.mensagem).substring(0, 150)}${o.mensagem.length > 150 ? '...' : ''}
        </div>
        ${o.resposta ? `<div style="font-size:11.5px; color:var(--ok); margin-top:4px; font-weight:600;">Respondido por ${esc(o.respondido_por || 'Equipe')}</div>` : ''}
      </td>
      <td><span class="badge ${esc(o.status)}">${esc(o.status).replace('_', ' ')}</span></td>
      <td style="white-space:nowrap; font-size:12.5px;">${formatDateTime(o.criado_em)}</td>
      <td style="white-space:nowrap;">
        <button class="btn" style="padding:6px 12px; font-size:12px;" data-reply='${JSON.stringify(o).replace(/'/g, "&apos;")}'>${ICONS.reply}<span>${o.resposta ? 'Visualizar Resposta' : 'Responder'}</span></button>
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/orcamentos/${o.id}">Excluir</button>
      </td>
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div>
        <h1>Solicitações &amp; Orçamentos</h1>
        <span class="muted">Gerenciamento e atendimento das solicitações recebidas pelo portal institucional</span>
      </div>
    </div>
    <div class="filter-bar">
      ${[
        ['todos', 'Todos', allItems.length],
        ['novo', 'Novos', allItems.filter((x) => x.status === 'novo').length],
        ['em_atendimento', 'Em Atendimento', allItems.filter((x) => x.status === 'em_atendimento').length],
        ['respondido', 'Respondidos', allItems.filter((x) => x.status === 'respondido').length],
        ['convertido', 'Convertidos', allItems.filter((x) => x.status === 'convertido').length]
      ].map(([key, label, count]) => `
        <button class="filter-pill ${statusFilter === key ? 'active' : ''}" data-filter="${key}">
          ${label} <span class="filter-count">${count}</span>
        </button>
      `).join('')}
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Solicitante</th><th>Contato</th><th>Tipo de Projeto</th><th>Mensagem</th><th>Status</th><th>Recebido em</th><th>Ações</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center; padding:32px;" class="muted">Nenhuma solicitação encontrada para os filtros selecionados.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderProjects() {
  await preloadRefs();
  const allItems = await apiRequest('/projetos');
  const clientMap = Object.fromEntries(cache.clientes.map((c) => [c.id, c.nome_empresa]));
  const userMap = Object.fromEntries(cache.usuarios.map((u) => [u.id, u.nome]));
  const isStaff = internalRoles.has(user.perfil);

  const items = allItems.filter((p) => {
    const okStatus = statusFilter === 'todos' || p.status === statusFilter;
    const okSearch = matchSearch([p.titulo, p.descricao, clientMap[p.cliente_id], p.status]);
    return okStatus && okSearch;
  });

  const rows = items.map((p) => `
    <tr>
      <td>
        <div class="row-entity">
          <div class="row-avatar">${initials(p.titulo)}</div>
          <div>
            <b>${esc(p.titulo)}</b>
            <div class="muted" style="font-size:12px;">${esc(p.descricao || 'Sem descrição adicional')}</div>
          </div>
        </div>
      </td>
      <td>${esc(clientMap[p.cliente_id] || 'Conta #' + p.cliente_id)}</td>
      <td>${esc(userMap[p.responsavel_id] || '-')}</td>
      <td><span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span></td>
      <td style="min-width:130px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <div style="flex:1; height:6px; background:var(--surface2); border-radius:4px; overflow:hidden; border:1px solid var(--border);">
            <div style="width:${p.progresso}%; height:100%; background:var(--primary);"></div>
          </div>
          <span style="font-size:12px; font-weight:700;">${p.progresso}%</span>
        </div>
      </td>
      <td style="font-weight:700;">${formatMoney(p.valor_total)}</td>
      <td>${formatDate(p.data_entrega)}</td>
      ${isStaff ? `<td style="white-space:nowrap;">
        <button class="btn secondary" style="padding:6px 10px; font-size:12px;" data-edit='${JSON.stringify(p).replace(/'/g, "&apos;")}'>Editar</button>
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/projetos/${p.id}">Excluir</button>
      </td>` : ''}
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Projetos</h1><span class="muted">Gerencie entregas, responsáveis, progresso e valores contratados</span></div>
      ${isStaff ? `<button class="btn" data-new>${ICONS.plus}<span>Novo Projeto</span></button>` : ''}
    </div>
    <div class="filter-bar">
      ${[
        ['todos', 'Todos', allItems.length],
        ['planejamento', 'Planejamento', allItems.filter((x) => x.status === 'planejamento').length],
        ['em_andamento', 'Em Andamento', allItems.filter((x) => x.status === 'em_andamento').length],
        ['homologacao', 'Homologação', allItems.filter((x) => x.status === 'homologacao').length],
        ['concluido', 'Concluídos', allItems.filter((x) => x.status === 'concluido').length]
      ].map(([key, label, count]) => `
        <button class="filter-pill ${statusFilter === key ? 'active' : ''}" data-filter="${key}">
          ${label} <span class="filter-count">${count}</span>
        </button>
      `).join('')}
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Projeto</th><th>Cliente</th><th>Responsável</th><th>Status</th><th>Progresso</th><th>Valor</th><th>Entrega</th>${isStaff ? '<th>Ações</th>' : ''}</tr></thead>
        <tbody>${rows || '<tr><td colspan="8" style="text-align:center; padding:32px;" class="muted">Nenhum projeto encontrado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderClients(onlyLeads = false) {
  const allItems = await apiRequest('/clientes' + (onlyLeads ? '?status_funil=lead' : ''));
  const items = allItems.filter((c) => {
    const okStatus = statusFilter === 'todos' || c.status_funil === statusFilter;
    const okSearch = matchSearch([c.nome_empresa, c.contato_nome, c.email, c.telefone, c.origem]);
    return okStatus && okSearch;
  });

  const rows = items.map((c) => `
    <tr>
      <td>
        <div class="row-entity">
          <div class="row-avatar">${initials(c.nome_empresa)}</div>
          <b>${esc(c.nome_empresa)}</b>
        </div>
      </td>
      <td>${esc(c.contato_nome)}</td>
      <td style="color:var(--primary); font-weight:500;">${esc(c.email)}</td>
      <td>${esc(c.telefone || '-')}</td>
      <td><span class="badge ${esc(c.status_funil)}">${esc(c.status_funil)}</span></td>
      <td>${esc(c.origem || '-')}</td>
      <td style="white-space:nowrap;">
        <button class="btn secondary" style="padding:6px 10px; font-size:12px;" data-edit='${JSON.stringify(c).replace(/'/g, "&apos;")}'>Editar</button>
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/clientes/${c.id}">Excluir</button>
      </td>
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>${onlyLeads ? 'Leads' : 'Clientes & Empresas'}</h1><span class="muted">Gestão de carteira de clientes, contas e relacionamento comercial</span></div>
      <button class="btn" data-new>${ICONS.plus}<span>Novo ${onlyLeads ? 'Lead' : 'Cliente'}</span></button>
    </div>
    ${!onlyLeads ? `
    <div class="filter-bar">
      ${[
        ['todos', 'Todos', allItems.length],
        ['lead', 'Leads', allItems.filter((x) => x.status_funil === 'lead').length],
        ['proposta', 'Proposta', allItems.filter((x) => x.status_funil === 'proposta').length],
        ['negociacao', 'Negociação', allItems.filter((x) => x.status_funil === 'negociacao').length],
        ['ativo', 'Ativos', allItems.filter((x) => x.status_funil === 'ativo').length]
      ].map(([key, label, count]) => `
        <button class="filter-pill ${statusFilter === key ? 'active' : ''}" data-filter="${key}">
          ${label} <span class="filter-count">${count}</span>
        </button>
      `).join('')}
    </div>` : ''}
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Empresa</th><th>Contato Principal</th><th>E-mail</th><th>Telefone</th><th>Estágio</th><th>Origem</th><th>Ações</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center; padding:32px;" class="muted">Nenhum registro encontrado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderUsers() {
  const allItems = await apiRequest('/usuarios');
  const items = allItems.filter((u) => matchSearch([u.nome, u.email, u.perfil]));

  const rows = items.map((u) => `
    <tr>
      <td>
        <div class="row-entity">
          <div class="row-avatar">${initials(u.nome)}</div>
          <b>${esc(u.nome)}</b>
        </div>
      </td>
      <td>${esc(u.email)}</td>
      <td><span class="badge">${esc(u.perfil)}</span></td>
      <td><span class="badge ${u.ativo ? 'ativo' : 'inativo'}">${u.ativo ? 'Ativo' : 'Inativo'}</span></td>
      <td>${formatDate(u.criado_em)}</td>
      <td style="white-space:nowrap;">
        <button class="btn secondary" style="padding:6px 10px; font-size:12px;" data-edit='${JSON.stringify(u).replace(/'/g, "&apos;")}'>Editar</button>
        ${u.id !== user.id ? `<button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/usuarios/${u.id}">Excluir</button>` : ''}
      </td>
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Usuários e Perfis</h1><span class="muted">Controle de acesso para administradores, equipe e clientes</span></div>
      <button class="btn" data-new>${ICONS.plus}<span>Novo Usuário</span></button>
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Usuário</th><th>E-mail</th><th>Perfil</th><th>Status</th><th>Criado em</th><th>Ações</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function renderTasks() {
  await preloadRefs();
  const allItems = await apiRequest('/tarefas');
  const projMap = Object.fromEntries(cache.projetos.map((p) => [p.id, p.titulo]));
  const userMap = Object.fromEntries(cache.usuarios.map((u) => [u.id, u.nome]));
  const items = allItems.filter((t) => matchSearch([t.titulo, projMap[t.projeto_id], t.status]));

  const rows = items.map((t) => `
    <tr>
      <td><b>${esc(t.titulo)}</b></td>
      <td>${esc(projMap[t.projeto_id] || 'Projeto #' + t.projeto_id)}</td>
      <td>${esc(userMap[t.responsavel_id] || '-')}</td>
      <td><span class="badge ${esc(t.status)}">${esc(t.status)}</span></td>
      <td>${formatDate(t.prazo)}</td>
      <td style="white-space:nowrap;">
        <button class="btn secondary" style="padding:6px 10px; font-size:12px;" data-edit='${JSON.stringify(t).replace(/'/g, "&apos;")}'>Editar</button>
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/tarefas/${t.id}">Excluir</button>
      </td>
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Tarefas &amp; Atividades</h1><span class="muted">Acompanhamento operacional das entregas por projeto</span></div>
      <button class="btn" data-new>${ICONS.plus}<span>Nova Tarefa</span></button>
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Tarefa</th><th>Projeto</th><th>Responsável</th><th>Status</th><th>Prazo</th><th>Ações</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" style="text-align:center; padding:32px;" class="muted">Nenhuma tarefa cadastrada.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderInvoices() {
  await preloadRefs();
  const allItems = await apiRequest('/faturas');
  const clientMap = Object.fromEntries(cache.clientes.map((c) => [c.id, c.nome_empresa]));
  const isStaff = internalRoles.has(user.perfil);
  const items = allItems.filter((f) => matchSearch([f.descricao, clientMap[f.cliente_id], f.status]));

  const rows = items.map((f) => `
    <tr>
      <td><b>${esc(f.descricao)}</b></td>
      <td>${esc(clientMap[f.cliente_id] || 'Conta #' + f.cliente_id)}</td>
      <td style="font-weight:700;">${formatMoney(f.valor)}</td>
      <td><span class="badge ${esc(f.status)}">${esc(f.status)}</span></td>
      <td>${formatDate(f.vencimento)}</td>
      ${isStaff ? `<td style="white-space:nowrap;">
        ${f.status !== 'pago' ? `<button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--ok);" data-pay="${f.id}">Confirmar Pagamento</button>` : ''}
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/faturas/${f.id}">Excluir</button>
      </td>` : ''}
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Faturas &amp; Cobranças</h1><span class="muted">Controle financeiro, vencimentos e recebimentos</span></div>
      ${isStaff ? `<button class="btn" data-new>${ICONS.plus}<span>Nova Fatura</span></button>` : ''}
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Descrição</th><th>Cliente</th><th>Valor</th><th>Status</th><th>Vencimento</th>${isStaff ? '<th>Ações</th>' : ''}</tr></thead>
        <tbody>${rows || '<tr><td colspan="6" style="text-align:center; padding:32px;" class="muted">Nenhuma fatura lançada.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderKanban(isPipeline = false) {
  if (isPipeline) {
    const clientes = await apiRequest('/clientes');
    const cols = [
      { key: 'lead', label: 'Entrada (Lead)' },
      { key: 'proposta', label: 'Proposta Enviada' },
      { key: 'negociacao', label: 'Em Negociação' },
      { key: 'ativo', label: 'Cliente Fechado' }
    ];
    return `
      <div class="toolbar"><div><h1>Funil de Vendas</h1><span class="muted">Acompanhe e mova oportunidades entre as etapas comerciais</span></div><button class="btn" data-new>${ICONS.plus}<span>Novo Lead</span></button></div>
      <div class="app-kanban">
        ${cols.map((col) => `
          <section class="app-column" data-drop-col="${col.key}" data-drop-type="client">
            <div class="app-column-header">
              <b>${col.label}</b>
              <span class="filter-count">${clientes.filter((c) => c.status_funil === col.key).length}</span>
            </div>
            <div class="app-column-body">
              ${clientes.filter((c) => c.status_funil === col.key).map((c) => `
                <div class="app-ticket" draggable="true" data-drag-id="${c.id}" data-drag-type="client">
                  <b>${esc(c.nome_empresa)}</b>
                  <p class="muted" style="font-size:12px; margin:4px 0 10px;">${esc(c.contato_nome)}</p>
                  <div style="display:flex; gap:4px; flex-wrap:wrap;">
                    ${cols.filter((x) => x.key !== col.key).map((x) => `
                      <button class="btn secondary" style="padding:4px 8px; font-size:11px;" data-move-client="${c.id}:${x.key}">${ICONS.arrowRight}<span>${x.label.split(' ')[0]}</span></button>
                    `).join('')}
                  </div>
                </div>
              `).join('') || '<p class="muted" style="font-size:12px;">Nenhum registro nesta etapa</p>'}
            </div>
          </section>
        `).join('')}
      </div>`;
  }

  const tarefas = await apiRequest('/tarefas');
  const cols = [
    { key: 'pendente', label: 'A Fazer' },
    { key: 'fazendo', label: 'Em Andamento' },
    { key: 'revisao', label: 'Homologação' },
    { key: 'concluida', label: 'Concluída' }
  ];
  return `
    <div class="toolbar"><div><h1>Quadro Kanban</h1><span class="muted">Fluxo visual de execução das tarefas</span></div><button class="btn" data-new>${ICONS.plus}<span>Nova Tarefa</span></button></div>
    <div class="app-kanban">
      ${cols.map((col) => `
        <section class="app-column" data-drop-col="${col.key}" data-drop-type="task">
          <div class="app-column-header">
            <b>${col.label}</b>
            <span class="filter-count">${tarefas.filter((t) => t.status === col.key).length}</span>
          </div>
          <div class="app-column-body">
            ${tarefas.filter((t) => t.status === col.key).map((t) => `
              <div class="app-ticket" draggable="true" data-drag-id="${t.id}" data-drag-type="task">
                <b>${esc(t.titulo)}</b>
                <p class="muted" style="font-size:12px; margin:4px 0 10px;">Prazo: ${formatDate(t.prazo)}</p>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                  ${cols.filter((x) => x.key !== col.key).map((x) => `
                    <button class="btn secondary" style="padding:4px 8px; font-size:11px;" data-move-task="${t.id}:${x.key}">${ICONS.arrowRight}<span>${x.label}</span></button>
                  `).join('')}
                </div>
              </div>
            `).join('') || '<p class="muted" style="font-size:12px;">Nenhuma tarefa nesta coluna</p>'}
          </div>
        </section>
      `).join('')}
    </div>`;
}

async function renderAudit() {
  const logs = await apiRequest('/auditoria');
  return `
    <div class="toolbar"><div><h1>Logs de Auditoria</h1><span class="muted">Histórico de movimentações e segurança operacional</span></div></div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Data / Hora</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead>
        <tbody>${logs.map((l) => `<tr><td>${new Date(l.criado_em).toLocaleString('pt-BR')}</td><td><b>${esc(l.usuario_nome)}</b></td><td><span class="badge">${esc(l.acao)}</span></td><td>${esc(l.detalhes)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Nenhum registro encontrado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderProfile() {
  return `
    <div class="toolbar"><div><h1>Meu Perfil</h1><span class="muted">Informações da conta e nível de permissão</span></div></div>
    <div class="card" style="max-width:520px;">
      <div class="row-entity" style="margin-bottom:20px;">
        <div class="row-avatar" style="width:48px; height:48px; font-size:16px;">${initials(user.nome)}</div>
        <div>
          <h3 style="margin:0;">${esc(user.nome)}</h3>
          <span class="muted">${esc(user.email)}</span>
        </div>
      </div>
      <p><b>Nível de Acesso:</b> <span class="badge ativo">${esc(user.perfil)}</span></p>
      <p><b>Status da Conta:</b> <span class="badge ativo">Ativa</span></p>
    </div>`;
}

// ==================== MODAL DE RESPOSTA A SOLICITAÇÃO ====================
let modalMode = 'entity'; // 'entity' | 'quote_reply'

function openQuoteReplyModal(quoteObj) {
  modalMode = 'quote_reply';
  editingId = quoteObj.id;
  const titleEl = $('#record-modal-title');
  const box = $('#dynamic-record-fields');
  const saveBtn = $('#record-save-btn');

  titleEl.textContent = `Solicitação #${quoteObj.id} — ${quoteObj.nome}`;
  saveBtn.textContent = 'Registrar Atendimento';

  box.innerHTML = `
    <div style="display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between; margin-bottom:14px; font-size:13px;">
      <div><b>Empresa:</b> ${esc(quoteObj.empresa || 'Não informada')}</div>
      <div><b>Projeto:</b> <span class="badge">${esc(quoteObj.tipo_projeto || 'Geral')}</span></div>
      <div><b>E-mail:</b> <a href="mailto:${esc(quoteObj.email)}" style="color:var(--primary);">${esc(quoteObj.email)}</a></div>
      <div><b>Telefone:</b> ${esc(quoteObj.telefone || '-')}</div>
    </div>

    <label class="field-full" style="margin-bottom:14px;">
      <span>Descrição da solicitação (${formatDateTime(quoteObj.criado_em)}):</span>
      <div class="quote-box">${esc(quoteObj.mensagem)}</div>
    </label>

    ${quoteObj.resposta ? `
      <div class="quote-reply-box">
        <div style="font-size:12px; font-weight:700; color:var(--primary); margin-bottom:4px;">
          Retorno registrado por ${esc(quoteObj.respondido_por || 'Equipe Comercial')} em ${formatDateTime(quoteObj.respondido_em)}:
        </div>
        ${esc(quoteObj.resposta)}
      </div>
    ` : ''}

    <div class="formgrid" style="margin-bottom:14px;">
      <label>Status do Atendimento
        <select name="status">
          <option value="respondido" ${quoteObj.status === 'respondido' || quoteObj.status === 'novo' ? 'selected' : ''}>Respondido</option>
          <option value="em_atendimento" ${quoteObj.status === 'em_atendimento' ? 'selected' : ''}>Em Atendimento</option>
          <option value="convertido" ${quoteObj.status === 'convertido' ? 'selected' : ''}>Convertido em Projeto</option>
          <option value="arquivado" ${quoteObj.status === 'arquivado' ? 'selected' : ''}>Arquivado</option>
        </select>
      </label>
      <div style="display:flex; align-items:flex-end;">
        ${quoteObj.cliente_id ? `<button type="button" class="btn secondary" style="width:100%; justify-content:center;" onclick="document.getElementById('record-dialog').close(); window.nexusGo('projects', true);">+ Converter em Projeto</button>` : ''}
      </div>
    </div>

    <label class="field-full">
      <span>Parecer / Retorno Comercial *</span>
      <textarea name="resposta" rows="4" required placeholder="Descreva a proposta comercial, o retorno técnico ou os próximos passos do atendimento...">${esc(quoteObj.resposta || '')}</textarea>
    </label>
  `;

  recordDialog.showModal();
}

window.nexusReplyQuote = async (id) => {
  if (!cache.orcamentos?.length) {
    cache.orcamentos = await apiRequest('/orcamentos');
  }
  const found = cache.orcamentos.find((o) => o.id === id);
  if (found) openQuoteReplyModal(found);
};

// ==================== MODAL DE CADASTRO / EDIÇÃO ====================
async function openRecordModal(editObj = null) {
  modalMode = 'entity';
  editingId = editObj ? editObj.id : null;
  await preloadRefs();
  const titleEl = $('#record-modal-title');
  const box = $('#dynamic-record-fields');
  $('#record-save-btn').textContent = 'Salvar Registro';

  const clientOptions = cache.clientes.map((c) => `<option value="${c.id}" ${editObj?.cliente_id === c.id ? 'selected' : ''}>${esc(c.nome_empresa)}</option>`).join('');
  const userOptions = `<option value="">-- Sem responsável --</option>` + cache.usuarios.map((u) => `<option value="${u.id}" ${editObj?.responsavel_id === u.id ? 'selected' : ''}>${esc(u.nome)}</option>`).join('');
  const projectOptions = cache.projetos.map((p) => `<option value="${p.id}" ${editObj?.projeto_id === p.id ? 'selected' : ''}>${esc(p.titulo)}</option>`).join('');

  if (page === 'projects') {
    titleEl.textContent = editObj ? 'Editar Projeto' : 'Novo Projeto';
    box.innerHTML = `
      <div class="formgrid">
        <label>Título do Projeto *<input name="titulo" required value="${esc(editObj?.titulo || '')}"></label>
        <label>Cliente *<select name="cliente_id" required>${clientOptions || '<option value="">Selecione um cliente</option>'}</select></label>
        <label>Responsável<select name="responsavel_id">${userOptions}</select></label>
        <label>Status<select name="status">
          ${['planejamento', 'em_andamento', 'homologacao', 'concluido', 'cancelado'].map((s) => `<option value="${s}" ${editObj?.status === s ? 'selected' : ''}>${s.replace('_', ' ')}</option>`).join('')}
        </select></label>
        <label>Progresso (%)<input name="progresso" type="number" min="0" max="100" value="${editObj?.progresso ?? 0}"></label>
        <label>Valor Total (R$)<input name="valor_total" type="number" step="0.01" value="${editObj?.valor_total ?? 0}"></label>
        <label>Data Início<input name="data_inicio" type="date" value="${editObj?.data_inicio || ''}"></label>
        <label>Data Entrega<input name="data_entrega" type="date" value="${editObj?.data_entrega || ''}"></label>
      </div>
      <label class="field-full" style="margin-top:16px;">Descrição<textarea name="descricao" rows="3">${esc(editObj?.descricao || '')}</textarea></label>`;
  } else if (['customers', 'leads', 'pipeline'].includes(page)) {
    titleEl.textContent = editObj ? 'Editar Cliente / Lead' : 'Novo Cliente / Lead';
    const defFunil = page === 'leads' || page === 'pipeline' ? 'lead' : 'ativo';
    box.innerHTML = `
      <div class="formgrid">
        <label>Empresa *<input name="nome_empresa" required value="${esc(editObj?.nome_empresa || '')}"></label>
        <label>Nome do Contato *<input name="contato_nome" required value="${esc(editObj?.contato_nome || '')}"></label>
        <label>E-mail *<input name="email" type="email" required value="${esc(editObj?.email || '')}"></label>
        <label>Telefone / WhatsApp<input name="telefone" value="${esc(editObj?.telefone || '')}"></label>
        <label>Estágio no Funil<select name="status_funil">
          ${['lead', 'proposta', 'negociacao', 'ativo', 'inativo'].map((s) => `<option value="${s}" ${(editObj?.status_funil || defFunil) === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select></label>
        <label>Origem<input name="origem" placeholder="Ex.: Site Institucional, Indicação" value="${esc(editObj?.origem || '')}"></label>
      </div>
      <label class="field-full" style="margin-top:16px;">Observações<textarea name="observacoes" rows="3">${esc(editObj?.observacoes || '')}</textarea></label>`;
  } else if (page === 'users') {
    titleEl.textContent = editObj ? 'Editar Usuário' : 'Novo Usuário';
    box.innerHTML = `
      <div class="formgrid">
        <label>Nome Completo *<input name="nome" required value="${esc(editObj?.nome || '')}"></label>
        <label>E-mail *<input name="email" type="email" required value="${esc(editObj?.email || '')}"></label>
        <label>Senha ${editObj ? '(deixe vazio para manter)' : '*'}<input name="senha" type="password" ${editObj ? '' : 'required'} minlength="6"></label>
        <label>Perfil<select name="perfil">
          ${['admin', 'colaborador', 'cliente'].map((r) => `<option value="${r}" ${editObj?.perfil === r ? 'selected' : ''}>${r}</option>`).join('')}
        </select></label>
        <label>Status<select name="ativo">
          <option value="true" ${editObj?.ativo !== false ? 'selected' : ''}>Ativo</option>
          <option value="false" ${editObj?.ativo === false ? 'selected' : ''}>Inativo</option>
        </select></label>
      </div>`;
  } else if (['tasks', 'kanban'].includes(page)) {
    titleEl.textContent = editObj ? 'Editar Tarefa' : 'Nova Tarefa';
    box.innerHTML = `
      <div class="formgrid">
        <label>Título da Tarefa *<input name="titulo" required value="${esc(editObj?.titulo || '')}"></label>
        <label>Projeto *<select name="projeto_id" required>${projectOptions || '<option value="">Selecione um projeto</option>'}</select></label>
        <label>Responsável<select name="responsavel_id">${userOptions}</select></label>
        <label>Status<select name="status">
          ${['pendente', 'fazendo', 'revisao', 'concluida'].map((s) => `<option value="${s}" ${editObj?.status === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select></label>
        <label>Prazo<input name="prazo" type="date" value="${editObj?.prazo || ''}"></label>
      </div>`;
  } else if (page === 'invoices') {
    titleEl.textContent = 'Nova Fatura';
    box.innerHTML = `
      <div class="formgrid">
        <label>Descrição *<input name="descricao" required placeholder="Ex.: Parcela 1 - Implantação"></label>
        <label>Projeto *<select name="projeto_id" required>${projectOptions}</select></label>
        <label>Cliente *<select name="cliente_id" required>${clientOptions}</select></label>
        <label>Valor (R$) *<input name="valor" type="number" step="0.01" required></label>
        <label>Vencimento *<input name="vencimento" type="date" required></label>
        <label>Status<select name="status"><option value="pendente">pendente</option><option value="pago">pago</option></select></label>
      </div>`;
  }

  recordDialog.showModal();
}

recordForm.onsubmit = async (e) => {
  e.preventDefault();
  const raw = Object.fromEntries(new FormData(recordForm));

  try {
    if (modalMode === 'quote_reply') {
      await apiRequest(`/orcamentos/${editingId}/responder`, {
        method: 'PATCH',
        body: JSON.stringify({
          resposta: raw.resposta,
          status: raw.status
        })
      });
    } else if (page === 'projects') {
      await apiRequest(editingId ? `/projetos/${editingId}` : '/projetos', {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          titulo: raw.titulo,
          cliente_id: Number(raw.cliente_id),
          responsavel_id: raw.responsavel_id ? Number(raw.responsavel_id) : null,
          status: raw.status,
          progresso: Number(raw.progresso || 0),
          valor_total: Number(raw.valor_total || 0),
          data_inicio: raw.data_inicio || null,
          data_entrega: raw.data_entrega || null,
          descricao: raw.descricao || null
        })
      });
    } else if (['customers', 'leads', 'pipeline'].includes(page)) {
      await apiRequest(editingId ? `/clientes/${editingId}` : '/clientes', {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          nome_empresa: raw.nome_empresa,
          contato_nome: raw.contato_nome,
          email: raw.email,
          telefone: raw.telefone || null,
          status_funil: raw.status_funil,
          origem: raw.origem || null,
          observacoes: raw.observacoes || null
        })
      });
    } else if (page === 'users') {
      await apiRequest(editingId ? `/usuarios/${editingId}` : '/usuarios', {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          nome: raw.nome,
          email: raw.email,
          perfil: raw.perfil,
          ativo: raw.ativo === 'true',
          ...(raw.senha ? { senha: raw.senha } : {})
        })
      });
    } else if (['tasks', 'kanban'].includes(page)) {
      await apiRequest(editingId ? `/tarefas/${editingId}` : '/tarefas', {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          titulo: raw.titulo,
          projeto_id: Number(raw.projeto_id),
          responsavel_id: raw.responsavel_id ? Number(raw.responsavel_id) : null,
          status: raw.status,
          prazo: raw.prazo || null
        })
      });
    } else if (page === 'invoices') {
      await apiRequest('/faturas', {
        method: 'POST',
        body: JSON.stringify({
          descricao: raw.descricao,
          projeto_id: Number(raw.projeto_id),
          cliente_id: Number(raw.cliente_id),
          valor: Number(raw.valor),
          vencimento: raw.vencimento,
          status: raw.status
        })
      });
    }

    recordDialog.close();
    invalidateCache();
    render();
  } catch (err) {
    alert('Não foi possível concluir a operação: ' + err.message);
  }
};

// ==================== RENDERIZADOR PRINCIPAL ====================
async function render() {
  const btn = $(`[data-app-page="${page}"]`);
  const labelText = btn?.querySelector('.nav-label')?.textContent.trim() || 'Dashboard';
  $('#app-title').textContent = labelText;
  $$('[data-app-page]').forEach((x) => x.classList.toggle('active', x.dataset.appPage === page));

  try {
    if (page === 'dashboard') view.innerHTML = await renderDashboard();
    else if (page === 'quotes') view.innerHTML = await renderQuotes();
    else if (page === 'projects') view.innerHTML = await renderProjects();
    else if (page === 'customers') view.innerHTML = await renderClients(false);
    else if (page === 'leads') view.innerHTML = await renderClients(true);
    else if (page === 'pipeline') view.innerHTML = await renderKanban(true);
    else if (page === 'users') view.innerHTML = await renderUsers();
    else if (page === 'tasks') view.innerHTML = await renderTasks();
    else if (page === 'kanban') view.innerHTML = await renderKanban(false);
    else if (page === 'invoices') view.innerHTML = await renderInvoices();
    else if (page === 'audit') view.innerHTML = await renderAudit();
    else if (page === 'profile') view.innerHTML = await renderProfile();

    $$('[data-new]').forEach((b) => (b.onclick = () => openRecordModal(null)));
    $$('[data-edit]').forEach((b) => (b.onclick = () => openRecordModal(JSON.parse(b.dataset.edit))));
    $$('[data-reply]').forEach((b) => (b.onclick = () => openQuoteReplyModal(JSON.parse(b.dataset.reply))));
    $$('[data-filter]').forEach((b) => (b.onclick = () => { statusFilter = b.dataset.filter; render(); }));
    $$('[data-del]').forEach((b) => (b.onclick = async () => {
      if (!confirm('Confirma a exclusão permanente deste registro?')) return;
      await apiRequest(b.dataset.del, { method: 'DELETE' });
      invalidateCache();
      render();
    }));
    $$('[data-pay]').forEach((b) => (b.onclick = async () => {
      await apiRequest(`/faturas/${b.dataset.pay}`, { method: 'PATCH', body: JSON.stringify({ status: 'pago' }) });
      invalidateCache();
      render();
    }));
    $$('[data-move-client]').forEach((b) => (b.onclick = async () => {
      const [id, status_funil] = b.dataset.moveClient.split(':');
      await apiRequest(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify({ status_funil }) });
      invalidateCache();
      render();
    }));
    $$('[data-move-task]').forEach((b) => (b.onclick = async () => {
      const [id, status] = b.dataset.moveTask.split(':');
      await apiRequest(`/tarefas/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      invalidateCache();
      render();
    }));

    // Drag and Drop para Kanban e Funil
    let dragged = null;
    $$('[draggable="true"]').forEach((card) => {
      card.addEventListener('dragstart', () => {
        dragged = { id: card.dataset.dragId, type: card.dataset.dragType };
      });
    });
    $$('[data-drop-col]').forEach((col) => {
      col.addEventListener('dragover', (e) => {
        e.preventDefault();
        col.classList.add('drag-over');
      });
      col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
      col.addEventListener('drop', async (e) => {
        e.preventDefault();
        col.classList.remove('drag-over');
        if (!dragged) return;
        const targetStatus = col.dataset.dropCol;
        if (dragged.type === 'client') {
          await apiRequest(`/clientes/${dragged.id}`, { method: 'PATCH', body: JSON.stringify({ status_funil: targetStatus }) });
        } else if (dragged.type === 'task') {
          await apiRequest(`/tarefas/${dragged.id}`, { method: 'PATCH', body: JSON.stringify({ status: targetStatus }) });
        }
        dragged = null;
        render();
      });
    });
  } catch (err) {
    view.innerHTML = `<div class="card" style="border-left:4px solid var(--danger);"><b>Aviso:</b> ${esc(err.message)}</div>`;
  }
}

window.nexusGo = (targetPage, openCreate = false) => {
  page = targetPage;
  statusFilter = 'todos';
  closeMobileDrawer();
  render().then(() => {
    if (openCreate) openRecordModal(null);
  });
};

$$('[data-app-page]').forEach((b) => (b.onclick = () => {
  page = b.dataset.appPage;
  statusFilter = 'todos';
  closeMobileDrawer();
  render();
}));

$('#global-search')?.addEventListener('input', (e) => {
  searchTerm = e.target.value;
  if (page !== 'dashboard' && page !== 'profile') render();
});

$$('[data-close-record]').forEach((b) => (b.onclick = () => recordDialog.close()));

$('#app-logout')?.addEventListener('click', () => {
  clearSession();
  window.location.href = '../index.html';
});

if (!getToken()) {
  window.location.href = '../login.html';
} else {
  const savedUser = (() => {
    try { return JSON.parse(localStorage.getItem('nexus_user') || 'null'); } catch { return null; }
  })();

  if (savedUser) {
    if (savedUser.perfil === 'cliente') {
      window.location.href = './portal.html';
    } else {
      user = savedUser;
      $('#app-user-name').textContent = savedUser.nome;
      $('#user-avatar-initials').textContent = initials(savedUser.nome);
      render();
    }
  }

  apiRequest('/auth/me')
    .then((u) => {
      const firstPaint = !user;
      user = u;
      localStorage.setItem('nexus_user', JSON.stringify(u));
      if (u.perfil === 'cliente') {
        window.location.href = './portal.html';
        return;
      }
      $('#app-user-name').textContent = u.nome;
      $('#user-avatar-initials').textContent = initials(u.nome);
      if (firstPaint) render();
    })
    .catch(() => {
      clearSession();
      window.location.href = '../login.html';
    });
}
