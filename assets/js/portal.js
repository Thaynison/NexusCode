import { apiRequest, clearSession, getToken } from './config.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const view = $('#view');
const shell = $('#app-shell');
const side = $('#app-side');
const backdrop = $('#sidebar-backdrop');

let user = null;
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const formatMoney = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

$('#app-menu')?.addEventListener('click', () => {
  if (window.innerWidth <= 900) {
    side.classList.toggle('open');
    backdrop.classList.toggle('open');
  } else {
    shell.classList.toggle('sidebar-collapsed');
  }
});
backdrop?.addEventListener('click', () => { side.classList.remove('open'); backdrop.classList.remove('open'); });
$('#theme')?.addEventListener('click', () => shell.classList.toggle('app-dark'));
$('#logout')?.addEventListener('click', () => { clearSession(); window.location.href = '../index.html'; });

async function render(page) {
  $$('[data-page]').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
  if (page === 'quotes') {
    const items = await apiRequest('/portal/orcamentos');
    view.innerHTML = `
      <div class="toolbar">
        <div><h1>Minhas Solicitações</h1><span class="muted">Histórico de solicitações enviadas e retornos da equipe comercial</span></div>
        <a href="../index.html#contact" class="btn" style="text-decoration:none;">+ Nova Solicitação</a>
      </div>
      ${items.map((q) => `
        <div class="card" style="margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px;">
            <div>
              <b>${esc(q.tipo_projeto || 'Orçamento')}</b>
              <span class="muted" style="font-size:12px;"> • Enviado em ${new Date(q.criado_em).toLocaleDateString('pt-BR')}</span>
            </div>
            <span class="badge ${esc(q.status)}">${esc(q.status).replace('_', ' ')}</span>
          </div>
          <div class="quote-box">${esc(q.mensagem)}</div>
          ${q.resposta ? `
            <div class="quote-reply-box" style="margin-bottom:0;">
              <div style="font-size:12px; font-weight:700; color:var(--primary); margin-bottom:4px;">
                Resposta de ${esc(q.respondido_por || 'Equipe Nexus Code')}:
              </div>
              ${esc(q.resposta)}
            </div>
          ` : '<p class="muted" style="margin:0; font-size:13px;">Em análise pela equipe comercial.</p>'}
        </div>
      `).join('') || '<div class="card"><p class="muted">Nenhuma solicitação registrada para esta conta.</p></div>'}`;
  } else if (page === 'projects') {
    const items = await apiRequest('/projetos');
    view.innerHTML = `
      <div class="toolbar"><div><h1>Meus Projetos</h1><span class="muted">Acompanhamento de escopo, cronograma e status das entregas</span></div></div>
      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Projeto</th><th>Status</th><th>Progresso</th><th>Valor</th></tr></thead>
          <tbody>${items.map((p) => `<tr><td><b>${esc(p.titulo)}</b></td><td><span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span></td><td>${p.progresso}%</td><td>${formatMoney(p.valor_total)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Nenhum projeto ativo vinculado a esta conta.</td></tr>'}</tbody>
        </table>
      </div>`;
  } else if (page === 'invoices') {
    const items = await apiRequest('/faturas');
    view.innerHTML = `
      <div class="toolbar"><div><h1>Minhas Faturas</h1><span class="muted">Demonstrativo financeiro, faturas e vencimentos</span></div></div>
      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Descrição</th><th>Valor</th><th>Status</th><th>Vencimento</th></tr></thead>
          <tbody>${items.map((f) => `<tr><td><b>${esc(f.descricao)}</b></td><td>${formatMoney(f.valor)}</td><td><span class="badge ${esc(f.status)}">${esc(f.status)}</span></td><td>${esc(f.vencimento)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Nenhuma fatura emitida para esta conta.</td></tr>'}</tbody>
        </table>
      </div>`;
  } else {
    view.innerHTML = `
      <div class="toolbar"><div><h1>Meu Perfil</h1><span class="muted">Informações cadastrais da conta</span></div></div>
      <div class="card" style="max-width:480px;">
        <p><b>Nome:</b> ${esc(user.nome)}</p>
        <p><b>E-mail:</b> ${esc(user.email)}</p>
        <p><b>Perfil:</b> <span class="badge ativo">Cliente</span></p>
      </div>`;
  }
}

$$('[data-page]').forEach((b) => (b.onclick = () => render(b.dataset.page)));

if (!getToken()) {
  window.location.href = '../login.html';
} else {
  apiRequest('/auth/me')
    .then((u) => {
      user = u;
      $('#portal-user').textContent = u.nome;
      $('#portal-initials').textContent = u.nome.slice(0, 2).toUpperCase();
      render('quotes');
    })
    .catch(() => { clearSession(); window.location.href = '../login.html'; });
}
