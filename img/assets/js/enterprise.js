import { apiRequest, setSession, clearSession, getToken } from './config.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const authDialog = $('#auth-dialog');
const authForm = $('#auth-form');
const authStatus = $('#auth-status');
const app = $('#enterprise-app');
const view = $('#app-view');
const recordDialog = $('#record-dialog');
const recordForm = $('#record-form');

let page = 'dashboard';
let user = null;
let editingId = null;
let searchTerm = '';
let statusFilter = 'todos';
let cache = { clientes: [], usuarios: [], projetos: [] };

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

// ==================== CONTROLE DO MODAL DE LOGIN ====================
function switchAuthMode(mode) {
  authForm.mode.value = mode;
  $$('[data-auth-tab]').forEach((btn) => {
    if (btn.classList.contains('nc-tab')) {
      btn.classList.toggle('active', btn.dataset.authTab === mode);
    }
  });

  const titles = {
    login: ['Bem-vindo de volta', 'Acesse o painel de gestão empresarial da Nexus Code', 'Entrar no Sistema'],
    register: ['Criar nova conta', 'Cadastre-se para acompanhar seus projetos no portal', 'Criar Minha Conta'],
    forgot: ['Recuperar senha', 'Informe seu e-mail para receber o link de redefinição', 'Enviar Instruções']
  };

  $('#auth-title').textContent = titles[mode][0];
  $('#auth-subtitle').textContent = titles[mode][1];
  $('#auth-submit-btn span').textContent = titles[mode][2];

  $('#auth-extra').innerHTML = mode === 'register'
    ? `<div class="nc-field">
        <label for="auth-name">Nome completo</label>
        <div class="nc-input-wrap">
          <svg class="nc-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          <input id="auth-name" name="displayName" type="text" placeholder="Ex: João Silva" required>
        </div>
      </div>`
    : '';

  $('#password-wrap').style.display = mode === 'forgot' ? 'none' : 'flex';
  authForm.password.required = mode !== 'forgot';
  authStatus.className = 'nc-auth-status';
  authStatus.textContent = '';
}

$$('[data-open-auth]').forEach((b) => (b.onclick = () => {
  if (user) {
    openApp();
  } else {
    switchAuthMode('login');
    authDialog.showModal();
  }
}));

$('[data-close-auth]').onclick = () => authDialog.close();

authDialog.addEventListener('click', (e) => {
  if (e.target === authDialog) authDialog.close();
});

$$('[data-auth-tab]').forEach((b) => (b.onclick = () => switchAuthMode(b.dataset.authTab)));

$('#toggle-password')?.addEventListener('click', () => {
  const pwd = $('#auth-password');
  pwd.type = pwd.type === 'password' ? 'text' : 'password';
});

