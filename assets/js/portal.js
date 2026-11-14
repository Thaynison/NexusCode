import { apiRequest, clearSession, getToken, applyWhiteLabelBranding } from './config.js';
import { showToast, showNoticeModal, showConfirmModal } from './ui.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const view = $('#view');
const shell = $('#app-shell');
const side = $('#app-side');
const backdrop = $('#sidebar-backdrop');
const portalDialog = $('#portal-dialog');
const portalModalContainer = $('#portal-modal-container');

let user = null;
let currentPage = 'overview';
let portalData = {
  cliente: null,
  projetos: [],
  tarefas: [],
  faturas: [],
  propostas: [],
  orcamentos: [],
  chamados: [],
  notificacoes: [],
  pagamento_info: {}
};

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const formatMoney = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const initials = (name) => String(name || 'CL').trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() || '').join('');
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

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo selecionado.'));
    reader.readAsDataURL(file);
  });
}

function safeJsonArray(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

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

async function loadPortalData() {
  portalData = await apiRequest('/portal/bootstrap');
  if (portalData?.organizacao) applyWhiteLabelBranding(portalData.organizacao);
  updateBadgesAndNotifications();
  return portalData;
}

function updateBadgesAndNotifications() {
  const pendProps = (portalData.propostas || []).filter((p) => p.status === 'enviada').length;
  const propBadge = $('#portal-prop-badge');
  if (propBadge) {
    propBadge.textContent = pendProps;
    propBadge.style.display = pendProps > 0 ? 'inline-block' : 'none';
  }

  const openTickets = (portalData.chamados || []).filter((c) => ['aberto', 'em_analise', 'aguardando_cliente'].includes(c.status)).length;
  const ticketBadge = $('#portal-ticket-badge');
  if (ticketBadge) {
    ticketBadge.textContent = openTickets;
    ticketBadge.style.display = openTickets > 0 ? 'inline-block' : 'none';
  }

  const unreadNotifs = (portalData.notificacoes || []).filter((n) => !n.lida);
  const dot = $('#portal-notif-count');
  if (dot) {
    dot.textContent = unreadNotifs.length;
    dot.style.display = unreadNotifs.length > 0 ? 'flex' : 'none';
  }
}

$('#portal-notif-btn')?.addEventListener('click', (e) => {
  e.stopPropagation();
  const pop = $('#portal-notif-popover');
  if (!pop) return;
  const isVisible = pop.style.display === 'block';
  if (isVisible) {
    pop.style.display = 'none';
    return;
  }
  const notifs = portalData.notificacoes || [];
  pop.innerHTML = `
    <div class="notif-popover-head">
      <b style="font-size:13.5px;">Notificações (${notifs.filter((n) => !n.lida).length} não lidas)</b>
      ${notifs.some((n) => !n.lida) ? `<button type="button" class="btn secondary" style="padding:4px 8px; font-size:11px;" id="portal-read-all-notifs">Marcar lidas</button>` : ''}
    </div>
    ${notifs.length ? notifs.map((n) => `
      <div class="notif-item ${n.lida ? '' : 'unread'}" data-pnotif-id="${n.id}" data-pnotif-link="${esc(n.link_pagina || 'overview')}">
        <div style="font-weight:700; font-size:13px; margin-bottom:2px;">${esc(n.titulo)}</div>
        <div class="muted" style="font-size:12px; line-height:1.4;">${esc(n.mensagem)}</div>
        <div style="font-size:10.5px; color:var(--muted); margin-top:4px;">${formatDateTime(n.criado_em)}</div>
      </div>
    `).join('') : '<div style="padding:20px; text-align:center;" class="muted">Nenhuma notificação recente.</div>'}
  `;
  pop.style.display = 'block';

  $('#portal-read-all-notifs')?.addEventListener('click', async () => {
    await apiRequest('/notificacoes/ler-todas', { method: 'POST' });
    await loadPortalData();
    pop.style.display = 'none';
  });

  pop.querySelectorAll('[data-pnotif-id]').forEach((el) => {
    el.onclick = async () => {
      const id = el.dataset.pnotifId;
      const link = el.dataset.pnotifLink;
      await apiRequest(`/notificacoes/${id}/lida`, { method: 'PATCH' }).catch(() => {});
      pop.style.display = 'none';
      await render(link);
    };
  });
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.notif-wrap')) {
    const pop = $('#portal-notif-popover');
    if (pop) pop.style.display = 'none';
  }
});

// ==================== MODAIS DO PORTAL DO CLIENTE ====================
window.portalOpenNewProjectRequestModal = () => {
  portalModalContainer.innerHTML = `
    <form id="portal-new-project-form">
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          </div>
          <div>
            <h2>Solicitar Novo Projeto ou Melhoria</h2>
            <p class="modal-subtitle">Envie o escopo desejado diretamente para nossa engenharia comercial</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-section-card">
          <div class="formgrid">
            <label>Tipo de Demanda *
              <select name="tipo_projeto" required>
                <option value="Desenvolvimento Web / Sistema">Desenvolvimento Web / Sistema</option>
                <option value="Novo Módulo / Evolução de Projeto">Novo Módulo / Evolução de Projeto</option>
                <option value="Aplicativo Mobile (iOS / Android)">Aplicativo Mobile (iOS / Android)</option>
                <option value="Integração de APIs / Automação">Integração de APIs / Automação</option>
                <option value="Consultoria / Infraestrutura Cloud">Consultoria / Infraestrutura Cloud</option>
              </select>
            </label>
            <label>Prioridade / Urgência *
              <select name="urgencia">
                <option value="normal">Normal (Planejada)</option>
                <option value="alta">Alta (Prioritária)</option>
                <option value="urgente">Urgente (Crítica)</option>
              </select>
            </label>
            <label>Título do Projeto / Demanda *
              <input type="text" name="titulo" required placeholder="Ex.: Módulo de Relatórios Financeiros">
            </label>
            <label>Orçamento Estimado (Opcional)
              <input type="text" name="orcamento_estimado" placeholder="Ex.: R$ 5.000 a R$ 10.000">
            </label>
          </div>
          <label class="field-full">Descrição Detalhada dos Objetivos e Requisitos *
            <textarea name="mensagem" rows="4" required placeholder="Descreva as funcionalidades esperadas, integrações necessárias e prazos desejados..."></textarea>
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Cancelar</button>
        <button type="submit" class="btn" id="portal-req-proj-btn">Enviar Solicitação</button>
      </div>
    </form>
  `;

  $('#portal-new-project-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#portal-req-proj-btn');
    const raw = Object.fromEntries(new FormData(e.target));
    btn.disabled = true;
    btn.textContent = 'Enviando...';
    try {
      await apiRequest('/portal/solicitar-projeto', {
        method: 'POST',
        body: JSON.stringify({
          tipo_projeto: raw.tipo_projeto,
          titulo: raw.titulo.trim(),
          urgencia: raw.urgencia,
          orcamento_estimado: raw.orcamento_estimado || null,
          mensagem: raw.mensagem.trim()
        })
      });
      portalDialog.close();
      showToast('Solicitação de novo projeto enviada com sucesso!', 'success');
      render('quotes');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao enviar solicitação', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Enviar Solicitação';
    }
  };

  portalDialog.showModal();
};

