import { apiRequest, clearSession, getToken } from './config.js';
import { showConfirmModal, showNoticeModal, showToast } from './ui.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const shell = $('#app-shell');
const side = $('#app-side');
const backdrop = $('#sidebar-backdrop');
const view = $('#app-view');
const recordDialog = $('#record-dialog');
const recordForm = $('#record-form');
const plannerDialog = $('#planner-dialog');
const plannerContainer = $('#planner-modal-container');
const holeriteDialog = $('#holerite-dialog');
const holeriteContainer = $('#holerite-modal-container');

let page = 'dashboard';
let user = null;
let editingId = null;
let searchTerm = '';
let statusFilter = 'todos';
let holeriteTab = 'holerites'; // 'holerites' | 'informes'
let holeriteUserFilter = 'todos';
let cache = {
  kpi: null,
  clientes: [],
  usuarios: [],
  projetos: [],
  orcamentos: [],
  tarefas: [],
  holerites: [],
  informes: [],
  loadedAt: 0
};
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
    holerites: data.holerites || [],
    informes: data.informes || [],
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
  const s = String(v).slice(0, 10);
  const d = new Date(s + 'T00:00:00');
  return isNaN(d) ? v : d.toLocaleDateString('pt-BR');
};

const formatDateTime = (v) => {
  if (!v) return '-';
  const d = new Date(v);
  return isNaN(d) ? v : d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

function safeParseJsonArray(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo selecionado.'));
    reader.readAsDataURL(file);
  });
}

const ICONS = {
  plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
  users: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
  inbox: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
  folder: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path></svg>',
  check: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>',
  dollar: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>',
  arrowRight: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>',
  reply: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>',
  paperclip: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>',
  calendar: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
  cake: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8"></path><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1"></path><path d="M2 21h20"></path><path d="M7 8v3"></path><path d="M12 8v3"></path><path d="M17 8v3"></path><path d="M7 4h.01"></path><path d="M12 4h.01"></path><path d="M17 4h.01"></path></svg>',
  award: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"></circle><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"></path></svg>',
  fileText: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>',
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

// ==================== CARREGAMENTO & PESQUISA GLOBAL ====================
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
  if (!searchTerm || !searchTerm.trim()) return true;
  const q = searchTerm.trim().toLowerCase();
  return texts.some((t) => String(t ?? '').toLowerCase().includes(q));
}

function renderGlobalSearchBanner() {
  const q = searchTerm.trim();
  if (!q) return '';

  const hits = [];
  (cache.clientes || []).forEach((c) => {
    if (matchSearch([c.nome_empresa, c.contato_nome, c.email, c.telefone, c.status_funil])) {
      hits.push({
        type: 'Cliente / Lead',
        title: c.nome_empresa,
        sub: `${c.contato_nome} • ${c.email}`,
        action: `window.nexusGo('customers')`
      });
    }
  });
  (cache.projetos || []).forEach((p) => {
    if (matchSearch([p.titulo, p.descricao, p.status])) {
      hits.push({
        type: 'Projeto',
        title: p.titulo,
        sub: `Status: ${p.status.replace('_', ' ')} • ${formatMoney(p.valor_total)}`,
        action: `window.nexusGo('projects')`
      });
    }
  });
  (cache.tarefas || []).forEach((t) => {
    if (matchSearch([t.titulo, t.descricao, t.status])) {
      hits.push({
        type: 'Tarefa Planner',
        title: t.titulo,
        sub: `Coluna: ${t.status} • Prazo: ${formatDate(t.prazo)}`,
        action: `window.nexusOpenPlannerTask(${t.id})`
      });
    }
  });
  (cache.orcamentos || []).forEach((o) => {
    if (matchSearch([o.nome, o.empresa, o.email, o.tipo_projeto, o.mensagem])) {
      hits.push({
        type: 'Solicitação',
        title: o.nome,
        sub: `${o.tipo_projeto || 'Orçamento'} • ${o.email}`,
        action: `window.nexusReplyQuote(${o.id})`
      });
    }
  });
  (cache.usuarios || []).forEach((u) => {
    if (matchSearch([u.nome, u.email, u.cargo, u.perfil, u.cidade])) {
      hits.push({
        type: 'Colaborador / Usuário',
        title: u.nome,
        sub: `${u.cargo || u.perfil} • ${u.email}`,
        action: `window.nexusGo('users')`
      });
    }
  });
  (cache.holerites || []).forEach((h) => {
    const uName = (cache.usuarios || []).find((u) => u.id === h.usuario_id)?.nome || '';
    if (matchSearch([h.competencia, h.tipo, uName, h.status])) {
      hits.push({
        type: 'Holerite',
        title: `${h.competencia} — ${h.tipo}`,
        sub: `${uName} • Líquido: ${formatMoney(h.valor_liquido)}`,
        action: `window.nexusGo('holerite')`
      });
    }
  });

  return `
    <div class="card global-search-banner">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
        <div>
          <b>Resultados da Pesquisa Global para "${esc(q)}"</b>
          <span class="muted" style="font-size:12.5px; margin-left:8px;">(${hits.length} registro(s) encontrado(s) em todo o sistema)</span>
        </div>
        <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusClearSearch()">Limpar Filtro</button>
      </div>
      ${hits.length ? `
        <div class="global-search-grid">
          ${hits.slice(0, 8).map((h) => `
            <div class="search-hit-item" onclick="${h.action}">
              <div style="min-width:0;">
                <span class="badge" style="font-size:10.5px; margin-bottom:4px;">${esc(h.type)}</span>
                <div style="font-weight:700; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(h.title)}</div>
                <div class="muted" style="font-size:11.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(h.sub)}</div>
              </div>
              <span style="color:var(--primary);">${ICONS.arrowRight}</span>
            </div>
          `).join('')}
        </div>
      ` : '<p class="muted" style="margin:10px 0 0;">Nenhum registro correspondente encontrado nas abas do sistema.</p>'}
    </div>
  `;
}

