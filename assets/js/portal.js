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
const formatDateTime = (v) => { if (!v) return '-'; const d = new Date(v); return isNaN(d) ? v : d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }); };

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
    const me = await apiRequest('/auth/me');
    const consentInfo = me.termos_aceitos_em
      ? `Consentimento LGPD registrado em ${formatDateTime(me.termos_aceitos_em)}.`
      : 'Pendente de confirmação de consentimento LGPD.';

    view.innerHTML = `
      <form id="profile-form" class="profile-shell">
        <div class="card profile-header-card">
          <div class="row-entity">
            <div class="row-avatar" style="width:48px; height:48px; font-size:17px;">${initials(me.nome)}</div>
            <div>
              <h3 style="margin:0 0 3px; font-size:18px;">${esc(me.nome)}</h3>
              <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <span class="muted">${esc(me.email)}</span>
                ${me.cargo ? `<span class="badge">${esc(me.cargo)}</span>` : ''}
                <span class="badge ativo">Cliente</span>
              </div>
            </div>
          </div>
        </div>

        <div class="profile-columns">
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
              <p class="profile-section-sub">Informe o CEP para preenchimento automático do endereço.</p>
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
                  <input type="text" name="cidade" id="prof-cidade" value="${esc(me.cidade || '')}" class="nc-input">
                </label>
                <label class="field-full">Estado (UF)
                  <input type="text" name="estado" id="prof-estado" value="${esc(me.estado || '')}" maxlength="2" placeholder="ES" style="text-transform:uppercase;" class="nc-input">
                </label>
              </div>
            </div>

            <div class="profile-section">
              <h4 class="profile-section-title">3. Segurança &amp; Alteração de Senha</h4>
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

          <div class="card profile-col-card">
            <div>
              <h4 class="profile-section-title">4. Qualificação Profissional</h4>
              <p class="profile-section-sub">Apresentação profissional, formação acadêmica e portfólio.</p>
              <div class="profile-grid">
                <label class="field-full">Cargo / Profissão
                  <input type="text" name="cargo" value="${esc(me.cargo || '')}" placeholder="Ex.: Diretor Comercial" class="nc-input">
                </label>
                <label class="field-full">Área de Atuação
                  <input type="text" name="area_atuacao" value="${esc(me.area_atuacao || '')}" placeholder="Ex.: Tecnologia, Varejo, Indústria" class="nc-input">
                </label>
                <label class="field-full">Formação Acadêmica
                  <input type="text" name="formacao" value="${esc(me.formacao || '')}" placeholder="Ex.: Administração / Engenharia" class="nc-input">
                </label>
                <label class="field-full">LinkedIn / Site / Portfólio
                  <input type="url" name="linkedin_url" value="${esc(me.linkedin_url || '')}" placeholder="https://linkedin.com/in/seu-perfil" class="nc-input">
                </label>
              </div>
              <div style="margin-top:12px; display:flex; flex-direction:column; gap:12px;">
                <label class="field-full">Principais Competências
                  <input type="text" name="habilidades" value="${esc(me.habilidades || '')}" placeholder="Ex.: Gestão de Projetos, Estratégia Digital" class="nc-input">
                </label>
                <label class="field-full">Resumo Profissional
                  <textarea name="resumo_profissional" rows="3" placeholder="Conte um pouco sobre sua experiência e objetivos..." class="nc-input">${esc(me.resumo_profissional || '')}</textarea>
                </label>
              </div>
            </div>

            <div style="display:flex; flex-direction:column; gap:14px;">
              <div class="lgpd-box">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>
                <div>
                  <p>
                    <b>Proteção de Dados Pessoais &amp; Conformidade LGPD (Lei nº 13.709/2018)</b><br>
                    Os dados pessoais e profissionais informados são protegidos por criptografia e utilizados exclusivamente pela <b>Nexus Code</b> para atendimento, faturamento e execução dos projetos contratados, sem compartilhamento indevido com terceiros.
                  </p>
                  <label class="lgpd-check-row">
                    <input type="checkbox" name="lgpd_consent" required ${me.termos_aceitos_em ? 'checked' : ''}>
                    <span>Declaro que os dados fornecidos são exatos e autorizo o tratamento nos termos da Política de Privacidade (LGPD).</span>
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

    const form = document.getElementById('profile-form');
    if (form) {
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
          $('#portal-user').textContent = user.nome;
          $('#portal-initials').textContent = initials(user.nome);
          showToast('Perfil atualizado com sucesso.', 'success');
          render('profile');
        } catch (err) {
          showNoticeModal({ title: 'Erro ao atualizar perfil', message: err.message, variant: 'error' });
        } finally {
          btn.disabled = false;
          btn.textContent = 'Salvar Alterações do Perfil';
        }
      };
    }
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