window.portalViewProposalModal = (propId) => {
  const prop = (portalData.propostas || []).find((p) => p.id === propId);
  if (!prop) return;
  const entregaveis = safeJsonArray(prop.entregaveis_json);
  const canDecide = ['enviada', 'ajuste_solicitado'].includes(prop.status);

  portalModalContainer.innerHTML = `
    <div class="modal-header">
      <div class="modal-header-main">
        <div class="modal-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="m9 15 2 2 4-4"></path></svg>
        </div>
        <div>
          <h2>Proposta ${esc(prop.codigo)} — ${esc(prop.titulo)}</h2>
          <p class="modal-subtitle">Validade: ${formatDate(prop.validade_ate)} • Prazo estimado: ${prop.prazo_dias} dias</p>
        </div>
      </div>
      <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
    </div>

    <div class="modal-body">
      <div class="grid" style="grid-template-columns:repeat(3, 1fr); gap:12px;">
        <div class="card" style="padding:14px;">
          <span class="muted" style="font-size:11.5px;">Investimento Total</span>
          <div style="font-size:20px; font-weight:800; color:var(--primary); margin-top:4px;">${formatMoney(prop.valor_total)}</div>
        </div>
        <div class="card" style="padding:14px;">
          <span class="muted" style="font-size:11.5px;">Parcelamento</span>
          <div style="font-size:16px; font-weight:700; margin-top:4px;">${prop.parcelas}x (${esc(prop.condicoes_pagamento || 'À combinar')})</div>
        </div>
        <div class="card" style="padding:14px;">
          <span class="muted" style="font-size:11.5px;">Status Atual</span>
          <div style="margin-top:6px;"><span class="badge ${esc(prop.status === 'aprovada' ? 'ativo' : 'pendente')}">${esc(prop.status).replace('_', ' ')}</span></div>
        </div>
      </div>

      <div class="modal-section-card">
        <div class="modal-section-title">Escopo Técnico &amp; Condições</div>
        <div style="white-space:pre-wrap; font-size:13.5px; line-height:1.55;">${esc(prop.escopo)}</div>
      </div>

      ${entregaveis.length ? `
        <div class="modal-section-card">
          <div class="modal-section-title">Cronograma de Entregáveis</div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            ${entregaveis.map((e, i) => `
              <div style="display:flex; justify-content:space-between; padding:8px 12px; background:var(--surface); border:1px solid var(--border); border-radius:8px; font-size:13px;">
                <span><b>Etapa ${i + 1}:</b> ${esc(e.titulo || e)}</span>
                <span class="muted">${e.prazo_dias ? `Dia ${e.prazo_dias}` : ''}</span>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${canDecide ? `
        <div class="modal-section-card">
          <div class="modal-section-title">Aprovação Digital da Proposta</div>
          <p class="muted" style="margin:0; font-size:12.5px;">Ao clicar em <b>Aprovar Proposta</b>, o projeto e o cronograma de entregas serão ativados automaticamente pela nossa equipe.</p>
          <label class="field-full">Observações ou Solicitação de Ajuste (Opcional)
            <textarea id="portal-prop-feedback" rows="2" placeholder="Caso deseje ajustar alguma cláusula ou prazo, descreva aqui..."></textarea>
          </label>
        </div>
      ` : `
        <div class="quote-reply-box" style="margin:0;">
          <b>Status: ${esc(prop.status).toUpperCase()}</b>
          ${prop.aprovado_por_cliente ? `<div style="font-size:12.5px; margin-top:4px;">Aprovado por ${esc(prop.aprovado_por_cliente)} em ${formatDateTime(prop.aprovado_em)}.</div>` : ''}
          ${prop.feedback_cliente ? `<div style="font-size:12.5px; margin-top:4px;">Parecer: ${esc(prop.feedback_cliente)}</div>` : ''}
        </div>
      `}
    </div>

    <div class="modal-footer" style="justify-content:space-between;">
      <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
      ${canDecide ? `
        <div style="display:flex; gap:10px;">
          <button type="button" class="btn secondary" id="portal-prop-rev-btn">Solicitar Revisão</button>
          <button type="button" class="btn" id="portal-prop-approve-btn">Aprovar Proposta Digitalmente</button>
        </div>
      ` : ''}
    </div>
  `;

  if (canDecide) {
    $('#portal-prop-rev-btn').onclick = async () => {
      const fb = $('#portal-prop-feedback').value.trim();
      if (!fb) {
        showToast('Informe no campo de observações o que deseja revisar na proposta.', 'error');
        return;
      }
      await apiRequest(`/portal/propostas/${prop.id}/decidir`, {
        method: 'POST',
        body: JSON.stringify({ decisao: 'ajuste_solicitado', feedback: fb })
      });
      portalDialog.close();
      showToast('Solicitação de revisão enviada para a equipe comercial.', 'info');
      render('proposals');
    };

    $('#portal-prop-approve-btn').onclick = async () => {
      const fb = $('#portal-prop-feedback').value.trim();
      const btn = $('#portal-prop-approve-btn');
      btn.disabled = true;
      btn.textContent = 'Ativando Projeto...';
      try {
        await apiRequest(`/portal/propostas/${prop.id}/decidir`, {
          method: 'POST',
          body: JSON.stringify({ decisao: 'aprovada', feedback: fb || 'Aprovado via Portal do Cliente' })
        });
        portalDialog.close();
        showToast('Proposta aprovada! Seu projeto foi ativado automaticamente.', 'success');
        render('projects');
      } catch (err) {
        showNoticeModal({ title: 'Erro ao aprovar proposta', message: err.message, variant: 'error' });
        btn.disabled = false;
        btn.textContent = 'Aprovar Proposta Digitalmente';
      }
    };
  }

  portalDialog.showModal();
};

window.portalViewProjectModal = (projId) => {
  const proj = (portalData.projetos || []).find((p) => p.id === projId);
  if (!proj) return;
  const tasks = (portalData.tarefas || []).filter((t) => t.projeto_id === proj.id);
  const doneCount = tasks.filter((t) => t.status === 'concluida').length;

  portalModalContainer.innerHTML = `
    <div class="modal-header">
      <div class="modal-header-main">
        <div class="modal-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path></svg>
        </div>
        <div>
          <h2>${esc(proj.titulo)}</h2>
          <p class="modal-subtitle">Início: ${formatDate(proj.data_inicio)} • Previsão de Entrega: ${formatDate(proj.data_entrega)}</p>
        </div>
      </div>
      <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
    </div>

    <div class="modal-body">
      <div class="modal-section-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
          <div>
            <span class="badge ${esc(proj.status)}">${esc(proj.status).replace('_', ' ')}</span>
            <span class="badge" style="margin-left:6px;">Homologação: ${esc(proj.aprovacao_cliente_status || 'pendente').replace('_', ' ')}</span>
          </div>
          <div style="font-weight:800; color:var(--primary);">Progresso Geral: ${proj.progresso}%</div>
        </div>
        <div style="height:8px; background:var(--surface); border-radius:999px; overflow:hidden; border:1px solid var(--border);">
          <div style="width:${proj.progresso}%; height:100%; background:#00B4D8;"></div>
        </div>
        ${proj.descricao ? `<p style="margin:0; font-size:13.5px; line-height:1.5;">${esc(proj.descricao)}</p>` : ''}
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          ${proj.url_homologacao ? `<a href="${esc(proj.url_homologacao)}" target="_blank" rel="noopener" class="btn secondary" style="text-decoration:none; font-size:12.5px;">Abrir Ambiente de Homologação</a>` : ''}
          ${proj.url_producao ? `<a href="${esc(proj.url_producao)}" target="_blank" rel="noopener" class="btn" style="text-decoration:none; font-size:12.5px;">Acessar Sistema em Produção</a>` : ''}
        </div>
      </div>

      <div class="modal-section-card">
        <div class="modal-section-title">Etapas &amp; Entregas do Cronograma (${doneCount}/${tasks.length} concluídas)</div>
        ${tasks.length ? `
          <div style="display:flex; flex-direction:column; gap:8px; max-height:220px; overflow-y:auto;">
            ${tasks.map((t) => `
              <div style="display:flex; justify-content:space-between; align-items:center; padding:9px 12px; background:var(--surface); border:1px solid var(--border); border-radius:8px; font-size:13px;">
                <div>
                  <span style="font-weight:600; ${t.status === 'concluida' ? 'text-decoration:line-through; color:var(--muted);' : ''}">${esc(t.titulo)}</span>
                  ${t.prazo ? `<div class="muted" style="font-size:11px;">Prazo: ${formatDate(t.prazo)}</div>` : ''}
                </div>
                <span class="badge ${esc(t.status)}">${esc(t.status)}</span>
              </div>
            `).join('')}
          </div>
        ` : '<p class="muted" style="margin:0; font-size:13px;">As etapas detalhadas estão sendo estruturadas pela equipe técnica.</p>'}
      </div>

      <div class="modal-section-card">
        <div class="modal-section-title">Homologação &amp; Aceite de Entrega</div>
        <p class="muted" style="margin:0; font-size:12.5px;">Valide o andamento ou registre observações para a equipe técnica da Nexus Code.</p>
        <textarea id="portal-homolog-obs" rows="2" placeholder="Comentários de homologação ou solicitação de ajustes...">${esc(proj.aprovacao_cliente_obs || '')}</textarea>
      </div>
    </div>

    <div class="modal-footer" style="justify-content:space-between;">
      <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
      <div style="display:flex; gap:10px;">
        <button type="button" class="btn secondary" id="portal-homolog-adj-btn">Solicitar Ajustes</button>
        <button type="button" class="btn" id="portal-homolog-ok-btn">Aprovar &amp; Homologar Entrega</button>
      </div>
    </div>
  `;

  const submitHomolog = async (decisao) => {
    const obs = $('#portal-homolog-obs').value.trim();
    try {
      await apiRequest(`/portal/projetos/${proj.id}/homologar`, {
        method: 'POST',
        body: JSON.stringify({ decisao, observacao: obs || null })
      });
      portalDialog.close();
      showToast(decisao === 'aprovado' ? 'Entrega homologada com sucesso!' : 'Solicitação de ajuste registrada.', 'success');
      render('projects');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao registrar parecer', message: err.message, variant: 'error' });
    }
  };

  $('#portal-homolog-adj-btn').onclick = () => submitHomolog('ajuste_solicitado');
  $('#portal-homolog-ok-btn').onclick = () => submitHomolog('aprovado');
  portalDialog.showModal();
};

window.portalOpenNewTicketModal = () => {
  const projs = portalData.projetos || [];
  portalModalContainer.innerHTML = `
    <form id="portal-new-ticket-form">
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
          </div>
          <div>
            <h2>Abrir Chamado de Suporte</h2>
            <p class="modal-subtitle">Atendimento técnico rastreado por protocolo e SLA</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-section-card">
          <div class="formgrid">
            <label>Assunto / Título *
              <input type="text" name="titulo" required placeholder="Ex.: Dúvida na emissão de relatório">
            </label>
            <label>Projeto Relacionado
              <select name="projeto_id">
                <option value="">-- Geral / Não vinculado --</option>
                ${projs.map((p) => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}
              </select>
            </label>
            <label>Categoria
              <select name="categoria">
                <option value="suporte_tecnico">Suporte Técnico / Dúvida</option>
                <option value="bug_correcao">Correção / Erro no Sistema</option>
                <option value="nova_funcionalidade">Solicitação de Melhoria</option>
                <option value="duvida_financeira">Financeiro / Faturamento</option>
              </select>
            </label>
            <label>Prioridade
              <select name="prioridade">
                <option value="baixa">Baixa (SLA 48h)</option>
                <option value="media" selected>Média (SLA 24h)</option>
                <option value="alta">Alta (SLA 8h)</option>
                <option value="critica">Crítica (SLA 4h)</option>
              </select>
            </label>
          </div>
          <label class="field-full">Descrição do Chamado *
            <textarea name="descricao" rows="4" required placeholder="Detalhe o ocorrido, passos para reproduzir ou sua solicitação..."></textarea>
          </label>
          <label class="field-full">Anexar Print ou Documento (Opcional, máx. 2,5 MB)
            <input type="file" id="portal-ticket-file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx">
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Cancelar</button>
        <button type="submit" class="btn" id="portal-ticket-save-btn">Registrar Chamado</button>
      </div>
    </form>
  `;

  $('#portal-new-ticket-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#portal-ticket-save-btn');
    const raw = Object.fromEntries(new FormData(e.target));
    const fileInp = $('#portal-ticket-file');

    btn.disabled = true;
    btn.textContent = 'Abrindo Chamado...';
    try {
      let anexo_nome = null;
      let anexo_data = null;
      if (fileInp?.files?.[0]) {
        const f = fileInp.files[0];
        if (f.size > 2.5 * 1024 * 1024) throw new Error('O anexo deve ter no máximo 2,5 MB.');
        anexo_nome = f.name;
        anexo_data = await readFileAsDataUrl(f);
      }
      await apiRequest('/portal/chamados', {
        method: 'POST',
        body: JSON.stringify({
          projeto_id: raw.projeto_id ? Number(raw.projeto_id) : null,
          titulo: raw.titulo.trim(),
          categoria: raw.categoria,
          prioridade: raw.prioridade,
          descricao: raw.descricao.trim(),
          anexo_nome,
          anexo_data
        })
      });
      portalDialog.close();
      showToast('Chamado aberto com sucesso!', 'success');
      render('tickets');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao abrir chamado', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Registrar Chamado';
    }
  };

  portalDialog.showModal();
};

window.portalOpenTicketThread = (ticketId) => {
  const ch = (portalData.chamados || []).find((c) => c.id === ticketId);
  if (!ch) return;
  const msgs = safeJsonArray(ch.mensagens_json);

  portalModalContainer.innerHTML = `
    <div class="modal-header">
      <div class="modal-header-main">
        <div class="modal-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <div>
          <h2>${esc(ch.protocolo)} — ${esc(ch.titulo)}</h2>
          <p class="modal-subtitle">Status: ${esc(ch.status).replace('_', ' ').toUpperCase()} • Prioridade: ${esc(ch.prioridade).toUpperCase()} • SLA: ${ch.sla_horas}h</p>
        </div>
      </div>
      <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
    </div>

    <div class="modal-body">
      <div class="ticket-thread" id="portal-ticket-thread-box">
        ${msgs.map((m) => `
          <div class="ticket-msg ${m.perfil === 'cliente' ? 'client' : 'staff'}">
            <div style="display:flex; justify-content:space-between; gap:12px; font-size:11px; color:var(--text-light); margin-bottom:4px;">
              <b>${esc(m.autor)} (${m.perfil === 'cliente' ? 'Você' : 'Equipe Nexus Code'})</b>
              <span>${esc(m.criado_em || '')}</span>
            </div>
            <div style="font-size:13.5px; line-height:1.5; white-space:pre-wrap;">${esc(m.texto)}</div>
            ${m.anexo_data ? `<div style="margin-top:6px;"><a href="${m.anexo_data}" download="${esc(m.anexo_nome || 'anexo')}" class="btn secondary" style="padding:4px 8px; font-size:11px; text-decoration:none;">Baixar ${esc(m.anexo_nome || 'Anexo')}</a></div>` : ''}
          </div>
        `).join('') || '<p class="muted">Nenhuma mensagem registrada.</p>'}
      </div>

      ${ch.status !== 'fechado' ? `
        <form id="portal-ticket-reply-form" style="display:flex; flex-direction:column; gap:10px;">
          <textarea id="portal-ticket-msg-txt" rows="3" required placeholder="Escreva sua resposta ou envie informações adicionais para a equipe técnica..."></textarea>
          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <input type="file" id="portal-ticket-reply-file" accept=".pdf,.png,.jpg,.jpeg" style="max-width:260px;">
            <button type="submit" class="btn" id="portal-ticket-send-btn">Enviar Mensagem</button>
          </div>
        </form>
      ` : '<div class="muted" style="font-size:13px;">Este chamado foi encerrado. Caso precise, abra um novo ticket.</div>'}
    </div>
  `;

  const box = $('#portal-ticket-thread-box');
  if (box) box.scrollTop = box.scrollHeight;

  $('#portal-ticket-reply-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('#portal-ticket-send-btn');
    const txt = $('#portal-ticket-msg-txt').value.trim();
    const fileInp = $('#portal-ticket-reply-file');
    if (!txt) return;

    btn.disabled = true;
    btn.textContent = 'Enviando...';
    try {
      let anexo_nome = null;
      let anexo_data = null;
      if (fileInp?.files?.[0]) {
        const f = fileInp.files[0];
        if (f.size > 2.5 * 1024 * 1024) throw new Error('O arquivo deve ter no máximo 2,5 MB.');
        anexo_nome = f.name;
        anexo_data = await readFileAsDataUrl(f);
      }
      await apiRequest(`/portal/chamados/${ch.id}/mensagens`, {
        method: 'POST',
        body: JSON.stringify({ texto: txt, anexo_nome, anexo_data })
      });
      await loadPortalData();
      window.portalOpenTicketThread(ch.id);
      showToast('Mensagem enviada!', 'success');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao enviar mensagem', message: err.message, variant: 'error' });
      btn.disabled = false;
      btn.textContent = 'Enviar Mensagem';
    }
  });

  portalDialog.showModal();
};