// ==================== TELAS DO SISTEMA ====================
async function renderDashboard() {
  const { kpi, projetos, orcamentos, usuarios } = await loadBootstrap();
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();
  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  // Identificar usuários fazendo aniversário no mês OU contratação/criação de conta no mês
  const teamMilestones = (usuarios || [])
    .filter((u) => u.ativo && u.perfil !== 'cliente')
    .map((u) => {
      let isBdayMonth = false;
      let bdayLabel = '';
      if (u.data_nascimento) {
        const parts = String(u.data_nascimento).slice(0, 10).split('-');
        if (parts.length === 3 && Number(parts[1]) === currentMonth) {
          isBdayMonth = true;
          bdayLabel = `${parts[2]}/${parts[1]}`;
        }
      }

      let isHireMonth = false;
      let hireLabel = '';
      let yearsCount = 0;
      const hireSource = u.data_contratacao || u.criado_em;
      if (hireSource) {
        const s = String(hireSource).slice(0, 10);
        const parts = s.split('-');
        if (parts.length === 3 && Number(parts[1]) === currentMonth) {
          isHireMonth = true;
          hireLabel = `${parts[2]}/${parts[1]}/${parts[0]}`;
          yearsCount = Math.max(0, currentYear - Number(parts[0]));
        }
      }

      return { ...u, isBdayMonth, bdayLabel, isHireMonth, hireLabel, yearsCount };
    })
    .filter((u) => u.isBdayMonth || u.isHireMonth);

  return `
    <div class="dashboard-layout">
      ${renderGlobalSearchBanner()}

      <div class="toolbar" style="margin-bottom:0;">
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
        <div class="card metric" style="cursor:pointer;" onclick="window.nexusGo('customers')">
          <div class="metric-head">
            <span class="title">Clientes &amp; Leads</span>
            <span class="metric-icon">${ICONS.users}</span>
          </div>
          <strong>${kpi.total_clientes}</strong>
          <span class="pill-info">${kpi.leads_abertos} oportunidades em andamento</span>
        </div>
        <div class="card metric" style="cursor:pointer;" onclick="window.nexusGo('projects')">
          <div class="metric-head">
            <span class="title">Projetos Ativos</span>
            <span class="metric-icon">${ICONS.folder}</span>
          </div>
          <strong>${kpi.projetos_ativos}</strong>
          <span class="pill-info">Em execução e homologação</span>
        </div>
        <div class="card metric" style="cursor:pointer;" onclick="window.nexusGo('invoices')">
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
          <div class="toolbar" style="margin-bottom:10px;">
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
          <div class="toolbar" style="margin-bottom:10px;">
            <h3 style="margin:0; font-size:16px;">Projetos em Andamento</h3>
            <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusGo('projects')">Ver todos</button>
          </div>
          ${projetos.slice(0, 5).map((p) => `
            <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px; cursor:pointer;" onclick="window.nexusGo('projects')">
              <div>
                <b>${esc(p.titulo)}</b>
                <div class="muted" style="font-size:12px;">Progresso: ${p.progresso}% • ${formatMoney(p.valor_total)}</div>
              </div>
              <span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span>
            </div>
          `).join('') || '<p class="muted">Nenhum projeto em andamento.</p>'}
        </div>
      </div>

      <div class="card milestones-card">
        <div class="milestones-header">
          <div>
            <h3 style="margin:0; font-size:15.5px;">Aniversariantes &amp; Tempo de Casa — ${monthNames[now.getMonth()]}</h3>
            <span class="muted" style="font-size:12px;">Colaboradores celebrando aniversário pessoal ou aniversário de contratação neste mês</span>
          </div>
          <span class="filter-count">${teamMilestones.length} destaque(s) no mês</span>
        </div>

        ${teamMilestones.length ? `
          <div class="milestones-grid">
            ${teamMilestones.map((u) => `
              <div class="milestone-user-card">
                <div class="milestone-avatar ${u.isBdayMonth ? 'bday' : 'hire'}">${initials(u.nome)}</div>
                <div style="min-width:0; flex:1;">
                  <div style="font-weight:700; font-size:14px; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(u.nome)}</div>
                  <div class="muted" style="font-size:12px;">${esc(u.cargo || (u.perfil === 'admin' ? 'Administrador' : 'Colaborador Nexus'))}</div>
                  <div class="milestone-badges">
                    ${u.isBdayMonth ? `<span class="milestone-pill bday">${ICONS.cake} Aniversário • ${esc(u.bdayLabel)}</span>` : ''}
                    ${u.isHireMonth ? `<span class="milestone-pill hire">${ICONS.award} ${u.yearsCount > 0 ? `${u.yearsCount} ano(s) de casa` : 'Contratação no mês'} • ${esc(u.hireLabel)}</span>` : ''}
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : '<p class="muted" style="margin:0; font-size:13px;">Nenhum aniversariante ou marco de contratação registrado para este mês.</p>'}
      </div>
    </div>`;
}

async function renderQuotes(useCache = false) {
  if (!useCache || !cache.loadedAt) {
    cache.orcamentos = await apiRequest('/orcamentos');
  }
  const allItems = cache.orcamentos || [];
  updateQuotesBadge();

  const items = allItems.filter((o) => {
    const okStatus = statusFilter === 'todos' || o.status === statusFilter;
    const okSearch = matchSearch([o.nome, o.empresa, o.email, o.telefone, o.tipo_projeto, o.mensagem, o.resposta, o.status]);
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
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/orcamentos/${o.id}" data-label="${esc(o.nome)}">Excluir</button>
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

async function renderProjects(useCache = false) {
  await preloadRefs();
  if (!useCache || !cache.projetos.length) {
    cache.projetos = await apiRequest('/projetos');
  }
  const allItems = cache.projetos;
  const clientMap = Object.fromEntries(cache.clientes.map((c) => [c.id, c.nome_empresa]));
  const userMap = Object.fromEntries(cache.usuarios.map((u) => [u.id, u.nome]));
  const isStaff = internalRoles.has(user.perfil);

  const items = allItems.filter((p) => {
    const okStatus = statusFilter === 'todos' || p.status === statusFilter;
    const okSearch = matchSearch([p.titulo, p.descricao, clientMap[p.cliente_id], userMap[p.responsavel_id], p.status]);
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
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/projetos/${p.id}" data-label="${esc(p.titulo)}">Excluir</button>
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

async function renderClients(onlyLeads = false, useCache = false) {
  if (!useCache || !cache.clientes.length) {
    cache.clientes = await apiRequest('/clientes');
  }
  const allItems = onlyLeads ? cache.clientes.filter((c) => c.status_funil === 'lead') : cache.clientes;
  const items = allItems.filter((c) => {
    const okStatus = statusFilter === 'todos' || c.status_funil === statusFilter;
    const okSearch = matchSearch([c.nome_empresa, c.contato_nome, c.email, c.telefone, c.origem, c.status_funil]);
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
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/clientes/${c.id}" data-label="${esc(c.nome_empresa)}">Excluir</button>
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

async function renderUsers(useCache = false) {
  if (!useCache || !cache.usuarios.length) {
    cache.usuarios = await apiRequest('/usuarios');
  }
  const allItems = cache.usuarios;
  const items = allItems.filter((u) => matchSearch([u.nome, u.email, u.perfil, u.cargo, u.cpf, u.cidade]));

  const rows = items.map((u) => `
    <tr>
      <td>
        <div class="row-entity">
          <div class="row-avatar">${initials(u.nome)}</div>
          <div>
            <b>${esc(u.nome)}</b>
            ${u.cargo ? `<div class="muted" style="font-size:12px;">${esc(u.cargo)}</div>` : ''}
          </div>
        </div>
      </td>
      <td>${esc(u.email)}</td>
      <td><span class="badge">${esc(u.perfil)}</span></td>
      <td>${formatDate(u.data_contratacao || u.criado_em)}</td>
      <td><span class="badge ${u.ativo ? 'ativo' : 'inativo'}">${u.ativo ? 'Ativo' : 'Inativo'}</span></td>
      <td style="white-space:nowrap;">
        <button class="btn secondary" style="padding:6px 10px; font-size:12px;" data-edit='${JSON.stringify(u).replace(/'/g, "&apos;")}'>Editar</button>
        ${u.id !== user.id ? `<button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/usuarios/${u.id}" data-label="${esc(u.nome)}">Excluir</button>` : ''}
      </td>
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Usuários e Perfis</h1><span class="muted">Controle de acesso para administradores, colaboradores e clientes</span></div>
      <button class="btn" data-new>${ICONS.plus}<span>Novo Usuário</span></button>
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Usuário</th><th>E-mail</th><th>Perfil</th><th>Contratação</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function renderTasks(useCache = false) {
  await preloadRefs();
  if (!useCache || !cache.tarefas.length) {
    cache.tarefas = await apiRequest('/tarefas');
  }
  const allItems = cache.tarefas;
  const projMap = Object.fromEntries(cache.projetos.map((p) => [p.id, p.titulo]));
  const userMap = Object.fromEntries(cache.usuarios.map((u) => [u.id, u.nome]));
  const items = allItems.filter((t) => matchSearch([t.titulo, t.descricao, projMap[t.projeto_id], userMap[t.responsavel_id], t.status, t.prioridade]));

  const rows = items.map((t) => {
    const checklist = safeParseJsonArray(t.checklist_json);
    const anexos = safeParseJsonArray(t.anexos_json);
    return `
      <tr>
        <td>
          <b>${esc(t.titulo)}</b>
          <div class="muted" style="font-size:12px;">
            ${checklist.length ? `Checklist: ${checklist.filter((c) => c.concluido).length}/${checklist.length} • ` : ''}
            ${anexos.length ? `${anexos.length} anexo(s)` : ''}
          </div>
        </td>
        <td>${esc(projMap[t.projeto_id] || 'Projeto #' + t.projeto_id)}</td>
        <td>${esc(userMap[t.responsavel_id] || '-')}</td>
        <td><span class="prio-badge prio-${esc(t.prioridade || 'media')}">${esc(t.prioridade || 'media')}</span></td>
        <td><span class="badge ${esc(t.status)}">${esc(t.status)}</span></td>
        <td>${formatDate(t.prazo)}</td>
        <td style="white-space:nowrap;">
          <button class="btn secondary" style="padding:6px 10px; font-size:12px;" onclick="window.nexusOpenPlannerTask(${t.id})">Abrir Planner</button>
          <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/tarefas/${t.id}" data-label="${esc(t.titulo)}">Excluir</button>
        </td>
      </tr>`;
  }).join('');

  return `
    <div class="toolbar">
      <div><h1>Tarefas &amp; Atividades</h1><span class="muted">Acompanhamento operacional das entregas por projeto</span></div>
      <div style="display:flex; gap:10px;">
        <button class="btn secondary" onclick="window.nexusGo('kanban')">Abrir Quadro Planner</button>
        <button class="btn" onclick="window.nexusOpenNewPlannerTask('pendente')">${ICONS.plus}<span>Nova Tarefa</span></button>
      </div>
    </div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Tarefa</th><th>Projeto</th><th>Responsável</th><th>Prioridade</th><th>Status</th><th>Prazo</th><th>Ações</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center; padding:32px;" class="muted">Nenhuma tarefa cadastrada.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderInvoices(useCache = false) {
  await preloadRefs();
  const allItems = await apiRequest('/faturas');
  const clientMap = Object.fromEntries(cache.clientes.map((c) => [c.id, c.nome_empresa]));
  const isStaff = internalRoles.has(user.perfil);
  const items = allItems.filter((f) => matchSearch([f.descricao, clientMap[f.cliente_id], f.status, f.vencimento]));

  const rows = items.map((f) => `
    <tr>
      <td><b>${esc(f.descricao)}</b></td>
      <td>${esc(clientMap[f.cliente_id] || 'Conta #' + f.cliente_id)}</td>
      <td style="font-weight:700;">${formatMoney(f.valor)}</td>
      <td><span class="badge ${esc(f.status)}">${esc(f.status)}</span></td>
      <td>${formatDate(f.vencimento)}</td>
      ${isStaff ? `<td style="white-space:nowrap;">
        ${f.status !== 'pago' ? `<button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--ok);" data-pay="${f.id}">Confirmar Pagamento</button>` : ''}
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/faturas/${f.id}" data-label="${esc(f.descricao)}">Excluir</button>
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

// ==================== HOLERITE, FOLHA DE PAGAMENTO & INFORME DE RENDIMENTOS ====================
async function renderHolerite(useCache = false) {
  await preloadRefs();
  if (!useCache || !cache.loadedAt) {
    const [holerites, informes] = await Promise.all([
      apiRequest('/holerites'),
      apiRequest('/informes-rendimentos')
    ]);
    cache.holerites = holerites;
    cache.informes = informes;
  }

  const isAdmin = user?.perfil === 'admin';
  const userMap = Object.fromEntries((cache.usuarios || []).map((u) => [u.id, u]));
  const staffUsers = (cache.usuarios || []).filter((u) => u.perfil !== 'cliente');

  const allHolerites = cache.holerites || [];
  const allInformes = cache.informes || [];

  const filteredHolerites = allHolerites.filter((h) => {
    const emp = userMap[h.usuario_id];
    const okUser = !isAdmin || holeriteUserFilter === 'todos' || String(h.usuario_id) === String(holeriteUserFilter);
    const okSearch = matchSearch([h.competencia, h.tipo, h.status, emp?.nome, emp?.cargo, h.descricao_proventos, h.observacoes]);
    return okUser && okSearch;
  });

  const filteredInformes = allInformes.filter((inf) => {
    const emp = userMap[inf.usuario_id];
    const okUser = !isAdmin || holeriteUserFilter === 'todos' || String(inf.usuario_id) === String(holeriteUserFilter);
    const okSearch = matchSearch([inf.ano_calendario, inf.ano_exercicio, emp?.nome, emp?.cpf, inf.observacoes]);
    return okUser && okSearch;
  });

  const myHolerites = allHolerites.filter((h) => h.usuario_id === user.id);
  const latestSlip = myHolerites[0] || filteredHolerites[0] || null;
  const currentYearStr = String(new Date().getFullYear());
  const totalYearNet = (isAdmin && holeriteUserFilter !== 'todos' ? filteredHolerites : myHolerites)
    .filter((h) => h.status === 'pago' && String(h.competencia || '').includes(currentYearStr))
    .reduce((acc, h) => acc + Number(h.valor_liquido || 0), 0);

  const holeriteRows = filteredHolerites.map((h) => {
    const emp = userMap[h.usuario_id] || { nome: 'Colaborador #' + h.usuario_id, cargo: '' };
    return `
      <tr>
        <td><b>${esc(h.competencia)}</b></td>
        ${isAdmin ? `<td>
          <div class="row-entity">
            <div class="row-avatar">${initials(emp.nome)}</div>
            <div>
              <b>${esc(emp.nome)}</b>
              <div class="muted" style="font-size:11.5px;">${esc(emp.cargo || emp.perfil || '')}</div>
            </div>
          </div>
        </td>` : ''}
        <td><span class="badge">${esc(h.tipo)}</span></td>
        <td>${formatMoney(h.salario_base)}</td>
        <td style="color:var(--ok); font-weight:600;">+${formatMoney(h.proventos)}</td>
        <td style="color:var(--danger); font-weight:600;">-${formatMoney(h.descontos)}</td>
        <td style="font-weight:800; color:var(--primary);">${formatMoney(h.valor_liquido)}</td>
        <td>${formatDate(h.data_pagamento)}</td>
        <td><span class="badge ${esc(h.status === 'pago' ? 'pago' : 'pendente')}">${esc(h.status)}</span></td>
        <td style="white-space:nowrap;">
          <button type="button" class="btn secondary" style="padding:6px 10px; font-size:12px;" onclick="window.nexusViewHolerite(${h.id})">${ICONS.fileText}<span>Demonstrativo</span></button>
          ${h.anexo_data ? `<a href="${h.anexo_data}" download="${esc(h.anexo_nome || 'holerite.pdf')}" class="btn secondary" style="padding:6px 10px; font-size:12px; text-decoration:none;">PDF</a>` : ''}
          ${isAdmin && h.status !== 'pago' ? `<button type="button" class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--ok);" onclick="window.nexusPayHolerite(${h.id})">Pagar</button>` : ''}
          ${isAdmin ? `<button type="button" class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/holerites/${h.id}" data-label="Holerite ${esc(h.competencia)} - ${esc(emp.nome)}">Excluir</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');

  const informeRows = filteredInformes.map((inf) => {
    const emp = userMap[inf.usuario_id] || { nome: 'Colaborador #' + inf.usuario_id, cpf: '' };
    return `
      <tr>
        <td><b>Ano-Calendário ${esc(inf.ano_calendario)}</b> <span class="muted" style="font-size:12px;">(Exercício ${esc(inf.ano_exercicio)})</span></td>
        ${isAdmin ? `<td><b>${esc(emp.nome)}</b><div class="muted" style="font-size:11.5px;">CPF: ${esc(emp.cpf || 'Não informado')}</div></td>` : ''}
        <td style="font-weight:600;">${formatMoney(inf.rendimentos_tributaveis)}</td>
        <td>${formatMoney(inf.contribuicao_previdenciaria)}</td>
        <td>${formatMoney(inf.irrf_retido)}</td>
        <td>${formatMoney(inf.decimo_terceiro)}</td>
        <td style="white-space:nowrap;">
          <button type="button" class="btn secondary" style="padding:6px 10px; font-size:12px;" onclick="window.nexusViewInforme(${inf.id})">${ICONS.fileText}<span>Visualizar Informe</span></button>
          ${inf.anexo_data ? `<a href="${inf.anexo_data}" download="${esc(inf.anexo_nome || 'informe_rendimentos.pdf')}" class="btn secondary" style="padding:6px 10px; font-size:12px; text-decoration:none;">Baixar PDF</a>` : ''}
          ${isAdmin ? `<button type="button" class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/informes-rendimentos/${inf.id}" data-label="Informe ${esc(inf.ano_calendario)} - ${esc(emp.nome)}">Excluir</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');

  return `
    <div class="toolbar">
      <div>
        <h1>Holerite &amp; Rendimentos</h1>
        <span class="muted">${isAdmin ? 'Gestão da folha de pagamento, demonstrativos salariais e informes de rendimentos da equipe' : 'Consulta de demonstrativos de pagamento e informes anuais de rendimentos (IRRF)'}</span>
      </div>
      ${isAdmin ? `
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button type="button" class="btn secondary" onclick="window.nexusOpenNewInformeModal()">${ICONS.plus}<span>Publicar Informe de Rendimentos</span></button>
          <button type="button" class="btn" onclick="window.nexusOpenNewHoleriteModal()">${ICONS.plus}<span>Lançar Holerite</span></button>
        </div>
      ` : ''}
    </div>

    <div class="grid" style="margin-bottom:18px;">
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Último Salário Líquido</span>
          <span class="metric-icon">${ICONS.dollar}</span>
        </div>
        <strong>${latestSlip ? formatMoney(latestSlip.valor_liquido) : formatMoney(user?.salario_base || 0)}</strong>
        <span class="pill-info">${latestSlip ? `Competência ${esc(latestSlip.competencia)}` : 'Aguardando lançamento'}</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Salário Base Cadastral</span>
          <span class="metric-icon">${ICONS.fileText}</span>
        </div>
        <strong>${formatMoney(latestSlip ? latestSlip.salario_base : (user?.salario_base || 0))}</strong>
        <span class="pill-info">${esc(user?.cargo || 'Colaborador Nexus Code')}</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Acumulado Pago (${currentYearStr})</span>
          <span class="metric-icon">${ICONS.check}</span>
        </div>
        <strong>${formatMoney(totalYearNet)}</strong>
        <span class="pill-info">${myHolerites.length} demonstrativo(s) registrado(s)</span>
      </div>
      <div class="card metric">
        <div class="metric-head">
          <span class="title">Informes de Rendimentos</span>
          <span class="metric-icon">${ICONS.award}</span>
        </div>
        <strong>${allInformes.length}</strong>
        <span class="pill-info">Disponíveis para IRPF</span>
      </div>
    </div>

    <div class="filter-bar" style="justify-content:space-between;">
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button type="button" class="filter-pill ${holeriteTab === 'holerites' ? 'active' : ''}" onclick="window.nexusSetHoleriteTab('holerites')">
          Demonstrativos de Pagamento <span class="filter-count">${filteredHolerites.length}</span>
        </button>
        <button type="button" class="filter-pill ${holeriteTab === 'informes' ? 'active' : ''}" onclick="window.nexusSetHoleriteTab('informes')">
          Informe de Rendimentos (IRRF) <span class="filter-count">${filteredInformes.length}</span>
        </button>
      </div>
      ${isAdmin ? `
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="muted" style="font-size:12.5px;">Colaborador:</span>
          <select class="nc-input" style="height:34px; padding:4px 10px; font-size:13px; width:auto;" onchange="window.nexusSetHoleriteUser(this.value)">
            <option value="todos" ${holeriteUserFilter === 'todos' ? 'selected' : ''}>Todos os Colaboradores</option>
            ${staffUsers.map((u) => `<option value="${u.id}" ${String(holeriteUserFilter) === String(u.id) ? 'selected' : ''}>${esc(u.nome)}</option>`).join('')}
          </select>
        </div>
      ` : ''}
    </div>

    ${holeriteTab === 'holerites' ? `
      <div class="card table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Competência</th>
              ${isAdmin ? '<th>Colaborador</th>' : ''}
              <th>Tipo</th>
              <th>Salário Base</th>
              <th>Proventos</th>
              <th>Descontos</th>
              <th>Valor Líquido</th>
              <th>Pagamento</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            ${holeriteRows || `<tr><td colspan="${isAdmin ? 10 : 9}" style="text-align:center; padding:32px;" class="muted">Nenhum demonstrativo de pagamento encontrado.</td></tr>`}
          </tbody>
        </table>
      </div>
    ` : `
      <div class="card table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Ano-Calendário</th>
              ${isAdmin ? '<th>Colaborador</th>' : ''}
              <th>Rendimentos Tributáveis</th>
              <th>Previdência (INSS)</th>
              <th>IRRF Retido</th>
              <th>13º Salário</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            ${informeRows || `<tr><td colspan="${isAdmin ? 7 : 6}" style="text-align:center; padding:32px;" class="muted">Nenhum informe de rendimentos publicado até o momento.</td></tr>`}
          </tbody>
        </table>
      </div>
    `}
  `;
}

window.nexusSetHoleriteTab = (tab) => {
  holeriteTab = tab;
  render(true);
};

window.nexusSetHoleriteUser = (uid) => {
  holeriteUserFilter = uid;
  render(true);
};

window.nexusPayHolerite = (id) => {
  showConfirmModal({
    title: 'Confirmar Pagamento Salarial',
    message: 'Deseja marcar este holerite como Pago?',
    confirmText: 'Confirmar Pagamento',
    variant: 'primary',
    onConfirm: async () => {
      await apiRequest(`/holerites/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'pago', data_pagamento: new Date().toISOString().slice(0, 10) })
      });
      invalidateCache();
      showToast('Holerite marcado como pago.', 'success');
      await render();
    }
  });
};

window.nexusOpenNewHoleriteModal = async () => {
  await preloadRefs();
  const staffUsers = (cache.usuarios || []).filter((u) => u.perfil !== 'cliente');
  const now = new Date();
  const defaultComp = `${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`;
  const todayStr = now.toISOString().slice(0, 10);

  holeriteContainer.innerHTML = `
    <form id="new-holerite-form">
      <div class="modal-header">
        <h2>Lançar Demonstrativo de Pagamento (Holerite)</h2>
        <button type="button" class="btn secondary icon-only" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
      </div>
      <div class="formgrid">
        <label>Colaborador *
          <select name="usuario_id" id="hol-user-sel" required>
            <option value="">Selecione o colaborador</option>
            ${staffUsers.map((u) => `<option value="${u.id}" data-sal="${u.salario_base || 0}">${esc(u.nome)} (${esc(u.cargo || u.perfil)})</option>`).join('')}
          </select>
        </label>
        <label>Competência (Mês/Ano) *
          <input type="text" name="competencia" value="${defaultComp}" placeholder="Ex.: 11/2026" required>
        </label>
        <label>Tipo de Folha *
          <select name="tipo">
            <option value="Salário Mensal">Salário Mensal</option>
            <option value="Adiantamento">Adiantamento Salarial</option>
            <option value="13º Salário">13º Salário</option>
            <option value="Férias">Férias</option>
            <option value="Bônus / PLR">Bônus / PLR</option>
          </select>
        </label>
        <label>Data de Pagamento
          <input type="date" name="data_pagamento" value="${todayStr}">
        </label>
        <label>Salário Base (R$) *
          <input type="number" step="0.01" name="salario_base" id="hol-base" value="0.00" required>
        </label>
        <label>Proventos / Adicionais (R$)
          <input type="number" step="0.01" name="proventos" id="hol-prov" value="0.00">
        </label>
        <label>Descrição dos Proventos
          <input type="text" name="descricao_proventos" placeholder="Ex.: Comissões, Horas Extras, Benefícios">
        </label>
        <label>Descontos (R$)
          <input type="number" step="0.01" name="descontos" id="hol-desc" value="0.00">
        </label>
        <label>Descrição dos Descontos
          <input type="text" name="descricao_descontos" placeholder="Ex.: INSS, IRRF, Vale Transporte">
        </label>
        <label>Base FGTS (R$)
          <input type="number" step="0.01" name="fgts_valor" value="0.00">
        </label>
        <label>Valor Líquido a Receber (R$) *
          <input type="number" step="0.01" name="valor_liquido" id="hol-liq" value="0.00" required style="font-weight:700; color:var(--primary);">
        </label>
        <label>Status do Pagamento
          <select name="status">
            <option value="pago">Pago</option>
            <option value="programado">Programado</option>
            <option value="pendente">Pendente</option>
          </select>
        </label>
      </div>
      <div style="margin-top:14px; display:flex; flex-direction:column; gap:12px;">
        <label class="field-full">Anexar Holerite / Comprovante (PDF ou Imagem)
          <input type="file" id="hol-file" accept=".pdf,.png,.jpg,.jpeg">
        </label>
        <label class="field-full">Observações
          <textarea name="observacoes" rows="2" placeholder="Informações complementares do demonstrativo..."></textarea>
        </label>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
        <button type="submit" class="btn" id="hol-save-btn">Publicar Holerite</button>
      </div>
    </form>
  `;

  const recalc = () => {
    const b = parseFloat(document.getElementById('hol-base').value) || 0;
    const p = parseFloat(document.getElementById('hol-prov').value) || 0;
    const d = parseFloat(document.getElementById('hol-desc').value) || 0;
    document.getElementById('hol-liq').value = Math.max(0, b + p - d).toFixed(2);
  };

  document.getElementById('hol-user-sel').onchange = (e) => {
    const opt = e.target.selectedOptions[0];
    if (opt && opt.dataset.sal) {
      document.getElementById('hol-base').value = Number(opt.dataset.sal).toFixed(2);
      recalc();
    }
  };
  ['hol-base', 'hol-prov', 'hol-desc'].forEach((id) => {
    document.getElementById(id).addEventListener('input', recalc);
  });

  document.getElementById('new-holerite-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('hol-save-btn');
    const raw = Object.fromEntries(new FormData(e.target));
    const fileInput = document.getElementById('hol-file');

    btn.disabled = true;
    btn.textContent = 'Publicando...';
    try {
      let anexo_nome = null;
      let anexo_data = null;
      if (fileInput?.files?.[0]) {
        const f = fileInput.files[0];
        if (f.size > 3 * 1024 * 1024) throw new Error('O arquivo anexo deve ter no máximo 3 MB.');
        anexo_nome = f.name;
        anexo_data = await readFileAsDataUrl(f);
      }

      await apiRequest('/holerites', {
        method: 'POST',
        body: JSON.stringify({
          usuario_id: Number(raw.usuario_id),
          competencia: raw.competencia.trim(),
          tipo: raw.tipo,
          salario_base: Number(raw.salario_base || 0),
          proventos: Number(raw.proventos || 0),
          descricao_proventos: raw.descricao_proventos || null,
          descontos: Number(raw.descontos || 0),
          descricao_descontos: raw.descricao_descontos || null,
          valor_liquido: Number(raw.valor_liquido || 0),
          fgts_valor: Number(raw.fgts_valor || 0),
          data_pagamento: raw.data_pagamento || null,
          status: raw.status,
          observacoes: raw.observacoes || null,
          anexo_nome,
          anexo_data
        })
      });

      holeriteDialog.close();
      invalidateCache();
      showToast('Holerite publicado com sucesso.', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Falha ao publicar holerite', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Publicar Holerite';
    }
  };

  holeriteDialog.showModal();
};

window.nexusOpenNewInformeModal = async () => {
  await preloadRefs();
  const staffUsers = (cache.usuarios || []).filter((u) => u.perfil !== 'cliente');
  const prevYear = String(new Date().getFullYear() - 1);
  const currYear = String(new Date().getFullYear());

  holeriteContainer.innerHTML = `
    <form id="new-informe-form">
      <div class="modal-header">
        <h2>Publicar Informe de Rendimentos (IRRF)</h2>
        <button type="button" class="btn secondary icon-only" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
      </div>
      <div class="formgrid">
        <label>Colaborador *
          <select name="usuario_id" required>
            <option value="">Selecione o colaborador</option>
            ${staffUsers.map((u) => `<option value="${u.id}">${esc(u.nome)} (${esc(u.cpf || u.email)})</option>`).join('')}
          </select>
        </label>
        <label>Ano-Calendário *
          <input type="text" name="ano_calendario" value="${prevYear}" required>
        </label>
        <label>Ano-Exercício *
          <input type="text" name="ano_exercicio" value="${currYear}" required>
        </label>
        <label>Rendimentos Tributáveis (R$) *
          <input type="number" step="0.01" name="rendimentos_tributaveis" value="0.00" required>
        </label>
        <label>Contribuição Previdenciária Oficial (R$)
          <input type="number" step="0.01" name="contribuicao_previdenciaria" value="0.00">
        </label>
        <label>Imposto de Renda Retido na Fonte - IRRF (R$)
          <input type="number" step="0.01" name="irrf_retido" value="0.00">
        </label>
        <label>13º Salário Líquido (R$)
          <input type="number" step="0.01" name="decimo_terceiro" value="0.00">
        </label>
        <label>Rendimentos Isentos e Não Tributáveis (R$)
          <input type="number" step="0.01" name="rendimentos_isentos" value="0.00">
        </label>
      </div>
      <div style="margin-top:14px; display:flex; flex-direction:column; gap:12px;">
        <label class="field-full">Anexar Documento Oficial (PDF)
          <input type="file" id="inf-file" accept=".pdf,.png,.jpg,.jpeg">
        </label>
        <label class="field-full">Observações
          <textarea name="observacoes" rows="2"></textarea>
        </label>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
        <button type="submit" class="btn" id="inf-save-btn">Publicar Informe</button>
      </div>
    </form>
  `;

  document.getElementById('new-informe-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('inf-save-btn');
    const raw = Object.fromEntries(new FormData(e.target));
    const fileInput = document.getElementById('inf-file');

    btn.disabled = true;
    btn.textContent = 'Publicando...';
    try {
      let anexo_nome = null;
      let anexo_data = null;
      if (fileInput?.files?.[0]) {
        const f = fileInput.files[0];
        if (f.size > 3 * 1024 * 1024) throw new Error('O arquivo PDF deve ter no máximo 3 MB.');
        anexo_nome = f.name;
        anexo_data = await readFileAsDataUrl(f);
      }

      await apiRequest('/informes-rendimentos', {
        method: 'POST',
        body: JSON.stringify({
          usuario_id: Number(raw.usuario_id),
          ano_calendario: raw.ano_calendario.trim(),
          ano_exercicio: raw.ano_exercicio.trim(),
          rendimentos_tributaveis: Number(raw.rendimentos_tributaveis || 0),
          contribuicao_previdenciaria: Number(raw.contribuicao_previdenciaria || 0),
          irrf_retido: Number(raw.irrf_retido || 0),
          decimo_terceiro: Number(raw.decimo_terceiro || 0),
          rendimentos_isentos: Number(raw.rendimentos_isentos || 0),
          observacoes: raw.observacoes || null,
          anexo_nome,
          anexo_data
        })
      });

      holeriteDialog.close();
      invalidateCache();
      holeriteTab = 'informes';
      showToast('Informe de rendimentos publicado com sucesso.', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Falha ao publicar informe', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Publicar Informe';
    }
  };

  holeriteDialog.showModal();
};

window.nexusViewHolerite = (id) => {
  const h = (cache.holerites || []).find((x) => x.id === id);
  if (!h) return;
  const emp = (cache.usuarios || []).find((u) => u.id === h.usuario_id) || user;

  holeriteContainer.innerHTML = `
    <div class="modal-header">
      <h2>Demonstrativo de Pagamento — ${esc(h.competencia)}</h2>
      <button type="button" class="btn secondary icon-only" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
    </div>

    <div id="holerite-printable" class="holerite-slip">
      <div class="holerite-slip-header">
        <div>
          <div style="font-size:18px; font-weight:800;">NEXUS CODE TECNOLOGIA LTDA</div>
          <div style="font-size:12px; color:#475569;">Aracruz - ES • contato@nexuscodebrasil.com.br</div>
        </div>
        <div style="text-align:right;">
          <div style="font-weight:800; font-size:14px;">RECIBO DE PAGAMENTO</div>
          <div style="font-size:12px; color:#475569;">Competência: <b>${esc(h.competencia)}</b> • ${esc(h.tipo)}</div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:12.5px; margin-bottom:12px;">
        <div><b>Colaborador:</b> ${esc(emp?.nome || '-')}</div>
        <div><b>CPF:</b> ${esc(emp?.cpf || 'Não informado')}</div>
        <div><b>Cargo / Função:</b> ${esc(emp?.cargo || 'Colaborador')}</div>
        <div><b>Admissão:</b> ${formatDate(emp?.data_contratacao || emp?.criado_em)}</div>
      </div>

      <table class="holerite-slip-table">
        <thead>
          <tr>
            <th>Código</th>
            <th>Descrição</th>
            <th>Proventos</th>
            <th>Descontos</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>001</td>
            <td>Salário Base (${esc(h.tipo)})</td>
            <td style="color:#15803d; font-weight:600;">${formatMoney(h.salario_base)}</td>
            <td>-</td>
          </tr>
          ${Number(h.proventos) > 0 ? `
            <tr>
              <td>002</td>
              <td>${esc(h.descricao_proventos || 'Adicionais / Comissões')}</td>
              <td style="color:#15803d; font-weight:600;">${formatMoney(h.proventos)}</td>
              <td>-</td>
            </tr>
          ` : ''}
          ${Number(h.descontos) > 0 ? `
            <tr>
              <td>101</td>
              <td>${esc(h.descricao_descontos || 'Descontos Legais (INSS / IRRF)')}</td>
              <td>-</td>
              <td style="color:#dc2626; font-weight:600;">${formatMoney(h.descontos)}</td>
            </tr>
          ` : ''}
        </tbody>
        <tfoot>
          <tr style="background:#f8fafc; font-weight:700;">
            <td colspan="2">TOTAIS</td>
            <td style="color:#15803d;">${formatMoney(Number(h.salario_base) + Number(h.proventos))}</td>
            <td style="color:#dc2626;">${formatMoney(h.descontos)}</td>
          </tr>
          <tr style="background:#eff6ff; font-weight:800; font-size:14px;">
            <td colspan="3" style="text-align:right;">VALOR LÍQUIDO A RECEBER:</td>
            <td style="color:#1d4ed8;">${formatMoney(h.valor_liquido)}</td>
          </tr>
        </tfoot>
      </table>

      <div style="display:flex; justify-content:space-between; font-size:12px; color:#475569; margin-top:10px;">
        <span>Base FGTS do Mês: <b>${formatMoney(h.fgts_valor)}</b></span>
        <span>Data do Crédito: <b>${formatDate(h.data_pagamento)}</b> (${esc(h.status).toUpperCase()})</span>
      </div>
      ${h.observacoes ? `<div style="margin-top:10px; font-size:12px; color:#475569;"><b>Observações:</b> ${esc(h.observacoes)}</div>` : ''}
    </div>

    <div class="modal-footer">
      ${h.anexo_data ? `<a href="${h.anexo_data}" download="${esc(h.anexo_nome || 'holerite.pdf')}" class="btn secondary" style="text-decoration:none;">Baixar Comprovante Anexo</a>` : ''}
      <button type="button" class="btn secondary" onclick="window.print()">Imprimir / Salvar PDF</button>
      <button type="button" class="btn" onclick="document.getElementById('holerite-dialog').close()">Fechar</button>
    </div>
  `;
  holeriteDialog.showModal();
};

window.nexusViewInforme = (id) => {
  const inf = (cache.informes || []).find((x) => x.id === id);
  if (!inf) return;
  const emp = (cache.usuarios || []).find((u) => u.id === inf.usuario_id) || user;

  holeriteContainer.innerHTML = `
    <div class="modal-header">
      <h2>Comprovante de Rendimentos — Ano-Calendário ${esc(inf.ano_calendario)}</h2>
      <button type="button" class="btn secondary icon-only" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
    </div>

    <div id="holerite-printable" class="holerite-slip">
      <div class="holerite-slip-header">
        <div>
          <div style="font-size:17px; font-weight:800;">COMPROVANTE DE RENDIMENTOS PAGOS E DE IRRF</div>
          <div style="font-size:12px; color:#475569;">Fonte Pagadora: NEXUS CODE TECNOLOGIA LTDA</div>
        </div>
        <div style="text-align:right;">
          <div style="font-weight:800;">Ano-Calendário: ${esc(inf.ano_calendario)}</div>
          <div style="font-size:12px; color:#475569;">Exercício: ${esc(inf.ano_exercicio)}</div>
        </div>
      </div>

      <div style="font-size:12.5px; margin-bottom:12px;">
        <b>Beneficiário:</b> ${esc(emp?.nome || '-')} • <b>CPF:</b> ${esc(emp?.cpf || 'Não informado')}
      </div>

      <table class="holerite-slip-table">
        <thead>
          <tr><th>Discriminação dos Rendimentos e Imposto Retido</th><th style="width:180px;">Valor (R$)</th></tr>
        </thead>
        <tbody>
          <tr><td>1. Total dos Rendimentos Tributáveis (inclusive férias)</td><td><b>${formatMoney(inf.rendimentos_tributaveis)}</b></td></tr>
          <tr><td>2. Contribuição Previdenciária Oficial (INSS)</td><td>${formatMoney(inf.contribuicao_previdenciaria)}</td></tr>
          <tr><td>3. Imposto sobre a Renda Retido na Fonte (IRRF)</td><td><b>${formatMoney(inf.irrf_retido)}</b></td></tr>
          <tr><td>4. Décimo Terceiro Salário (Tributação Exclusiva)</td><td>${formatMoney(inf.decimo_terceiro)}</td></tr>
          <tr><td>5. Rendimentos Isentos e Não Tributáveis</td><td>${formatMoney(inf.rendimentos_isentos)}</td></tr>
        </tbody>
      </table>
      ${inf.observacoes ? `<div style="margin-top:10px; font-size:12px; color:#475569;"><b>Informações Complementares:</b> ${esc(inf.observacoes)}</div>` : ''}
    </div>

    <div class="modal-footer">
      ${inf.anexo_data ? `<a href="${inf.anexo_data}" download="${esc(inf.anexo_nome || 'informe_rendimentos.pdf')}" class="btn secondary" style="text-decoration:none;">Baixar PDF Oficial</a>` : ''}
      <button type="button" class="btn secondary" onclick="window.print()">Imprimir / Salvar PDF</button>
      <button type="button" class="btn" onclick="document.getElementById('holerite-dialog').close()">Fechar</button>
    </div>
  `;
  holeriteDialog.showModal();
};

// ==================== QUADRO KANBAN ESTILO MICROSOFT PLANNER (MS365) & FUNIL ====================
async function renderKanban(isPipeline = false, useCache = false) {
  await preloadRefs();
  if (isPipeline) {
    if (!useCache || !cache.clientes.length) {
      cache.clientes = await apiRequest('/clientes');
    }
    const clientes = cache.clientes.filter((c) =>
      matchSearch([c.nome_empresa, c.contato_nome, c.email, c.origem, c.status_funil])
    );
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

  if (!useCache || !cache.tarefas.length) {
    cache.tarefas = await apiRequest('/tarefas');
  }
  const projMap = Object.fromEntries((cache.projetos || []).map((p) => [p.id, p.titulo]));
  const userMap = Object.fromEntries((cache.usuarios || []).map((u) => [u.id, u.nome]));
  const todayStr = new Date().toISOString().slice(0, 10);

  const tarefas = cache.tarefas.filter((t) =>
    matchSearch([t.titulo, t.descricao, projMap[t.projeto_id], userMap[t.responsavel_id], t.status, t.prioridade])
  );

  const buckets = [
    { key: 'pendente', label: 'A Fazer', color: '#64748b' },
    { key: 'fazendo', label: 'Em Andamento', color: '#2563eb' },
    { key: 'revisao', label: 'Homologação', color: '#f59e0b' },
    { key: 'concluida', label: 'Concluída', color: '#16a34a' }
  ];

  return `
    <div class="toolbar">
      <div>
        <h1>Quadro Planner</h1>
        <span class="muted">Clique em qualquer cartão para editar textos, checklist, prazos, status e anexar documentos</span>
      </div>
      <button class="btn" onclick="window.nexusOpenNewPlannerTask('pendente')">${ICONS.plus}<span>Nova Tarefa</span></button>
    </div>

    <div class="planner-board">
      ${buckets.map((col) => {
        const colTasks = tarefas.filter((t) => t.status === col.key);
        return `
          <section class="planner-bucket" data-drop-col="${col.key}" data-drop-type="task">
            <div class="planner-bucket-bar" style="background:${col.color};"></div>
            <div class="planner-bucket-head">
              <b style="font-size:14px;">${col.label}</b>
              <span class="filter-count">${colTasks.length}</span>
            </div>
            <div class="planner-bucket-body">
              <button type="button" class="planner-add-inline" onclick="window.nexusOpenNewPlannerTask('${col.key}')">
                ${ICONS.plus}<span>Adicionar tarefa</span>
              </button>

              ${colTasks.map((t) => {
                const checklist = safeParseJsonArray(t.checklist_json);
                const doneChecks = checklist.filter((c) => c.concluido).length;
                const anexos = safeParseJsonArray(t.anexos_json);
                const isDone = t.status === 'concluida';
                const isOverdue = !isDone && t.prazo && String(t.prazo).slice(0, 10) < todayStr;
                const respName = userMap[t.responsavel_id] || 'Não atribuído';

                return `
                  <div class="planner-card ${isDone ? 'completed' : ''}" draggable="true" data-drag-id="${t.id}" data-drag-type="task" onclick="window.nexusOpenPlannerTask(${t.id})">
                    <div class="planner-card-top">
                      <span class="planner-project-tag" title="${esc(projMap[t.projeto_id] || '')}">${esc(projMap[t.projeto_id] || 'Projeto #' + t.projeto_id)}</span>
                      <span class="prio-badge prio-${esc(t.prioridade || 'media')}">${esc(t.prioridade || 'media')}</span>
                    </div>

                    <div class="planner-title-row">
                      <button type="button" class="planner-check-circle ${isDone ? 'checked' : ''}" title="${isDone ? 'Reabrir tarefa' : 'Concluir tarefa'}" onclick="event.stopPropagation(); window.nexusTogglePlannerComplete(${t.id})">
                        ${isDone ? '✓' : ''}
                      </button>
                      <div class="planner-card-title">${esc(t.titulo)}</div>
                    </div>

                    ${t.descricao ? `<div class="planner-card-desc">${esc(t.descricao)}</div>` : ''}

                    <div class="planner-meta-chips">
                      ${t.prazo ? `<span class="planner-chip ${isOverdue ? 'overdue' : isDone ? 'done' : ''}">${ICONS.calendar} ${formatDate(t.prazo)}</span>` : ''}
                      ${checklist.length ? `<span class="planner-chip ${doneChecks === checklist.length ? 'done' : ''}">☑ ${doneChecks}/${checklist.length}</span>` : ''}
                      ${anexos.length ? `<span class="planner-chip">${ICONS.paperclip} ${anexos.length} doc(s)</span>` : ''}
                    </div>

                    <div class="planner-card-footer">
                      <div class="planner-assignee">
                        <div class="row-avatar" style="width:24px; height:24px; font-size:10px;">${initials(respName)}</div>
                        <span>${esc(respName)}</span>
                      </div>
                      <div style="display:flex; gap:4px;" onclick="event.stopPropagation();">
                        ${buckets.filter((b) => b.key !== col.key).slice(0, 2).map((b) => `
                          <button type="button" class="btn secondary" style="padding:3px 7px; font-size:10.5px;" data-move-task="${t.id}:${b.key}" title="Mover para ${b.label}">${ICONS.arrowRight}</button>
                        `).join('')}
                      </div>
                    </div>
                  </div>
                `;
              }).join('') || '<p class="muted" style="font-size:12px; text-align:center; margin-top:8px;">Nenhuma tarefa neste bucket</p>'}
            </div>
          </section>
        `;
      }).join('')}
    </div>`;
}

window.nexusTogglePlannerComplete = async (taskId) => {
  const t = (cache.tarefas || []).find((x) => x.id === taskId);
  if (!t) return;
  const nextStatus = t.status === 'concluida' ? 'pendente' : 'concluida';
  try {
    await apiRequest(`/tarefas/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: nextStatus })
    });
    invalidateCache();
    showToast(nextStatus === 'concluida' ? 'Tarefa concluída!' : 'Tarefa reaberta.', 'success');
    render();
  } catch (err) {
    showNoticeModal({ title: 'Erro ao atualizar status', message: err.message, variant: 'error' });
  }
};

window.nexusOpenNewPlannerTask = async (defaultBucket = 'pendente') => {
  await preloadRefs();
  const firstProjId = cache.projetos?.[0]?.id;
  if (!firstProjId) {
    showNoticeModal({
      title: 'Cadastre um Projeto Primeiro',
      message: 'Para criar tarefas no Planner, é necessário ter ao menos um projeto ativo cadastrado.',
      variant: 'warning'
    });
    return;
  }
  openPlannerModal({
    id: null,
    projeto_id: firstProjId,
    responsavel_id: user?.id || null,
    titulo: '',
    descricao: '',
    status: defaultBucket,
    prioridade: 'media',
    data_inicio: new Date().toISOString().slice(0, 10),
    prazo: '',
    checklist_json: '[]',
    anexos_json: '[]',
    comentarios_json: '[]'
  });
};

window.nexusOpenPlannerTask = async (taskId) => {
  await preloadRefs();
  if (!cache.tarefas.length) {
    cache.tarefas = await apiRequest('/tarefas');
  }
  const t = cache.tarefas.find((x) => x.id === taskId);
  if (t) openPlannerModal(t);
};

function openPlannerModal(taskObj) {
  const isNew = !taskObj.id;
  let checklist = safeParseJsonArray(taskObj.checklist_json);
  let anexos = safeParseJsonArray(taskObj.anexos_json);
  let comentarios = safeParseJsonArray(taskObj.comentarios_json);

  const projectOptions = (cache.projetos || [])
    .map((p) => `<option value="${p.id}" ${Number(taskObj.projeto_id) === p.id ? 'selected' : ''}>${esc(p.titulo)}</option>`)
    .join('');
  const userOptions = `<option value="">-- Não atribuído --</option>` + (cache.usuarios || [])
    .filter((u) => u.perfil !== 'cliente')
    .map((u) => `<option value="${u.id}" ${Number(taskObj.responsavel_id) === u.id ? 'selected' : ''}>${esc(u.nome)}</option>`)
    .join('');

  plannerContainer.innerHTML = `
    <form id="planner-detail-form">
      <div class="modal-header">
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
          <span class="badge ${esc(taskObj.status)}">${isNew ? 'Nova Tarefa Planner' : `Tarefa #${taskObj.id}`}</span>
          <span class="prio-badge prio-${esc(taskObj.prioridade || 'media')}">${esc(taskObj.prioridade || 'media')}</span>
        </div>
        <button type="button" class="btn secondary icon-only" onclick="document.getElementById('planner-dialog').close()">&times;</button>
      </div>

      <div style="margin-bottom:16px;">
        <label class="field-full">Título da Tarefa *
          <input type="text" name="titulo" value="${esc(taskObj.titulo || '')}" required placeholder="Digite o título da tarefa..." class="nc-input" style="font-size:16px; font-weight:700;">
        </label>
      </div>

      <div class="planner-modal-grid">
        <!-- Coluna Principal: Textos, Checklist e Anexos -->
        <div>
          <div class="planner-box">
            <label class="field-full">Anotações &amp; Descrição Detalhada
              <textarea name="descricao" rows="4" placeholder="Descreva o escopo, instruções técnicas, critérios de entrega ou observações..." class="nc-input">${esc(taskObj.descricao || '')}</textarea>
            </label>
          </div>

          <div class="planner-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <b style="font-size:13.5px;">Checklist de Execução</b>
              <span id="planner-check-progress" class="muted" style="font-size:12px;"></span>
            </div>
            <div id="planner-checklist-list"></div>
            <div style="display:flex; gap:8px; margin-top:8px;">
              <input type="text" id="planner-new-check-input" placeholder="Adicionar item ao checklist..." class="nc-input" style="height:36px;">
              <button type="button" id="planner-add-check-btn" class="btn secondary" style="padding:0 14px; height:36px;">Adicionar</button>
            </div>
          </div>

          <div class="planner-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <b style="font-size:13.5px;">Documentos &amp; Anexos</b>
              <label class="btn secondary" style="padding:5px 10px; font-size:12px; cursor:pointer; margin:0;">
                ${ICONS.paperclip}<span>Anexar Arquivo</span>
                <input type="file" id="planner-file-input" multiple style="display:none;">
              </label>
            </div>
            <div id="planner-attachments-list"></div>
            <div style="display:flex; gap:8px; margin-top:8px;">
              <input type="url" id="planner-link-input" placeholder="Ou cole o link de um documento (SharePoint, Drive, Figma...)" class="nc-input" style="height:36px;">
              <button type="button" id="planner-add-link-btn" class="btn secondary" style="padding:0 12px; height:36px;">Vincular</button>
            </div>
          </div>
        </div>

        <!-- Coluna Lateral: Status, Bucket, Prioridade, Datas e Comentários -->
        <div>
          <div class="planner-box" style="display:flex; flex-direction:column; gap:12px;">
            <label class="field-full">Bucket / Status *
              <select name="status" class="nc-input">
                <option value="pendente" ${taskObj.status === 'pendente' ? 'selected' : ''}>A Fazer (Pendente)</option>
                <option value="fazendo" ${taskObj.status === 'fazendo' ? 'selected' : ''}>Em Andamento</option>
                <option value="revisao" ${taskObj.status === 'revisao' ? 'selected' : ''}>Homologação / Revisão</option>
                <option value="concluida" ${taskObj.status === 'concluida' ? 'selected' : ''}>Concluída</option>
              </select>
            </label>

            <label class="field-full">Prioridade
              <select name="prioridade" class="nc-input">
                <option value="baixa" ${(taskObj.prioridade || 'media') === 'baixa' ? 'selected' : ''}>Baixa</option>
                <option value="media" ${(taskObj.prioridade || 'media') === 'media' ? 'selected' : ''}>Média</option>
                <option value="alta" ${(taskObj.prioridade || 'media') === 'alta' ? 'selected' : ''}>Alta</option>
                <option value="urgente" ${(taskObj.prioridade || 'media') === 'urgente' ? 'selected' : ''}>Urgente</option>
              </select>
            </label>

            <label class="field-full">Projeto Vinculado *
              <select name="projeto_id" required class="nc-input">${projectOptions}</select>
            </label>

            <label class="field-full">Responsável
              <select name="responsavel_id" class="nc-input">${userOptions}</select>
            </label>

            <div class="profile-grid">
              <label class="field-full">Data de Início
                <input type="date" name="data_inicio" value="${taskObj.data_inicio ? String(taskObj.data_inicio).slice(0, 10) : ''}" class="nc-input">
              </label>
              <label class="field-full">Prazo (Entrega)
                <input type="date" name="prazo" value="${taskObj.prazo ? String(taskObj.prazo).slice(0, 10) : ''}" class="nc-input">
              </label>
            </div>
          </div>

          <div class="planner-box">
            <b style="font-size:13.5px; display:block; margin-bottom:8px;">Comentários &amp; Atualizações</b>
            <div id="planner-comments-list" style="max-height:170px; overflow-y:auto; display:flex; flex-direction:column; gap:6px; margin-bottom:8px;"></div>
            <div style="display:flex; gap:6px;">
              <input type="text" id="planner-comment-input" placeholder="Escreva um comentário..." class="nc-input" style="height:36px;">
              <button type="button" id="planner-add-comment-btn" class="btn secondary" style="padding:0 12px; height:36px;">Enviar</button>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer" style="justify-content:space-between;">
        <div>
          ${!isNew ? `<button type="button" class="btn danger" id="planner-delete-btn">Excluir Tarefa</button>` : ''}
        </div>
        <div style="display:flex; gap:10px;">
          <button type="button" class="btn secondary" onclick="document.getElementById('planner-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="planner-save-btn">${isNew ? 'Criar Tarefa' : 'Salvar Alterações'}</button>
        </div>
      </div>
    </form>
  `;

  function renderChecklistUI() {
    const listEl = document.getElementById('planner-checklist-list');
    const progEl = document.getElementById('planner-check-progress');
    const doneCount = checklist.filter((c) => c.concluido).length;
    progEl.textContent = checklist.length ? `${doneCount} de ${checklist.length} concluído(s)` : 'Nenhum item';

    listEl.innerHTML = checklist.map((item, idx) => `
      <div class="planner-checklist-item ${item.concluido ? 'checked' : ''}">
        <input type="checkbox" ${item.concluido ? 'checked' : ''} data-chk-idx="${idx}" style="width:16px; height:16px; accent-color:var(--ok);">
        <span style="flex:1; font-size:13px;">${esc(item.texto)}</span>
        <button type="button" data-chk-del="${idx}" style="background:none; border:0; color:var(--danger); cursor:pointer; font-weight:700;">&times;</button>
      </div>
    `).join('');

    listEl.querySelectorAll('[data-chk-idx]').forEach((cb) => {
      cb.onchange = () => {
        const i = Number(cb.dataset.chkIdx);
        checklist[i].concluido = cb.checked;
        renderChecklistUI();
      };
    });
    listEl.querySelectorAll('[data-chk-del]').forEach((btn) => {
      btn.onclick = () => {
        checklist.splice(Number(btn.dataset.chkDel), 1);
        renderChecklistUI();
      };
    });
  }

  function renderAttachmentsUI() {
    const listEl = document.getElementById('planner-attachments-list');
    if (!anexos.length) {
      listEl.innerHTML = '<div class="muted" style="font-size:12px;">Nenhum documento anexado a esta tarefa.</div>';
      return;
    }
    listEl.innerHTML = anexos.map((a, idx) => `
      <div class="planner-attachment-row">
        <div style="min-width:0; flex:1;">
          <div style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(a.nome)}</div>
          <div class="muted" style="font-size:11px;">${esc(a.tamanho || 'Link externo')} • ${esc(a.adicionado_por || 'Equipe')}</div>
        </div>
        <div style="display:flex; gap:6px; align-items:center;">
          ${a.data_url ? `<a href="${a.data_url}" download="${esc(a.nome)}" class="btn secondary" style="padding:4px 8px; font-size:11px; text-decoration:none;">Baixar</a>` : ''}
          ${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener" class="btn secondary" style="padding:4px 8px; font-size:11px; text-decoration:none;">Abrir</a>` : ''}
          <button type="button" data-att-del="${idx}" style="background:none; border:0; color:var(--danger); cursor:pointer; font-weight:700; font-size:16px;">&times;</button>
        </div>
      </div>
    `).join('');

    listEl.querySelectorAll('[data-att-del]').forEach((btn) => {
      btn.onclick = () => {
        anexos.splice(Number(btn.dataset.attDel), 1);
        renderAttachmentsUI();
      };
    });
  }

  function renderCommentsUI() {
    const listEl = document.getElementById('planner-comments-list');
    if (!comentarios.length) {
      listEl.innerHTML = '<div class="muted" style="font-size:12px;">Sem comentários registrados.</div>';
      return;
    }
    listEl.innerHTML = comentarios.map((c) => `
      <div style="background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:12.5px;">
        <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-light); margin-bottom:2px;">
          <b>${esc(c.autor)}</b>
          <span>${esc(c.criado_em)}</span>
        </div>
        <div>${esc(c.texto)}</div>
      </div>
    `).join('');
  }

  renderChecklistUI();
  renderAttachmentsUI();
  renderCommentsUI();

  document.getElementById('planner-add-check-btn').onclick = () => {
    const inp = document.getElementById('planner-new-check-input');
    const txt = inp.value.trim();
    if (!txt) return;
    checklist.push({ id: Date.now(), texto: txt, concluido: false });
    inp.value = '';
    renderChecklistUI();
  };

  document.getElementById('planner-file-input').onchange = async (e) => {
    const files = [...(e.target.files || [])];
    for (const f of files) {
      if (f.size > 2.5 * 1024 * 1024) {
        showToast(`Arquivo "${f.name}" excede 2,5 MB.`, 'error');
        continue;
      }
      const dataUrl = await readFileAsDataUrl(f);
      anexos.push({
        id: Date.now() + Math.random(),
        nome: f.name,
        tamanho: `${Math.max(1, Math.round(f.size / 1024))} KB`,
        data_url: dataUrl,
        adicionado_por: user?.nome || 'Usuário'
      });
    }
    e.target.value = '';
    renderAttachmentsUI();
  };

  document.getElementById('planner-add-link-btn').onclick = () => {
    const inp = document.getElementById('planner-link-input');
    const url = inp.value.trim();
    if (!url) return;
    anexos.push({
      id: Date.now(),
      nome: url.replace(/^https?:\/\//, '').slice(0, 48),
      tamanho: 'Link externo',
      url,
      adicionado_por: user?.nome || 'Usuário'
    });
    inp.value = '';
    renderAttachmentsUI();
  };

  document.getElementById('planner-add-comment-btn').onclick = () => {
    const inp = document.getElementById('planner-comment-input');
    const txt = inp.value.trim();
    if (!txt) return;
    comentarios.push({
      id: Date.now(),
      autor: user?.nome || 'Usuário',
      texto: txt,
      criado_em: new Date().toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
    });
    inp.value = '';
    renderCommentsUI();
  };

  if (!isNew) {
    document.getElementById('planner-delete-btn').onclick = () => {
      plannerDialog.close();
      showConfirmModal({
        title: 'Excluir Tarefa do Planner',
        message: `Deseja excluir permanentemente a tarefa "${taskObj.titulo}"?`,
        confirmText: 'Excluir Tarefa',
        variant: 'danger',
        onConfirm: async () => {
          await apiRequest(`/tarefas/${taskObj.id}`, { method: 'DELETE' });
          invalidateCache();
          showToast('Tarefa excluída com sucesso.', 'success');
          await render();
        }
      });
    };
  }

  document.getElementById('planner-detail-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('planner-save-btn');
    const raw = Object.fromEntries(new FormData(e.target));

    btn.disabled = true;
    btn.textContent = 'Salvando...';
    try {
      const payload = {
        titulo: raw.titulo.trim(),
        projeto_id: Number(raw.projeto_id),
        responsavel_id: raw.responsavel_id ? Number(raw.responsavel_id) : null,
        status: raw.status,
        prioridade: raw.prioridade,
        data_inicio: raw.data_inicio || null,
        prazo: raw.prazo || null,
        descricao: raw.descricao ? raw.descricao.trim() : null,
        checklist_json: JSON.stringify(checklist),
        anexos_json: JSON.stringify(anexos),
        comentarios_json: JSON.stringify(comentarios)
      };

      await apiRequest(isNew ? '/tarefas' : `/tarefas/${taskObj.id}`, {
        method: isNew ? 'POST' : 'PATCH',
        body: JSON.stringify(payload)
      });

      plannerDialog.close();
      invalidateCache();
      showToast(isNew ? 'Tarefa criada no Planner!' : 'Tarefa atualizada com sucesso!', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro ao salvar tarefa', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = isNew ? 'Criar Tarefa' : 'Salvar Alterações';
    }
  };

  plannerDialog.showModal();
}

async function renderAudit(useCache = false) {
  const logs = await apiRequest('/auditoria');
  const filtered = logs.filter((l) => matchSearch([l.usuario_nome, l.acao, l.detalhes]));
  return `
    <div class="toolbar"><div><h1>Logs de Auditoria</h1><span class="muted">Histórico de movimentações e segurança operacional</span></div></div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Data / Hora</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead>
        <tbody>${filtered.map((l) => `<tr><td>${new Date(l.criado_em).toLocaleString('pt-BR')}</td><td><b>${esc(l.usuario_nome)}</b></td><td><span class="badge">${esc(l.acao)}</span></td><td>${esc(l.detalhes)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Nenhum registro encontrado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderProfile() {
  const me = await apiRequest('/auth/me');
  const consentInfo = me.termos_aceitos_em
    ? `Consentimento LGPD registrado em ${formatDateTime(me.termos_aceitos_em)}.`
    : 'Pendente de confirmação de consentimento LGPD.';

  return `
    ${renderGlobalSearchBanner()}
    <form id="profile-form" class="profile-shell">
      <div class="card profile-header-card">
        <div class="row-entity">
          <div class="row-avatar" style="width:48px; height:48px; font-size:17px;">${initials(me.nome)}</div>
          <div>
            <h3 style="margin:0 0 3px; font-size:18px;">${esc(me.nome)}</h3>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
              <span class="muted">${esc(me.email)}</span>
              ${me.cargo ? `<span class="badge">${esc(me.cargo)}</span>` : ''}
              <span class="badge ativo">${esc(me.perfil)}</span>
            </div>
          </div>
        </div>
        <div style="font-size:12px; color:var(--text-light);">
          Contratação / Cadastro: <b>${formatDate(me.data_contratacao || me.criado_em)}</b>
        </div>
      </div>

      <div class="profile-columns">
        <!-- Coluna Esquerda: Identificação, Endereço e Segurança -->
        <div class="card profile-col-card">
          <div>
            <h4 class="profile-section-title">1. Identificação &amp; Dados Pessoais</h4>
            <p class="profile-section-sub">Informações cadastrais básicas do titular da conta.</p>
            <div class="profile-grid" style="margin-bottom:12px;">
              <label class="field-full">Nome Completo *
                <input type="text" name="nome" value="${esc(me.nome)}" required class="nc-input">
              </label>
              <label class="field-full">E-mail de Acesso
                <input type="email" value="${esc(me.email)}" readonly class="nc-input">
              </label>
            </div>
            <div class="profile-grid-personal">
              <label class="field-full">CPF
                <input type="text" name="cpf" id="prof-cpf" value="${esc(me.cpf || '')}" maxlength="14" placeholder="000.000.000-00" class="nc-input">
              </label>
              <label class="field-full">Data de Nascimento
                <input type="date" name="data_nascimento" value="${me.data_nascimento || ''}" class="nc-input">
              </label>
              <label class="field-full">Telefone / WhatsApp
                <input type="tel" name="telefone" id="prof-tel" value="${esc(me.telefone || '')}" maxlength="15" placeholder="(00) 90000-0000" class="nc-input">
              </label>
            </div>
          </div>

          <div class="profile-section">
            <h4 class="profile-section-title">2. Endereço</h4>
            <p class="profile-section-sub">Informe o CEP para preenchimento automático de logradouro, bairro, cidade e estado.</p>
            <div class="profile-grid-addr-top">
              <label class="field-full">CEP
                <input type="text" name="cep" id="prof-cep" value="${esc(me.cep || '')}" maxlength="9" placeholder="00000-000" class="nc-input">
              </label>
              <label class="field-full">Logradouro / Rua e Número
                <input type="text" name="endereco" id="prof-endereco" value="${esc(me.endereco || '')}" placeholder="Rua, Avenida, Número" class="nc-input">
              </label>
              <label class="field-full">Bairro / Complemento
                <input type="text" name="bairro" id="prof-bairro" value="${esc(me.bairro || '')}" placeholder="Bairro, Sala/Apto" class="nc-input">
              </label>
            </div>
            <div class="profile-grid-addr-bottom">
              <label class="field-full">Cidade
                <input type="text" name="cidade" id="prof-cidade" value="${esc(me.cidade || '')}" placeholder="Ex.: Aracruz" class="nc-input">
              </label>
              <label class="field-full">Estado (UF)
                <input type="text" name="estado" id="prof-estado" value="${esc(me.estado || '')}" maxlength="2" placeholder="ES" style="text-transform:uppercase;" class="nc-input">
              </label>
            </div>
          </div>

          <div class="profile-section">
            <h4 class="profile-section-title">3. Segurança &amp; Alteração de Senha</h4>
            <p class="profile-section-sub">Preencha apenas se desejar substituir sua senha de acesso atual.</p>
            <div class="profile-grid">
              <label class="field-full">Nova Senha (mínimo 6 caracteres)
                <input type="password" name="senha" minlength="6" autocomplete="new-password" placeholder="Deixe em branco para manter a atual" class="nc-input">
              </label>
              <label class="field-full">Confirmar Nova Senha
                <input type="password" name="senha_confirm" minlength="6" autocomplete="new-password" placeholder="Repita a nova senha" class="nc-input">
              </label>
            </div>
          </div>
        </div>

        <!-- Coluna Direita: Currículo, LGPD e Salvar -->
        <div class="card profile-col-card">
          <div>
            <h4 class="profile-section-title">4. Qualificação Profissional</h4>
            <p class="profile-section-sub">Apresentação profissional, formação acadêmica, competências e links de portfólio.</p>
            <div class="profile-grid">
              <label class="field-full">Cargo / Título Profissional
                <input type="text" name="cargo" value="${esc(me.cargo || '')}" placeholder="Ex.: Engenheiro de Software Full Stack" class="nc-input">
              </label>
              <label class="field-full">Área de Atuação / Especialidade
                <input type="text" name="area_atuacao" value="${esc(me.area_atuacao || '')}" placeholder="Ex.: Arquitetura Cloud, Sistemas" class="nc-input">
              </label>
              <label class="field-full">Formação Acadêmica
                <input type="text" name="formacao" value="${esc(me.formacao || '')}" placeholder="Ex.: Ciência da Computação" class="nc-input">
              </label>
              <label class="field-full">LinkedIn / Portfólio / GitHub
                <input type="url" name="linkedin_url" value="${esc(me.linkedin_url || '')}" placeholder="https://linkedin.com/in/seu-perfil" class="nc-input">
              </label>
            </div>
            <div style="margin-top:12px; display:flex; flex-direction:column; gap:12px;">
              <label class="field-full">Principais Competências &amp; Tecnologias
                <input type="text" name="habilidades" value="${esc(me.habilidades || '')}" placeholder="Ex.: Python, FastAPI, PostgreSQL, React, Gestão Ágil" class="nc-input">
              </label>
              <label class="field-full">Resumo Profissional &amp; Experiência
                <textarea name="resumo_profissional" rows="3" placeholder="Descreva sua trajetória profissional, principais projetos conduzidos e certificações..." class="nc-input">${esc(me.resumo_profissional || '')}</textarea>
              </label>
            </div>
          </div>

          <div style="display:flex; flex-direction:column; gap:14px;">
            <div class="lgpd-box">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>
              <div>
                <p>
                  <b>Proteção de Dados Pessoais &amp; Conformidade LGPD (Lei nº 13.709/2018)</b><br>
                  Os dados pessoais e profissionais informados nesta página são tratados pela <b>Nexus Code</b> exclusivamente para identificação contratual, gestão interna e execução dos serviços contratados, protegidos por criptografia e controle de acesso restrito.
                </p>
                <label class="lgpd-check-row">
                  <input type="checkbox" name="lgpd_consent" required ${me.termos_aceitos_em ? 'checked' : ''}>
                  <span>Declaro que as informações fornecidas são verdadeiras e autorizo o tratamento dos meus dados pessoais nos termos da Política de Privacidade e da LGPD.</span>
                </label>
                <div class="lgpd-meta">${consentInfo}</div>
              </div>
            </div>

            <div class="profile-footer-actions">
              <button type="submit" class="btn" id="save-profile-btn">Salvar Alterações do Perfil</button>
            </div>
          </div>
        </div>
      </div>
    </form>
  `;
}

window.bindProfileForm = () => {
  const form = document.getElementById('profile-form');
  if (!form) return;

  const cpfInput = document.getElementById('prof-cpf');
  cpfInput?.addEventListener('input', (e) => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 11);
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    e.target.value = v;
  });

  const telInput = document.getElementById('prof-tel');
  telInput?.addEventListener('input', (e) => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 11);
    if (v.length > 10) v = v.replace(/^(\d{2})(\d{5})(\d{4}).*/, '($1) $2-$3');
    else if (v.length > 5) v = v.replace(/^(\d{2})(\d{4})(\d{0,4}).*/, '($1) $2-$3');
    else if (v.length > 2) v = v.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
    e.target.value = v;
  });

  const cepInput = document.getElementById('prof-cep');
  cepInput?.addEventListener('input', async (e) => {
    let digits = e.target.value.replace(/\D/g, '').slice(0, 8);
    e.target.value = digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
    if (digits.length === 8) {
      try {
        const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
        const addr = await res.json();
        if (!addr.erro) {
          if (addr.logradouro) document.getElementById('prof-endereco').value = addr.logradouro;
          if (addr.bairro) document.getElementById('prof-bairro').value = addr.bairro;
          if (addr.localidade) document.getElementById('prof-cidade').value = addr.localidade;
          if (addr.uf) document.getElementById('prof-estado').value = addr.uf;
        }
      } catch (_) {}
    }
  });

  form.onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('save-profile-btn');
    const raw = Object.fromEntries(new FormData(form));

    if (!raw.lgpd_consent) {
      showNoticeModal({
        title: 'Consentimento LGPD Obrigatório',
        message: 'Marque a caixa de autorização de tratamento de dados pessoais (LGPD) antes de salvar seu perfil.',
        variant: 'warning'
      });
      return;
    }

    if (raw.senha && raw.senha !== raw.senha_confirm) {
      showNoticeModal({
        title: 'Senhas Divergentes',
        message: 'A nova senha e a confirmação de senha devem ser idênticas.',
        variant: 'warning'
      });
      return;
    }

    const optionalFields = [
      'cpf', 'data_nascimento', 'telefone', 'cargo', 'area_atuacao',
      'formacao', 'habilidades', 'linkedin_url', 'resumo_profissional',
      'cep', 'endereco', 'bairro', 'cidade', 'estado'
    ];

    const payload = { nome: raw.nome.trim() };
    for (const field of optionalFields) {
      const val = (raw[field] ?? '').trim();
      payload[field] = val === '' ? null : (field === 'estado' ? val.toUpperCase() : val);
    }
    if (raw.senha && raw.senha.trim() !== '') {
      payload.senha = raw.senha.trim();
    }

    btn.disabled = true;
    btn.textContent = 'Salvando...';
    try {
      const updatedUser = await apiRequest('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(payload)
      });
      user = updatedUser;
      localStorage.setItem('nexus_user', JSON.stringify(user));
      $('#app-user-name').textContent = user.nome;
      $('#user-avatar-initials').textContent = initials(user.nome);
      invalidateCache();
      showToast('Perfil atualizado com sucesso.', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro ao atualizar perfil', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Salvar Alterações do Perfil';
    }
  };
};

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
        <label>Cargo / Função<input name="cargo" placeholder="Ex.: Desenvolvedor Full Stack" value="${esc(editObj?.cargo || '')}"></label>
        <label>Data de Contratação<input name="data_contratacao" type="date" value="${editObj?.data_contratacao ? String(editObj.data_contratacao).slice(0, 10) : ''}"></label>
        <label>Salário Base (R$)<input name="salario_base" type="number" step="0.01" value="${editObj?.salario_base ?? 0}"></label>
        <label>Status<select name="ativo">
          <option value="true" ${editObj?.ativo !== false ? 'selected' : ''}>Ativo</option>
          <option value="false" ${editObj?.ativo === false ? 'selected' : ''}>Inativo</option>
        </select></label>
      </div>`;
  } else if (['tasks', 'kanban'].includes(page)) {
    openPlannerModal(editObj || {
      id: null,
      projeto_id: cache.projetos?.[0]?.id || '',
      responsavel_id: user?.id || null,
      titulo: '',
      descricao: '',
      status: 'pendente',
      prioridade: 'media',
      prazo: ''
    });
    return;
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
  const saveBtn = $('#record-save-btn');
  const prevBtnText = saveBtn ? saveBtn.textContent : 'Salvar';
  let inlineErr = $('#record-form-error');
  if (!inlineErr) {
    inlineErr = document.createElement('div');
    inlineErr.id = 'record-form-error';
    inlineErr.className = 'nc-inline-error';
    inlineErr.style.display = 'none';
    $('#dynamic-record-fields')?.appendChild(inlineErr);
  }
  inlineErr.style.display = 'none';

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Salvando...';
  }

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
          cargo: raw.cargo || null,
          data_contratacao: raw.data_contratacao || null,
          salario_base: Number(raw.salario_base || 0),
          ativo: raw.ativo === 'true',
          ...(raw.senha ? { senha: raw.senha } : {})
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
    showToast(
      modalMode === 'quote_reply'
        ? 'Atendimento comercial registrado com sucesso.'
        : editingId
          ? 'Registro atualizado com sucesso.'
          : 'Registro cadastrado com sucesso.',
      'success'
    );
    render();
  } catch (err) {
    inlineErr.textContent = err?.message || 'Não foi possível concluir a operação.';
    inlineErr.style.display = 'block';
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = prevBtnText;
    }
  }
};

// ==================== RENDERIZADOR PRINCIPAL ====================
async function render(useCache = false) {
  $$('[data-app-page]').forEach((x) => x.classList.toggle('active', x.dataset.appPage === page));

  try {
    if (page === 'dashboard') view.innerHTML = await renderDashboard();
    else if (page === 'quotes') view.innerHTML = await renderQuotes(useCache);
    else if (page === 'projects') view.innerHTML = await renderProjects(useCache);
    else if (page === 'customers') view.innerHTML = await renderClients(false, useCache);
    else if (page === 'leads') view.innerHTML = await renderClients(true, useCache);
    else if (page === 'pipeline') view.innerHTML = await renderKanban(true, useCache);
    else if (page === 'users') view.innerHTML = await renderUsers(useCache);
    else if (page === 'tasks') view.innerHTML = await renderTasks(useCache);
    else if (page === 'kanban') view.innerHTML = await renderKanban(false, useCache);
    else if (page === 'invoices') view.innerHTML = await renderInvoices(useCache);
    else if (page === 'holerite') view.innerHTML = await renderHolerite(useCache);
    else if (page === 'audit') view.innerHTML = await renderAudit(useCache);
    else if (page === 'profile') {
      view.innerHTML = await renderProfile();
      window.bindProfileForm();
    }

    $$('[data-new]').forEach((b) => (b.onclick = () => openRecordModal(null)));
    $$('[data-edit]').forEach((b) => (b.onclick = () => openRecordModal(JSON.parse(b.dataset.edit))));
    $$('[data-reply]').forEach((b) => (b.onclick = () => openQuoteReplyModal(JSON.parse(b.dataset.reply))));
    $$('[data-filter]').forEach((b) => (b.onclick = () => { statusFilter = b.dataset.filter; render(true); }));
    $$('[data-del]').forEach((b) => (b.onclick = () => {
      const label = b.dataset.label ? ` "${b.dataset.label}"` : '';
      showConfirmModal({
        title: 'Confirmar Exclusão',
        message: `Deseja excluir permanentemente o registro${label}?`,
        detail: 'Esta ação é irreversível e removerá permanentemente as informações associadas.',
        confirmText: 'Excluir Registro',
        cancelText: 'Cancelar',
        variant: 'danger',
        onConfirm: async () => {
          await apiRequest(b.dataset.del, { method: 'DELETE' });
          invalidateCache();
          showToast('Registro excluído com sucesso.', 'success');
          await render();
        }
      });
    }));
    $$('[data-pay]').forEach((b) => (b.onclick = () => {
      showConfirmModal({
        title: 'Confirmar Recebimento',
        message: 'Deseja registrar o pagamento desta fatura?',
        detail: 'O status financeiro será atualizado para Pago com a data e hora atuais.',
        confirmText: 'Confirmar Pagamento',
        cancelText: 'Cancelar',
        variant: 'primary',
        onConfirm: async () => {
          await apiRequest(`/faturas/${b.dataset.pay}`, { method: 'PATCH', body: JSON.stringify({ status: 'pago' }) });
          invalidateCache();
          showToast('Pagamento confirmado com sucesso.', 'success');
          await render();
        }
      });
    }));
    $$('[data-move-client]').forEach((b) => (b.onclick = async () => {
      try {
        const [id, status_funil] = b.dataset.moveClient.split(':');
        await apiRequest(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify({ status_funil }) });
        invalidateCache();
        showToast('Etapa comercial atualizada.', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Falha ao Mover Oportunidade', message: err.message, variant: 'error' });
      }
    }));
    $$('[data-move-task]').forEach((b) => (b.onclick = async () => {
      try {
        const [id, status] = b.dataset.moveTask.split(':');
        await apiRequest(`/tarefas/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
        invalidateCache();
        showToast('Status da tarefa atualizado.', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Falha ao Atualizar Tarefa', message: err.message, variant: 'error' });
      }
    }));

    // Drag and Drop para Planner Kanban e Funil de Vendas
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
        const current = dragged;
        dragged = null;
        const targetStatus = col.dataset.dropCol;
        try {
          if (current.type === 'client') {
            await apiRequest(`/clientes/${current.id}`, { method: 'PATCH', body: JSON.stringify({ status_funil: targetStatus }) });
            showToast('Etapa comercial atualizada.', 'success');
          } else if (current.type === 'task') {
            await apiRequest(`/tarefas/${current.id}`, { method: 'PATCH', body: JSON.stringify({ status: targetStatus }) });
            showToast('Tarefa movida no Planner.', 'success');
          }
          invalidateCache();
          render();
        } catch (err) {
          showNoticeModal({ title: 'Não foi possível concluir a movimentação', message: err.message, variant: 'error' });
        }
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

window.nexusClearSearch = () => {
  const inp = $('#global-search');
  const clearBtn = $('#clear-global-search');
  if (inp) inp.value = '';
  if (clearBtn) clearBtn.style.display = 'none';
  searchTerm = '';
  render(true);
};

$$('[data-app-page]').forEach((b) => (b.onclick = () => {
  page = b.dataset.appPage;
  statusFilter = 'todos';
  closeMobileDrawer();
  render();
}));

$('#global-search')?.addEventListener('input', (e) => {
  searchTerm = e.target.value;
  const clearBtn = $('#clear-global-search');
  if (clearBtn) clearBtn.style.display = searchTerm ? 'inline-block' : 'none';
  render(true);
});

$('#clear-global-search')?.addEventListener('click', window.nexusClearSearch);

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