authForm.onsubmit = async (e) => {
  e.preventDefault();
  const mode = authForm.mode.value;
  const btn = $('#auth-submit-btn');
  const labelSpan = btn.querySelector('span');
  const prevText = labelSpan.textContent;

  btn.disabled = true;
  labelSpan.textContent = 'Autenticando...';
  authStatus.className = 'nc-auth-status';
  authStatus.textContent = '';

  try {
    const raw = Object.fromEntries(new FormData(authForm));

    if (mode === 'forgot') {
      const res = await apiRequest('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email: raw.username })
      });
      authStatus.className = 'nc-auth-status success';
      authStatus.textContent = res.message;
      return;
    }

    const endpoint = mode === 'register' ? '/auth/register' : '/auth/login';
    const payload = mode === 'register'
      ? { nome: raw.displayName, email: raw.username, senha: raw.password }
      : { email: raw.username, senha: raw.password };

    const data = await apiRequest(endpoint, {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    setSession(data.access_token, data.usuario);
    user = data.usuario;
    authDialog.close();
    openApp();
  } catch (err) {
    authStatus.className = 'nc-auth-status error';
    authStatus.textContent = err.message;
  } finally {
    btn.disabled = false;
    labelSpan.textContent = prevText;
  }
};

// ==================== NAVEGAÇÃO DO PAINEL CRM ====================
const internalRoles = new Set(['admin', 'colaborador']);
const clientPages = new Set(['dashboard', 'projects', 'invoices', 'profile']);

function openApp() {
  document.body.style.overflow = 'hidden';
  app.classList.remove('hidden');
  $('#app-user-name').textContent = user.nome;
  $('#user-avatar-initials').textContent = initials(user.nome);

  const isStaff = internalRoles.has(user.perfil);
  $$('[data-app-page]').forEach((b) => {
    b.style.display = isStaff || clientPages.has(b.dataset.appPage) ? 'flex' : 'none';
  });

  page = isStaff ? 'dashboard' : 'projects';
  statusFilter = 'todos';
  render();
}

async function preloadRefs() {
  if (!internalRoles.has(user?.perfil)) return;
  try {
    const [clientes, usuarios, projetos] = await Promise.all([
      apiRequest('/clientes'),
      apiRequest('/usuarios'),
      apiRequest('/projetos')
    ]);
    cache = { clientes, usuarios, projetos };
  } catch (_) {}
}

function matchSearch(texts) {
  if (!searchTerm) return true;
  const q = searchTerm.toLowerCase();
  return texts.some((t) => String(t ?? '').toLowerCase().includes(q));
}

// ==================== TELAS DO SISTEMA ====================
async function renderDashboard() {
  if (!internalRoles.has(user.perfil)) {
    const projetos = await apiRequest('/projetos');
    return `
      <div class="toolbar">
        <div><h1>Olá, ${esc(user.nome)}</h1><span class="muted">Acompanhe seus projetos e faturas na Nexus Code</span></div>
      </div>
      <div class="grid">
        <div class="card metric"><span class="title">Meus Projetos</span><strong>${projetos.length}</strong><span class="pill-info">Ativos no portal</span></div>
      </div>`;
  }

  const [kpi, projetos, clientes] = await Promise.all([
    apiRequest('/dashboard/resumo'),
    apiRequest('/projetos'),
    apiRequest('/clientes')
  ]);

  return `
    <div class="toolbar">
      <div>
        <h1>Dashboard Executivo</h1>
        <span class="muted">Visão consolidada em tempo real • MySQL Localhost</span>
      </div>
      <button class="btn" onclick="window.nexusGo('projects', true)">+ Novo Projeto</button>
    </div>

    <div class="grid">
      <div class="card metric">
        <span class="title">Clientes &amp; Leads</span>
        <strong>${kpi.total_clientes}</strong>
        <span class="pill-info">${kpi.leads_abertos} leads no funil</span>
      </div>
      <div class="card metric">
        <span class="title">Projetos Ativos</span>
        <strong>${kpi.projetos_ativos}</strong>
        <span class="pill-info">Em execução / homologação</span>
      </div>
      <div class="card metric">
        <span class="title">Tarefas Pendentes</span>
        <strong>${kpi.tarefas_pendentes}</strong>
        <span class="pill-info">Backlog operacional</span>
      </div>
      <div class="card metric">
        <span class="title">Receita Paga</span>
        <strong>${formatMoney(kpi.receita_paga)}</strong>
        <span class="pill-info">A receber: ${formatMoney(kpi.receita_pendente)}</span>
      </div>
    </div>

    <div class="grid" style="margin-top:20px; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));">
      <div class="card">
        <div class="toolbar" style="margin-bottom:12px;">
          <h3 style="margin:0; font-size:16px;">Projetos em Andamento</h3>
          <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusGo('projects')">Ver todos</button>
        </div>
        ${projetos.slice(0, 5).map((p) => `
          <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
            <div>
              <b>${esc(p.titulo)}</b>
              <div class="muted" style="font-size:12px;">Progresso: ${p.progresso}% • ${formatMoney(p.valor_total)}</div>
            </div>
            <span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span>
          </div>
        `).join('') || '<p class="muted">Nenhum projeto cadastrado.</p>'}
      </div>

      <div class="card">
        <div class="toolbar" style="margin-bottom:12px;">
          <h3 style="margin:0; font-size:16px;">Últimos Clientes &amp; Leads</h3>
          <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusGo('customers')">Ver todos</button>
        </div>
        ${clientes.slice(0, 5).map((c) => `
          <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
            <div class="row-entity">
              <div class="row-avatar">${initials(c.nome_empresa)}</div>
              <div>
                <b>${esc(c.nome_empresa)}</b>
                <div class="muted" style="font-size:12px;">${esc(c.contato_nome)} • ${esc(c.email)}</div>
              </div>
            </div>
            <span class="badge ${esc(c.status_funil)}">${esc(c.status_funil)}</span>
          </div>
        `).join('') || '<p class="muted">Nenhum cliente cadastrado.</p>'}
      </div>
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
            <div class="muted" style="font-size:12px;">${esc(p.descricao || 'Sem descrição')}</div>
          </div>
        </div>
      </td>
      <td>${esc(clientMap[p.cliente_id] || 'Cliente #' + p.cliente_id)}</td>
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
      <div><h1>Projetos</h1><span class="muted">Gerencie entregas, responsáveis, progresso e valores</span></div>
      ${isStaff ? `<button class="btn" data-new>+ Novo Projeto</button>` : ''}
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
      <div><h1>${onlyLeads ? 'Leads' : 'Clientes & Empresas'}</h1><span class="muted">Base comercial salva no MySQL</span></div>
      <button class="btn" data-new>+ Novo ${onlyLeads ? 'Lead' : 'Cliente'}</button>
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
      <div><h1>Usuários e Permissões</h1><span class="muted">Controle de acesso para administradores, equipe e clientes</span></div>
      <button class="btn" data-new>+ Novo Usuário</button>
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
      <div><h1>Tarefas &amp; Atividades</h1><span class="muted">Acompanhamento de entregas por projeto</span></div>
      <button class="btn" data-new>+ Nova Tarefa</button>
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
      <td>${esc(clientMap[f.cliente_id] || 'Cliente #' + f.cliente_id)}</td>
      <td style="font-weight:700;">${formatMoney(f.valor)}</td>
      <td><span class="badge ${esc(f.status)}">${esc(f.status)}</span></td>
      <td>${formatDate(f.vencimento)}</td>
      ${isStaff ? `<td style="white-space:nowrap;">
        ${f.status !== 'pago' ? `<button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--ok);" data-pay="${f.id}">Dar Baixa</button>` : ''}
        <button class="btn secondary" style="padding:6px 10px; font-size:12px; color:var(--danger);" data-del="/faturas/${f.id}">Excluir</button>
      </td>` : ''}
    </tr>`).join('');

  return `
    <div class="toolbar">
      <div><h1>Faturas &amp; Financeiro</h1><span class="muted">Controle de cobranças e recebimentos</span></div>
      ${isStaff ? `<button class="btn" data-new>+ Nova Fatura</button>` : ''}
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
      <div class="toolbar"><div><h1>Funil de Vendas</h1><span class="muted">Mova os clientes entre as etapas comerciais</span></div><button class="btn" data-new>+ Novo Lead</button></div>
      <div class="app-kanban">
        ${cols.map((col) => `
          <section class="app-column">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <b>${col.label}</b>
              <span class="filter-count">${clientes.filter((c) => c.status_funil === col.key).length}</span>
            </div>
            ${clientes.filter((c) => c.status_funil === col.key).map((c) => `
              <div class="app-ticket">
                <b>${esc(c.nome_empresa)}</b>
                <p class="muted" style="font-size:12px; margin:4px 0 10px;">${esc(c.contato_nome)}</p>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                  ${cols.filter((x) => x.key !== col.key).map((x) => `
                    <button class="btn secondary" style="padding:4px 8px; font-size:11px;" data-move-client="${c.id}:${x.key}">→ ${x.label.split(' ')[0]}</button>
                  `).join('')}
                </div>
              </div>
            `).join('') || '<p class="muted" style="font-size:12px;">Nenhum card nesta etapa</p>'}
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
    <div class="toolbar"><div><h1>Quadro Kanban</h1><span class="muted">Fluxo operacional de tarefas</span></div><button class="btn" data-new>+ Nova Tarefa</button></div>
    <div class="app-kanban">
      ${cols.map((col) => `
        <section class="app-column">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <b>${col.label}</b>
            <span class="filter-count">${tarefas.filter((t) => t.status === col.key).length}</span>
          </div>
          ${tarefas.filter((t) => t.status === col.key).map((t) => `
            <div class="app-ticket">
              <b>${esc(t.titulo)}</b>
              <p class="muted" style="font-size:12px; margin:4px 0 10px;">Prazo: ${formatDate(t.prazo)}</p>
              <div style="display:flex; gap:4px; flex-wrap:wrap;">
                ${cols.filter((x) => x.key !== col.key).map((x) => `
                  <button class="btn secondary" style="padding:4px 8px; font-size:11px;" data-move-task="${t.id}:${x.key}">→ ${x.label}</button>
                `).join('')}
              </div>
            </div>
          `).join('') || '<p class="muted" style="font-size:12px;">Sem tarefas</p>'}
        </section>
      `).join('')}
    </div>`;
}

async function renderAudit() {
  const logs = await apiRequest('/auditoria');
  return `
    <div class="toolbar"><div><h1>Logs de Auditoria</h1><span class="muted">Registro de ações realizadas no sistema</span></div></div>
    <div class="card table-wrap">
      <table class="table">
        <thead><tr><th>Data / Hora</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead>
        <tbody>${logs.map((l) => `<tr><td>${new Date(l.criado_em).toLocaleString('pt-BR')}</td><td><b>${esc(l.usuario_nome)}</b></td><td><span class="badge">${esc(l.acao)}</span></td><td>${esc(l.detalhes)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Nenhum log registrado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderProfile() {
  return `
    <div class="toolbar"><div><h1>Meu Perfil</h1><span class="muted">Informações da sessão autenticada</span></div></div>
    <div class="card" style="max-width:520px;">
      <div class="row-entity" style="margin-bottom:20px;">
        <div class="row-avatar" style="width:48px; height:48px; font-size:16px;">${initials(user.nome)}</div>
        <div>
          <h3 style="margin:0;">${esc(user.nome)}</h3>
          <span class="muted">${esc(user.email)}</span>
        </div>
      </div>
      <p><b>Nível de Acesso:</b> <span class="badge ativo">${esc(user.perfil)}</span></p>
      <p><b>API Conectada:</b> <code>http://127.0.0.1:8000/api</code></p>
    </div>`;
}

// ==================== MODAL DE CADASTRO / EDIÇÃO ====================
async function openRecordModal(editObj = null) {
  editingId = editObj ? editObj.id : null;
  await preloadRefs();
  const titleEl = $('#record-modal-title');
  const box = $('#dynamic-record-fields');

  const clientOptions = cache.clientes.map((c) => `<option value="${c.id}" ${editObj?.cliente_id === c.id ? 'selected' : ''}>${esc(c.nome_empresa)}</option>`).join('');
  const userOptions = `<option value="">-- Sem responsável --</option>` + cache.usuarios.map((u) => `<option value="${u.id}" ${editObj?.responsavel_id === u.id ? 'selected' : ''}>${esc(u.nome)}</option>`).join('');
  const projectOptions = cache.projetos.map((p) => `<option value="${p.id}" ${editObj?.projeto_id === p.id ? 'selected' : ''}>${esc(p.titulo)}</option>`).join('');

  if (page === 'projects') {
    titleEl.textContent = editObj ? 'Editar Projeto' : 'Novo Projeto';
    box.innerHTML = `
      <div class="formgrid">
        <label>Título do Projeto *<input name="titulo" required value="${esc(editObj?.titulo || '')}"></label>
        <label>Cliente *<select name="cliente_id" required>${clientOptions || '<option value="">Cadastre um cliente primeiro</option>'}</select></label>
        <label>Responsável<select name="responsavel_id">${userOptions}</select></label>
        <label>Status<select name="status">
          ${['planejamento', 'em_andamento', 'homologacao', 'concluido', 'cancelado'].map((s) => `<option value="${s}" ${editObj?.status === s ? 'selected' : ''}>${s}</option>`).join('')}
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
        <label>Origem<input name="origem" placeholder="Site, Indicação..." value="${esc(editObj?.origem || '')}"></label>
      </div>
      <label class="field-full" style="margin-top:16px;">Observações<textarea name="observacoes" rows="3">${esc(editObj?.observacoes || '')}</textarea></label>`;
  } else if (page === 'users') {
    titleEl.textContent = editObj ? 'Editar Usuário' : 'Novo Usuário';
    box.innerHTML = `
      <div class="formgrid">
        <label>Nome Completo *<input name="nome" required value="${esc(editObj?.nome || '')}"></label>
        <label>E-mail *<input name="email" type="email" required value="${esc(editObj?.email || '')}"></label>
        <label>Senha ${editObj ? '(vazio para manter)' : '*'}<input name="senha" type="password" ${editObj ? '' : 'required'} minlength="6"></label>
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
        <label>Projeto *<select name="projeto_id" required>${projectOptions || '<option value="">Cadastre um projeto primeiro</option>'}</select></label>
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
        <label>Descrição *<input name="descricao" required placeholder="Parcela 1 - Desenvolvimento"></label>
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
    if (page === 'projects') {
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
    render();
  } catch (err) {
    alert('Erro ao salvar: ' + err.message);
  }
};

// ==================== RENDERIZADOR PRINCIPAL ====================
async function render() {
  const btn = $(`[data-app-page="${page}"]`);
  $('#app-title').textContent = btn?.textContent.replace(/^[^\wÀ-ÿ]+/, '').trim() || 'Dashboard';
  $$('[data-app-page]').forEach((x) => x.classList.toggle('active', x.dataset.appPage === page));

  try {
    if (page === 'dashboard') view.innerHTML = await renderDashboard();
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
    $$('[data-filter]').forEach((b) => (b.onclick = () => { statusFilter = b.dataset.filter; render(); }));
    $$('[data-del]').forEach((b) => (b.onclick = async () => {
      if (!confirm('Deseja realmente excluir este registro?')) return;
      await apiRequest(b.dataset.del, { method: 'DELETE' });
      render();
    }));
    $$('[data-pay]').forEach((b) => (b.onclick = async () => {
      await apiRequest(`/faturas/${b.dataset.pay}`, { method: 'PATCH', body: JSON.stringify({ status: 'pago' }) });
      render();
    }));
    $$('[data-move-client]').forEach((b) => (b.onclick = async () => {
      const [id, status_funil] = b.dataset.moveClient.split(':');
      await apiRequest(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify({ status_funil }) });
      render();
    }));
    $$('[data-move-task]').forEach((b) => (b.onclick = async () => {
      const [id, status] = b.dataset.moveTask.split(':');
      await apiRequest(`/tarefas/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      render();
    }));
  } catch (err) {
    view.innerHTML = `<div class="card" style="border-left:4px solid var(--danger);"><b>Aviso:</b> ${esc(err.message)}</div>`;
  }
}

window.nexusGo = (targetPage, openCreate = false) => {
  page = targetPage;
  statusFilter = 'todos';
  render().then(() => {
    if (openCreate) openRecordModal(null);
  });
};

$$('[data-app-page]').forEach((b) => (b.onclick = () => {
  page = b.dataset.appPage;
  statusFilter = 'todos';
  render();
}));

$('#global-search')?.addEventListener('input', (e) => {
  searchTerm = e.target.value;
  if (page !== 'dashboard' && page !== 'profile') render();
});

$$('[data-close-record]').forEach((b) => (b.onclick = () => recordDialog.close()));
$('#app-menu')?.addEventListener('click', () => $('#app-side').classList.toggle('open'));
$('#app-theme')?.addEventListener('click', () => app.classList.toggle('app-dark'));
$('#app-logout')?.addEventListener('click', () => {
  clearSession();
  app.classList.add('hidden');
  document.body.style.overflow = 'auto';
  user = null;
});

if (getToken()) {
  apiRequest('/auth/me')
    .then((u) => {
      user = u;
      openApp();
    })
    .catch(() => clearSession());
}