let portalMpPollTimer = null;

function stopPortalMpPolling() {
  if (portalMpPollTimer) {
    clearInterval(portalMpPollTimer);
    portalMpPollTimer = null;
  }
}

portalDialog?.addEventListener('close', stopPortalMpPolling);

window.portalPayInvoiceMP = async (faturaId, metodo = 'pix') => {
  stopPortalMpPolling();
  const baseFat = (portalData.faturas || []).find((f) => f.id === faturaId);

  portalModalContainer.innerHTML = `
    <div class="modal-header">
      <div class="modal-header-main">
        <div class="modal-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect width="20" height="14" x="2" y="5" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg>
        </div>
        <div>
          <h2>Pagamento Online — Mercado Pago</h2>
          <p class="modal-subtitle">${esc(baseFat?.descricao || 'Fatura #' + faturaId)} • ${formatMoney(baseFat?.valor || 0)}</p>
        </div>
      </div>
      <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
    </div>
    <div class="modal-body" id="mp-pay-modal-body" style="text-align:center; padding:28px 20px;">
      <div style="font-weight:700; font-size:15px; margin-bottom:6px;">Conectando ao Mercado Pago...</div>
      <div class="muted" style="font-size:13px;">Gerando cobrança segura com baixa automática.</div>
    </div>
  `;
  if (!portalDialog.open) portalDialog.showModal();

  const bodyEl = document.getElementById('mp-pay-modal-body');

  try {
    const fat = await apiRequest(`/faturas/${faturaId}/mercadopago`, {
      method: 'POST',
      body: JSON.stringify({ metodo })
    });

    if (fat.status === 'pago') {
      portalDialog.close();
      showToast('Esta fatura já consta como paga!', 'success');
      render('invoices');
      return;
    }

    const tabsHtml = `
      <div style="display:flex; gap:8px; justify-content:center; margin-bottom:18px;">
        <button type="button" class="btn ${metodo === 'pix' ? '' : 'secondary'}" style="padding:7px 14px; font-size:12.5px; ${metodo === 'pix' ? 'background:#00B4D8; color:#0A1D37; font-weight:800;' : ''}" onclick="window.portalPayInvoiceMP(${faturaId}, 'pix')">
          PIX Instantâneo (QR Code)
        </button>
        <button type="button" class="btn ${metodo === 'checkout_pro' ? '' : 'secondary'}" style="padding:7px 14px; font-size:12.5px; ${metodo === 'checkout_pro' ? 'background:#00B4D8; color:#0A1D37; font-weight:800;' : ''}" onclick="window.portalPayInvoiceMP(${faturaId}, 'checkout_pro')">
          Cartão de Crédito / Débito
        </button>
      </div>
    `;

    if (metodo === 'pix') {
      const qrImgHtml = fat.mp_qr_code_base64
        ? `<img src="data:image/png;base64,${fat.mp_qr_code_base64}" alt="QR Code PIX Mercado Pago" style="width:210px; height:210px; border-radius:12px; border:2px solid var(--border); padding:8px; background:#fff; margin:0 auto 14px; display:block;">`
        : (fat.mp_qr_code
          ? `<img src="https://api.qrserver.com/v1/create-qr-code/?size=210x210&data=${encodeURIComponent(fat.mp_qr_code)}" alt="QR Code PIX" style="width:210px; height:210px; border-radius:12px; border:2px solid var(--border); padding:8px; background:#fff; margin:0 auto 14px; display:block;">`
          : '');

      bodyEl.innerHTML = `
        ${tabsHtml}
        <div style="margin-bottom:14px;">
          <div style="font-size:26px; font-weight:900; color:var(--primary);">${formatMoney(fat.valor)}</div>
          <div class="muted" style="font-size:13px;">${esc(fat.descricao)}</div>
          ${fat.mp_order_id ? `<div style="font-size:11px; color:var(--muted); margin-top:3px;">Order MP: <code>${esc(fat.mp_order_id)}</code></div>` : ''}
        </div>

        ${qrImgHtml}

        ${fat.mp_qr_code ? `
          <div style="text-align:left; margin:12px 0;">
            <label style="display:block; font-size:12px; font-weight:700; margin-bottom:6px;">Código PIX Copia e Cola:</label>
            <div style="display:flex; gap:8px;">
              <input type="text" readonly value="${esc(fat.mp_qr_code)}" class="nc-input" id="mp-pix-copy-input" style="font-family:monospace; font-size:11.5px;">
              <button type="button" class="btn" id="mp-pix-copy-btn">Copiar</button>
            </div>
          </div>
        ` : `
          <div class="modal-section-card" style="text-align:center; margin:12px 0;">
            <div style="font-size:13px; font-weight:700; margin-bottom:6px;">Order PIX registrada no Mercado Pago</div>
            <div class="muted" style="font-size:12px; margin-bottom:10px;">
              ${fat.mp_checkout_url ? 'Clique abaixo para abrir o QR Code / comprovante oficial no Mercado Pago.' : 'Caso o aplicativo bancário não leia o código acima, utilize a aba "Cartão de Crédito / Débito" ao lado.'}
            </div>
            ${fat.mp_checkout_url ? `<a href="${esc(fat.mp_checkout_url)}" target="_blank" rel="noopener" class="btn" style="text-decoration:none; background:#00B4D8; color:#0A1D37; font-weight:800;">Abrir Pagamento Mercado Pago ↗</a>` : ''}
          </div>
        `}

        <div style="display:flex; align-items:center; justify-content:center; gap:8px; margin-top:14px; font-size:12px; color:var(--primary); font-weight:600;">
          <span>● Aguardando confirmação automática do pagamento...</span>
        </div>
        <div style="margin-top:14px; display:flex; justify-content:center; gap:10px;">
          <button type="button" class="btn secondary" id="mp-check-now-btn">Já paguei — Verificar agora</button>
          <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
        </div>
      `;

      document.getElementById('mp-pix-copy-btn')?.addEventListener('click', () => {
        const inp = document.getElementById('mp-pix-copy-input');
        navigator.clipboard?.writeText(inp?.value || '');
        showToast('Código PIX Copia e Cola copiado!', 'success');
      });
    } else {
      bodyEl.innerHTML = `
        ${tabsHtml}
        <div style="margin-bottom:16px;">
          <div style="font-size:26px; font-weight:900; color:var(--primary);">${formatMoney(fat.valor)}</div>
          <div class="muted" style="font-size:13px;">${esc(fat.descricao)}</div>
        </div>
        <div class="modal-section-card" style="text-align:center;">
          <p style="margin:0 0 14px; font-size:13.5px;">Finalize o pagamento com <b>Cartão de Crédito (em até 12x)</b>, <b>Débito</b> ou <b>Saldo Mercado Pago</b> no ambiente seguro:</p>
          ${fat.mp_checkout_url
            ? `<a href="${esc(fat.mp_checkout_url)}" target="_blank" rel="noopener" class="btn" style="text-decoration:none; background:#00B4D8; color:#0A1D37; font-weight:800; padding:11px 20px;">Pagar Agora no Mercado Pago ↗</a>`
            : '<div class="muted">Link de checkout indisponível.</div>'}
        </div>
        <div style="margin-top:14px; display:flex; justify-content:center; gap:10px;">
          <button type="button" class="btn secondary" id="mp-check-now-btn">Verificar Confirmação</button>
          <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
        </div>
      `;
    }

    const checkPaymentStatus = async (manual = false) => {
      try {
        const st = await apiRequest(`/faturas/${faturaId}/mercadopago/status`);
        if (st && st.status === 'pago') {
          stopPortalMpPolling();
          portalDialog.close();
          showToast('Pagamento confirmado automaticamente via Mercado Pago!', 'success');
          render('invoices');
          return true;
        }
        if (manual) {
          showToast('Pagamento ainda pendente de compensação. Aguarde alguns segundos.', 'info');
        }
      } catch (_) {}
      return false;
    };

    document.getElementById('mp-check-now-btn')?.addEventListener('click', () => checkPaymentStatus(true));
    portalMpPollTimer = setInterval(() => {
      if (!portalDialog.open) {
        stopPortalMpPolling();
        return;
      }
      checkPaymentStatus(false);
    }, 4500);
  } catch (err) {
    bodyEl.innerHTML = `
      <div style="display:flex; gap:8px; justify-content:center; margin-bottom:18px;">
        <button type="button" class="btn ${metodo === 'pix' ? '' : 'secondary'}" style="padding:7px 14px; font-size:12.5px;" onclick="window.portalPayInvoiceMP(${faturaId}, 'pix')">
          PIX Instantâneo (QR Code)
        </button>
        <button type="button" class="btn ${metodo === 'checkout_pro' ? '' : 'secondary'}" style="padding:7px 14px; font-size:12.5px;" onclick="window.portalPayInvoiceMP(${faturaId}, 'checkout_pro')">
          Cartão de Crédito / Débito
        </button>
      </div>
      <div style="color:var(--danger); font-weight:700; margin-bottom:8px;">Não foi possível iniciar o pagamento</div>
      <div class="muted" style="font-size:13px; margin-bottom:16px;">${esc(err.message)}</div>
      <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
    `;
  }
};

