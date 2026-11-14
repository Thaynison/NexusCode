import { apiRequest, clearSession, getToken } from './config.js';
import { showToast, showNoticeModal } from './ui.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const view = $('#view');
const shell = $('#app-shell');
const side = $('#app-side');
const backdrop = $('#sidebar-backdrop');

let user = null;
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const formatMoney = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const initials = (name) => String(name || 'NC').trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() || '').join('');

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
  } else if (page === 'profile') {
    const me = await apiRequest('/auth/me'); // Get fresh user data
    view.innerHTML = `
      <div class="toolbar">
        <div>
          <h1>Meu Perfil</h1>
          <span class="muted">Gerencie suas informações pessoais, endereço e aceite as políticas de privacidade (LGPD)</span>
        </div>
      </div>
      <div class="grid" style="grid-template-columns: 1fr; max-width: 800px;">
        <div class="card">
          <div class="row-entity" style="margin-bottom:24px; padding-bottom: 24px; border-bottom: 1px solid var(--border);">
            <div class="row-avatar" style="width:56px; height:56px; font-size:18px;">${initials(me.nome)}</div>
            <div>
              <h3 style="margin:0 0 6px; font-size:20px;">${esc(me.nome)}</h3>
              <div style="display:flex; gap:10px; align-items:center;">
                <span class="muted">${esc(me.email)}</span>
                <span class="badge ativo">Cliente</span>
              </div>
            </div>
          </div>

          <form id="profile-form" style="display:flex; flex-direction:column; gap:16px;">
            <h4 style="margin:0; font-size:15px; color:var(--text); font-weight:700;">Dados Pessoais & Profissionais</h4>
            <div class="profile-grid">
              <label class="field-full">Nome Completo *
                <input type="text" name="nome" value="${esc(me.nome)}" required class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Cargo / Profissão
                <input type="text" name="cargo" value="${esc(me.cargo || '')}" placeholder="Ex.: Proprietário" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">CPF
                <input type="text" name="cpf" value="${esc(me.cpf || '')}" placeholder="000.000.000-00" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Data de Nascimento
                <input type="date" name="data_nascimento" value="${me.data_nascimento || ''}" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Telefone / WhatsApp
                <input type="tel" name="telefone" value="${esc(me.telefone || '')}" placeholder="(00) 90000-0000" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
            </div>

            <h4 style="margin:12px 0 0; font-size:15px; color:var(--text); font-weight:700;">Endereço</h4>
            <div class="profile-grid">
              <label class="field-full">CEP
                <input type="text" name="cep" value="${esc(me.cep || '')}" placeholder="00000-000" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Endereço Completo
                <input type="text" name="endereco" value="${esc(me.endereco || '')}" placeholder="Rua, Número, Bairro" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Cidade
                <input type="text" name="cidade" value="${esc(me.cidade || '')}" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
              <label class="field-full">Estado (UF)
                <input type="text" name="estado" value="${esc(me.estado || '')}" maxlength="2" placeholder="Ex.: ES" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
            </div>

            <h4 style="margin:12px 0 0; font-size:15px; color:var(--text); font-weight:700;">Segurança</h4>
            <div class="profile-grid">
              <label class="field-full">Nova Senha (deixe em branco para manter)
                <input type="password" name="senha" minlength="6" placeholder="******" class="modal-input" style="width:100%; background:var(--surface2); border:1px solid var(--border); padding:10px 12px; border-radius:8px;">
              </label>
            </div>

            <div class="lgpd-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
              <div>
                <p><b>Privacidade e Proteção de Dados (LGPD)</b><br>As informações coletadas neste perfil são armazenadas com criptografia de ponta a ponta e utilizadas exclusivamente para processamento contratual, faturamento e prestação dos serviços contratados, conforme a Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018). Seus dados não serão compartilhados com terceiros.</p>
                <label>
                  <input type="checkbox" name="lgpd_consent" required ${me.termos_aceitos_em ? 'checked' : ''}>
                  Confirmo que os dados fornecidos são exatos e consinto com o tratamento para as finalidades descritas.
                </label>
              </div>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:12px;">
              <button type="submit" class="btn" id="save-profile-btn">Atualizar Meu Perfil</button>
            </div>
          </form>
        </div>
      </div>
    `;

    setTimeout(() => {
      const form = document.getElementById('profile-form');
      if (form) {
        form.onsubmit = async (e) => {
          e.preventDefault();
          const btn = document.getElementById('save-profile-btn');
          const raw = Object.fromEntries(new FormData(form));
          
          if (!raw.lgpd_consent) {
            showNoticeModal({ title: 'Atenção', message: 'Você precisa consentir com os termos da LGPD para salvar seu perfil.', variant: 'warning' });
            return;
          }
          
          const payload = {};
          for (const [k, v] of Object.entries(raw)) {
            if (v.trim() !== '' && k !== 'lgpd_consent') payload[k] = v.trim();
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
            $('#portal-user').textContent = user.nome;
            $('#portal-initials').textContent = user.nome.slice(0, 2).toUpperCase();
            showToast('Perfil atualizado com sucesso.', 'success');
          } catch (err) {
            showNoticeModal({ title: 'Erro ao atualizar perfil', message: err.message, variant: 'error' });
          } finally {
            btn.disabled = false;
            btn.textContent = 'Atualizar Meu Perfil';
          }
        };
      }
    }, 50);
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