window.portalOpenOfficialReceiptModal = async (faturaId) => {
  portalModalContainer.innerHTML = `
    <div class="modal-header">
      <div class="modal-header-main">
        <div class="modal-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="m9 15 2 2 4-4"></path></svg>
        </div>
        <div>
          <h2>Comprovante Oficial de Pagamento</h2>
          <p class="modal-subtitle">Gerando recibo eletrônico autenticado...</p>
        </div>
      </div>
      <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
    </div>
    <div class="modal-body" style="text-align:center; padding:30px;">
      <div class="muted">Carregando dados da transação...</div>
    </div>
  `;
  if (!portalDialog.open) portalDialog.showModal();

  try {
    const rec = await apiRequest(`/faturas/${faturaId}/recibo-digital`);
    const b = rec.branding || {};
    const em = rec.emissor || {};
    const pg = rec.pagador || {};
    const ft = rec.fatura || {};
    const txId = ft.mp_order_id || ft.mp_payment_id || rec.numero_comprovante;

    portalModalContainer.innerHTML = `
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="m9 15 2 2 4-4"></path></svg>
          </div>
          <div>
            <h2>Comprovante de Pagamento &bull; ${esc(rec.numero_comprovante)}</h2>
            <p class="modal-subtitle">Recibo digital emitido automaticamente sem necessidade de anexo manual</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
      </div>

      <div class="modal-body">
        <div id="receipt-printable" class="digital-receipt-card">
          <div class="digital-receipt-banner">
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="width:42px; height:42px; border-radius:11px; background:#061224; border:1.5px solid #00B4D8; display:flex; align-items:center; justify-content:center; padding:6px;">
                <svg viewBox="0 0 320 220" width="28" height="20"><g transform="translate(160, 110)"><path d="M -80 80 L -80 -80 L 80 80 L 80 -80" fill="none" stroke="#FFFFFF" stroke-width="28" stroke-linecap="square"/><circle cx="0" cy="0" r="20" fill="#00B4D8"/><circle cx="0" cy="0" r="8" fill="#0A1D37"/></g></svg>
              </div>
              <div>
                <div style="font-size:18px; font-weight:900; letter-spacing:0.04em; color:#FFFFFF;">${esc(b.nome_plataforma || 'NEXUS CODE')}</div>
                <div style="font-size:10px; font-weight:800; letter-spacing:0.28em; color:#00B4D8;">${esc(b.subtitulo_plataforma || 'BRASIL')}</div>
              </div>
            </div>
            <div style="text-align:right;">
              <span class="receipt-badge-paid">&#10003; Pagamento Confirmado</span>
              <div style="font-size:12px; color:#cbd5e1; margin-top:6px;">Recibo Nº <b>${esc(rec.numero_comprovante)}</b></div>
            </div>
          </div>

          <div style="padding:22px 24px;">
            <div class="receipt-amount-highlight">
              <div>
                <div style="font-size:11px; font-weight:800; text-transform:uppercase; color:#0284C7; letter-spacing:0.05em;">Valor Total Liquidado</div>
                <div style="font-size:28px; font-weight:900; color:#0A1D37;">${esc(ft.valor_formatado)}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:12px; color:#475569;">Data e Hora da Liquidação</div>
                <div style="font-size:14px; font-weight:800; color:#0A1D37;">${esc(ft.pago_em)}</div>
                <div style="font-size:11.5px; color:#0284C7; font-weight:700;">Via ${esc(ft.forma_pagamento)}</div>
              </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px; font-size:12.5px;">
              <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                <div style="font-size:10.5px; font-weight:800; text-transform:uppercase; color:#64748b; margin-bottom:4px;">Recebedor (Favorecido)</div>
                <div style="font-weight:800; color:#0A1D37;">${esc(em.razao_social)}</div>
                <div style="color:#475569; margin-top:2px;">CNPJ: ${esc(em.cnpj)}</div>
                <div style="color:#475569;">${esc(em.localizacao)}</div>
              </div>
              <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px;">
                <div style="font-size:10.5px; font-weight:800; text-transform:uppercase; color:#64748b; margin-bottom:4px;">Pagador (Cliente)</div>
                <div style="font-weight:800; color:#0A1D37;">${esc(pg.nome_empresa)}</div>
                <div style="color:#475569; margin-top:2px;">Responsável: ${esc(pg.contato_nome)}</div>
                <div style="color:#475569;">${esc(pg.email)}</div>
              </div>
            </div>

            <table class="holerite-slip-table" style="margin:0;">
              <thead>
                <tr>
                  <th>Descrição do Pagamento</th>
                  <th>Vencimento</th>
                  <th>ID Transação</th>
                  <th>Valor Pago</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><b>${esc(ft.descricao)}</b>${ft.projeto ? `<div style="font-size:11.5px; color:#64748b;">Projeto: ${esc(ft.projeto)}</div>` : ''}</td>
                  <td>${esc(ft.vencimento)}</td>
                  <td style="font-family:monospace; font-size:11.5px;">${esc(txId)}</td>
                  <td style="font-weight:800; color:#15803d;">${esc(ft.valor_formatado)}</td>
                </tr>
              </tbody>
            </table>

            <div class="receipt-auth-box">
              <div>
                <div style="font-size:11px; font-weight:800; text-transform:uppercase;">Autenticação Eletrônica de Quitação</div>
                <div style="font-size:11.5px; opacity:0.9;">Documento gerado automaticamente pelo gateway financeiro integrado.</div>
              </div>
              <div style="font-family:monospace; font-size:13px; font-weight:900; letter-spacing:0.05em;">
                ${esc(rec.codigo_autenticacao)}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        ${ft.mp_checkout_url ? `<a href="${esc(ft.mp_checkout_url)}" target="_blank" rel="noopener" class="btn secondary" style="text-decoration:none;">Comprovante Mercado Pago ↗</a>` : ''}
        <button type="button" class="btn secondary" onclick="window.print()">Imprimir / Salvar PDF</button>
        <button type="button" class="btn" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
      </div>
    `;
  } catch (err) {
    portalModalContainer.innerHTML = `
      <div class="modal-header">
        <div class="modal-header-main"><h2>Comprovante de Pagamento</h2></div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
      </div>
      <div class="modal-body">
        <div style="color:var(--danger); font-weight:700;">${esc(err.message)}</div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Fechar</button>
      </div>
    `;
  }
};

window.portalOpenInvoiceReceiptModal = (fatId) => {
  const fat = (portalData.faturas || []).find((f) => f.id === fatId);
  if (!fat) return;
  const pix = portalData.pagamento_info || {};

  portalModalContainer.innerHTML = `
    <form id="portal-receipt-form">
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect width="20" height="14" x="2" y="5" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg>
          </div>
          <div>
            <h2>Pagamento &amp; Comprovante — ${esc(fat.descricao)}</h2>
            <p class="modal-subtitle">Valor: ${formatMoney(fat.valor)} • Vencimento: ${formatDate(fat.vencimento)}</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('portal-dialog').close()">&times;</button>
      </div>

      <div class="modal-body">
        <div class="modal-section-card">
          <div class="modal-section-title">Enviar Comprovante de Pagamento</div>
          <label class="field-full">Selecione o Arquivo (PDF, PNG ou JPG, máx. 2,5 MB) *
            <input type="file" id="portal-receipt-file" accept=".pdf,.png,.jpg,.jpeg" required>
          </label>
          <label class="field-full">Observações (Opcional)
            <input type="text" name="observacoes" value="${esc(fat.observacoes || '')}" placeholder="Ex.: Pago via PIX em ${new Date().toLocaleDateString('pt-BR')}">
          </label>
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="document.getElementById('portal-dialog').close()">Cancelar</button>
        <button type="submit" class="btn" id="portal-receipt-save-btn">Enviar Comprovante</button>
      </div>
    </form>
  `;

  $('#portal-receipt-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#portal-receipt-save-btn');
    const fileInp = $('#portal-receipt-file');
    const obs = new FormData(e.target).get('observacoes');
    if (!fileInp?.files?.[0]) return;

    btn.disabled = true;
    btn.textContent = 'Enviando...';
    try {
      const f = fileInp.files[0];
      if (f.size > 2.5 * 1024 * 1024) throw new Error('O comprovante deve ter no máximo 2,5 MB.');
      const dataUrl = await readFileAsDataUrl(f);
      await apiRequest(`/portal/faturas/${fat.id}/comprovante`, {
        method: 'POST',
        body: JSON.stringify({
          comprovante_nome: f.name,
          comprovante_data: dataUrl,
          observacoes: obs || null
        })
      });
      portalDialog.close();
      showToast('Comprovante enviado! Nossa equipe financeira fará a baixa.', 'success');
      render('invoices');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao enviar comprovante', message: err.message, variant: 'error' });
      btn.disabled = false;
      btn.textContent = 'Enviar Comprovante';
    }
  };

  portalDialog.showModal();
};

// ==================== RENDERIZAÇÃO DAS TELAS DO PORTAL ====================
async function render(page) {
  currentPage = page;
  $$('[data-page]').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
  side?.classList.remove('open');
  backdrop?.classList.remove('open');

  await loadPortalData();

  if (page === 'overview') {
    const projs = portalData.projetos || [];
    const props = portalData.propostas || [];
    const fats = portalData.faturas || [];
    const tickets = portalData.chamados || [];
    const activeProjs = projs.filter((p) => !['concluido', 'cancelado'].includes(p.status));
    const openProps = props.filter((p) => ['enviada', 'ajuste_solicitado'].includes(p.status));
    const openFats = fats.filter((f) => ['pendente', 'atrasado'].includes(f.status));
    const openTickets = tickets.filter((t) => ['aberto', 'em_analise', 'aguardando_cliente'].includes(t.status));

    view.innerHTML = `
      <div class="portal-hero">
        <div>
          <span style="font-size:11.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#00B4D8;">Portal Corporativo do Cliente</span>
          <h1 style="margin:4px 0 6px; font-size:24px;">Bem-vindo, ${esc(user?.nome)}</h1>
          <p style="margin:0; font-size:13.5px; color:#cbd5e1;">Acompanhe seus projetos em tempo real, aprove propostas, gerencie faturas e fale diretamente com nossa engenharia.</p>
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button type="button" class="btn secondary" onclick="window.portalOpenNewTicketModal()">+ Abrir Chamado</button>
          <button type="button" class="btn" style="background:#00B4D8; color:#0A1D37; font-weight:800;" onclick="window.portalOpenNewProjectRequestModal()">+ Solicitar Novo Projeto</button>
        </div>
      </div>

      <div class="grid" style="margin-bottom:20px;">
        <div class="card metric" style="cursor:pointer;" onclick="window.portalGo('projects')">
          <span class="title">Projetos em Andamento</span>
          <strong>${activeProjs.length}</strong>
          <span class="pill-info">${projs.length} projeto(s) no total</span>
        </div>
        <div class="card metric" style="cursor:pointer;" onclick="window.portalGo('proposals')">
          <span class="title">Propostas Pendentes</span>
          <strong>${openProps.length}</strong>
          <span class="pill-info">${props.length} proposta(s) recebida(s)</span>
        </div>
        <div class="card metric" style="cursor:pointer;" onclick="window.portalGo('invoices')">
          <span class="title">Faturas em Aberto</span>
          <strong>${formatMoney(openFats.reduce((a, f) => a + Number(f.valor || 0), 0))}</strong>
          <span class="pill-info">${openFats.length} cobrança(s) pendente(s)</span>
        </div>
        <div class="card metric" style="cursor:pointer;" onclick="window.portalGo('tickets')">
          <span class="title">Chamados de Suporte</span>
          <strong>${openTickets.length}</strong>
          <span class="pill-info">${tickets.length} ticket(s) registrado(s)</span>
        </div>
      </div>

      <div class="dashboard-panels">
        <div class="card">
          <div class="toolbar" style="margin-bottom:10px;">
            <h3 style="margin:0; font-size:16px;">Meus Projetos</h3>
            <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.portalGo('projects')">Ver detalhes</button>
          </div>
          ${projs.slice(0, 4).map((p) => `
            <div class="app-ticket" style="cursor:pointer;" onclick="window.portalViewProjectModal(${p.id})">
              <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:6px;">
                <b>${esc(p.titulo)}</b>
                <span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span>
              </div>
              <div style="display:flex; align-items:center; gap:10px;">
                <div style="flex:1; height:6px; background:var(--surface2); border-radius:4px; overflow:hidden; border:1px solid var(--border);">
                  <div style="width:${p.progresso}%; height:100%; background:#00B4D8;"></div>
                </div>
                <span style="font-size:12px; font-weight:700;">${p.progresso}%</span>
              </div>
            </div>
          `).join('') || '<p class="muted">Nenhum projeto ativo no momento. Clique em "+ Solicitar Novo Projeto" para iniciar.</p>'}
        </div>

        <div class="card">
          <div class="toolbar" style="margin-bottom:10px;">
            <h3 style="margin:0; font-size:16px;">Propostas &amp; Aprovações</h3>
            <button class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.portalGo('proposals')">Ver todas</button>
          </div>
          ${props.slice(0, 4).map((pr) => `
            <div class="app-ticket" style="display:flex; justify-content:space-between; align-items:center; gap:12px; cursor:pointer;" onclick="window.portalViewProposalModal(${pr.id})">
              <div>
                <b>${esc(pr.codigo)} — ${esc(pr.titulo)}</b>
                <div class="muted" style="font-size:12px;">Valor: ${formatMoney(pr.valor_total)} • Prazo: ${pr.prazo_dias} dias</div>
              </div>
              <span class="badge ${esc(pr.status === 'aprovada' ? 'ativo' : 'pendente')}">${esc(pr.status).replace('_', ' ')}</span>
            </div>
          `).join('') || '<p class="muted">Nenhuma proposta comercial pendente.</p>'}
        </div>
      </div>
    `;
  } else if (page === 'proposals') {
    const items = portalData.propostas || [];
    view.innerHTML = `
      <div class="toolbar">
        <div>
          <h1>Propostas Comerciais &amp; Contratos</h1>
          <span class="muted">Analise escopos, cronogramas e aprove propostas digitalmente</span>
        </div>
        <button type="button" class="btn" onclick="window.portalOpenNewProjectRequestModal()">+ Solicitar Nova Proposta</button>
      </div>
      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Código</th><th>Título</th><th>Investimento</th><th>Condições</th><th>Validade</th><th>Status</th><th>Ações</th></tr></thead>
          <tbody>
            ${items.map((p) => `
              <tr>
                <td><b>${esc(p.codigo)}</b></td>
                <td><b>${esc(p.titulo)}</b><div class="muted" style="font-size:12px;">Prazo: ${p.prazo_dias} dias</div></td>
                <td style="font-weight:800; color:var(--primary);">${formatMoney(p.valor_total)}</td>
                <td>${p.parcelas}x • ${esc(p.condicoes_pagamento || '-')}</td>
                <td>${formatDate(p.validade_ate)}</td>
                <td><span class="badge ${esc(p.status === 'aprovada' ? 'ativo' : 'pendente')}">${esc(p.status).replace('_', ' ')}</span></td>
                <td>
                  <button type="button" class="btn" style="padding:6px 12px; font-size:12px;" onclick="window.portalViewProposalModal(${p.id})">
                    ${['enviada', 'ajuste_solicitado'].includes(p.status) ? 'Analisar & Aprovar' : 'Visualizar'}
                  </button>
                </td>
              </tr>
            `).join('') || '<tr><td colspan="7" style="text-align:center; padding:32px;" class="muted">Nenhuma proposta comercial emitida para sua conta até o momento.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
  } else if (page === 'projects') {
    const items = portalData.projetos || [];
    view.innerHTML = `
      <div class="toolbar">
        <div><h1>Meus Projetos</h1><span class="muted">Acompanhamento de etapas, links de homologação e aceite de entregas</span></div>
        <button type="button" class="btn" onclick="window.portalOpenNewProjectRequestModal()">+ Solicitar Novo Projeto</button>
      </div>
      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Projeto</th><th>Status</th><th>Progresso</th><th>Homologação</th><th>Entrega Prevista</th><th>Ações</th></tr></thead>
          <tbody>
            ${items.map((p) => `
              <tr>
                <td>
                  <b>${esc(p.titulo)}</b>
                  <div style="display:flex; gap:8px; margin-top:4px;">
                    ${p.url_homologacao ? `<a href="${esc(p.url_homologacao)}" target="_blank" rel="noopener" style="font-size:11.5px; color:var(--primary);">Link Homologação ↗</a>` : ''}
                    ${p.url_producao ? `<a href="${esc(p.url_producao)}" target="_blank" rel="noopener" style="font-size:11.5px; color:var(--ok);">Link Produção ↗</a>` : ''}
                  </div>
                </td>
                <td><span class="badge ${esc(p.status)}">${esc(p.status).replace('_', ' ')}</span></td>
                <td style="min-width:130px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <div style="flex:1; height:6px; background:var(--surface2); border-radius:4px; overflow:hidden; border:1px solid var(--border);">
                      <div style="width:${p.progresso}%; height:100%; background:var(--primary);"></div>
                    </div>
                    <span style="font-size:12px; font-weight:700;">${p.progresso}%</span>
                  </div>
                </td>
                <td><span class="badge ${p.aprovacao_cliente_status === 'aprovado' ? 'ativo' : 'pendente'}">${esc(p.aprovacao_cliente_status || 'pendente').replace('_', ' ')}</span></td>
                <td>${formatDate(p.data_entrega)}</td>
                <td>
                  <button type="button" class="btn secondary" style="padding:6px 12px; font-size:12px;" onclick="window.portalViewProjectModal(${p.id})">Etapas &amp; Homologar</button>
                </td>
              </tr>
            `).join('') || '<tr><td colspan="6" style="text-align:center; padding:32px;" class="muted">Nenhum projeto ativo vinculado a esta conta.</td></tr>'}
          </tbody>
        </table>
      </div>`;
  } else if (page === 'quotes') {
    const items = portalData.orcamentos || [];
    view.innerHTML = `
      <div class="toolbar">
        <div><h1>Solicitações &amp; Novos Projetos</h1><span class="muted">Solicite novos sistemas ou melhorias e acompanhe o retorno comercial</span></div>
        <button type="button" class="btn" onclick="window.portalOpenNewProjectRequestModal()">+ Nova Solicitação de Projeto</button>
      </div>
      ${items.map((q) => `
        <div class="card" style="margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px;">
            <div>
              <b>${esc(q.tipo_projeto || 'Orçamento')}</b>
              <span class="muted" style="font-size:12px;"> • Enviado em ${formatDateTime(q.criado_em)}</span>
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
      `).join('') || '<div class="card"><p class="muted">Nenhuma solicitação registrada para esta conta. Clique em "+ Nova Solicitação de Projeto" acima.</p></div>'}`;
  } else if (page === 'tickets') {
    const items = portalData.chamados || [];
    view.innerHTML = `
      <div class="toolbar">
        <div><h1>Suporte &amp; Chamados</h1><span class="muted">Atendimento técnico direto com protocolo, SLA e histórico de mensagens</span></div>
        <button type="button" class="btn" onclick="window.portalOpenNewTicketModal()">+ Abrir Novo Chamado</button>
      </div>
      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Protocolo</th><th>Assunto</th><th>Categoria</th><th>Prioridade</th><th>Status</th><th>Atualizado em</th><th>Ações</th></tr></thead>
          <tbody>
            ${items.map((c) => `
              <tr>
                <td><b>${esc(c.protocolo)}</b></td>
                <td><b>${esc(c.titulo)}</b></td>
                <td>${esc(c.categoria).replace('_', ' ')}</td>
                <td><span class="prio-badge prio-${esc(c.prioridade)}">${esc(c.prioridade)}</span></td>
                <td><span class="badge ${c.status === 'resolvido' || c.status === 'fechado' ? 'ativo' : 'pendente'}">${esc(c.status).replace('_', ' ')}</span></td>
                <td>${formatDateTime(c.atualizado_em || c.criado_em)}</td>
                <td>
                  <button type="button" class="btn secondary" style="padding:6px 12px; font-size:12px;" onclick="window.portalOpenTicketThread(${c.id})">Abrir Conversa</button>
                </td>
              </tr>
            `).join('') || '<tr><td colspan="7" style="text-align:center; padding:32px;" class="muted">Nenhum chamado de suporte registrado.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
  } else if (page === 'invoices') {
    const items = portalData.faturas || [];
    view.innerHTML = `
      <div class="toolbar"><div><h1>Minhas Faturas &amp; Pagamentos</h1><span class="muted">Pagamento online automatizado via Mercado Pago (PIX ou Cartão) e histórico de faturas</span></div></div>

      <div class="card table-wrap">
        <table class="table">
          <thead><tr><th>Descrição</th><th>Valor</th><th>Vencimento</th><th>Status</th><th>Comprovante</th><th>Ações</th></tr></thead>
          <tbody>
            ${items.map((f) => `
              <tr>
                <td><b>${esc(f.descricao)}</b></td>
                <td style="font-weight:800;">${formatMoney(f.valor)}</td>
                <td>${formatDate(f.vencimento)}</td>
                <td><span class="badge ${esc(f.status)}">${esc(f.status)}</span></td>
                <td>
                  ${f.status === 'pago'
                    ? `
                      <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px; color:var(--ok); border-color:rgba(22,163,74,0.35); font-weight:700;" onclick="window.portalOpenOfficialReceiptModal(${f.id})">
                        ✓ Comprovante Oficial
                      </button>
                      ${f.comprovante_data ? `<div style="margin-top:4px;"><a href="${f.comprovante_data}" download="${esc(f.comprovante_nome || 'comprovante')}" style="color:var(--primary); font-size:11.5px;">Anexo: ${esc(f.comprovante_nome || 'Arquivo')}</a></div>` : ''}
                    `
                    : (f.comprovante_data
                      ? `<a href="${f.comprovante_data}" download="${esc(f.comprovante_nome || 'comprovante')}" style="color:var(--ok); font-weight:600; font-size:12.5px;">✓ ${esc(f.comprovante_nome || 'Enviado')}</a>`
                      : '<span class="muted" style="font-size:12px;">Aguardando pagamento</span>')}
                </td>
                <td>
                  ${f.status !== 'pago'
                    ? `
                      <button type="button" class="btn secondary" style="padding:6px 12px; font-size:12px;" onclick="window.portalOpenInvoiceReceiptModal(${f.id})">Anexar Comprovante (Manual)</button>
                      <button type="button" class="btn" style="padding:6px 12px; font-size:12px; background:#00B4D8; color:#0A1D37; font-weight:800;" onclick="window.portalPayInvoiceMP(${f.id})">Pagar com PIX/Cartão</button>
                    `
                    : `
                      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                        <button type="button" class="btn" style="padding:6px 12px; font-size:12px; background:#00B4D8; color:#0A1D37; font-weight:800;" onclick="window.portalOpenOfficialReceiptModal(${f.id})">Ver Comprovante / PDF</button>
                      </div>
                    `}
                </td>
              </tr>
            `).join('') || '<tr><td colspan="6" style="text-align:center; padding:32px;" class="muted">Nenhuma fatura emitida para esta conta.</td></tr>'}
          </tbody>
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
                    Os dados pessoais e profissionais informados são protegidos por criptografia e utilizados exclusivamente pela <b>Nexus Code</b> para atendimento, faturamento e execução dos projetos contratados.
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

window.portalGo = (target) => render(target);
$$('[data-page]').forEach((b) => (b.onclick = () => render(b.dataset.page)));

if (!getToken()) {
  window.location.href = '../login.html';
} else {
  apiRequest('/auth/me')
    .then((u) => {
      user = u;
      $('#portal-user').textContent = u.nome;
      $('#portal-initials').textContent = initials(u.nome);
      const qp = new URLSearchParams(window.location.search);
      const mpStatus = qp.get('mp_status');
      const mpRef = qp.get('ref') || '';
      if (mpStatus) {
        window.history.replaceState({}, document.title, window.location.pathname);
        render('invoices').then(async () => {
          if (mpStatus === 'approved') {
            const fatIdMatch = mpRef.match(/^FATURA[-:](\d+)$/i);
            if (fatIdMatch) {
              await apiRequest(`/faturas/${fatIdMatch[1]}/mercadopago/status`).catch(() => {});
              await render('invoices');
            }
            showToast('Pagamento confirmado com sucesso via Mercado Pago!', 'success');
          } else if (mpStatus === 'pending') {
            showToast('Pagamento em processamento. A fatura será baixada assim que compensar.', 'info');
          } else if (mpStatus === 'failure') {
            showToast('O pagamento não foi concluído. Você pode tentar novamente quando desejar.', 'error');
          }
        });
      } else {
        render('overview');
      }
    })
    .catch(() => { clearSession(); window.location.href = '../login.html'; });
}
