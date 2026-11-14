import { apiRequest, applyWhiteLabelBranding, setSession } from './config.js';
import { showToast, showNoticeModal, showConfirmModal } from './ui.js';

const esc = (v) =>
  String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

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

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo selecionado.'));
    reader.readAsDataURL(file);
  });
}

export function exportRowsToCsv(filename, headers, rows) {
  const escapeCell = (val) => {
    const s = String(val ?? '').replace(/"/g, '""');
    return `"${s}"`;
  };
  const csvContent = [
    headers.map(escapeCell).join(';'),
    ...rows.map((r) => r.map(escapeCell).join(';'))
  ].join('\n');

  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast(`Relatório "${filename}" exportado com sucesso!`, 'success');
}

// ==================== 1. TIMESHEET & RENTABILIDADE DE PROJETOS ====================
export async function renderTimesheetView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const projMap = Object.fromEntries((cache.projetos || []).map((p) => [p.id, p]));
  const userMap = Object.fromEntries((cache.usuarios || []).map((u) => [u.id, u]));
  const taskMap = Object.fromEntries((cache.tarefas || []).map((t) => [t.id, t]));
  const apontamentos = cache.apontamentos || [];
  const despesas = cache.despesas || [];

  // Cálculo de rentabilidade por projeto
  const profRows = (cache.projetos || []).map((p) => {
    const logs = apontamentos.filter((a) => a.projeto_id === p.id);
    const horasReais = logs.reduce((acc, a) => acc + Number(a.horas || 0), 0);
    const custoMaoObra = logs.reduce((acc, a) => acc + Number(a.horas || 0) * Number(a.custo_hora_snapshot || 0), 0);
    const custoDireto = despesas
      .filter((d) => d.projeto_id === p.id && d.status !== 'cancelado')
      .reduce((acc, d) => acc + Number(d.valor || 0), 0);
    const receita = Number(p.valor_total || 0);
    const custoTotal = custoMaoObra + custoDireto;
    const lucro = receita - custoTotal;
    const margem = receita > 0 ? ((lucro / receita) * 100).toFixed(1) : '0.0';
    return { p, horasReais, custoMaoObra, custoDireto, custoTotal, receita, lucro, margem };
  });

  const filteredLogs = apontamentos.filter((a) => {
    const pTitle = projMap[a.projeto_id]?.titulo || '';
    const uName = userMap[a.usuario_id]?.nome || '';
    return matchSearch([pTitle, uName, a.descricao, a.data_trabalho]);
  });

  const totalHoras = filteredLogs.reduce((acc, a) => acc + Number(a.horas || 0), 0);
  const totalCusto = filteredLogs.reduce((acc, a) => acc + Number(a.horas || 0) * Number(a.custo_hora_snapshot || 0), 0);

  window.nexusOpenNewTimesheetModal = () => {
    const projs = cache.projetos || [];
    const tasks = cache.tarefas || [];
    const staff = (cache.usuarios || []).filter((u) => u.perfil !== 'cliente');
    const todayStr = new Date().toISOString().slice(0, 10);

    holeriteContainer.innerHTML = `
      <form id="new-timesheet-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.clock}</div>
            <div>
              <h2>Apontar Horas Trabalhadas (Timesheet)</h2>
              <p class="modal-subtitle">Registre horas dedicadas para cálculo de custo e margem do projeto</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Projeto *
                <select name="projeto_id" required>
                  <option value="">Selecione o projeto</option>
                  ${projs.map((p) => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}
                </select>
              </label>
              <label>Tarefa Vinculada (Opcional)
                <select name="tarefa_id">
                  <option value="">-- Geral do Projeto --</option>
                  ${tasks.map((t) => `<option value="${t.id}">#${t.id} - ${esc(t.titulo)}</option>`).join('')}
                </select>
              </label>
              ${user?.perfil === 'admin' ? `
                <label>Colaborador
                  <select name="usuario_id">
                    ${staff.map((u) => `<option value="${u.id}" ${u.id === user.id ? 'selected' : ''}>${esc(u.nome)}</option>`).join('')}
                  </select>
                </label>
              ` : ''}
              <label>Data *
                <input type="date" name="data_trabalho" value="${todayStr}" required>
              </label>
              <label>Quantidade de Horas *
                <input type="number" step="0.25" min="0.25" max="24" name="horas" value="2.00" required>
              </label>
              <label>Tipo de Hora
                <select name="faturavel">
                  <option value="true">Faturável / Escopo Contratado</option>
                  <option value="false">Interna / Garantia</option>
                </select>
              </label>
            </div>
            <label class="field-full">Atividade Executada *
              <input type="text" name="descricao" required placeholder="Ex.: Implementação da API de faturamento e testes">
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="ts-save-btn">Registrar Horas</button>
        </div>
      </form>
    `;

    document.getElementById('new-timesheet-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('ts-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      btn.disabled = true;
      btn.textContent = 'Salvando...';
      try {
        await apiRequest('/timesheet', {
          method: 'POST',
          body: JSON.stringify({
            projeto_id: Number(raw.projeto_id),
            tarefa_id: raw.tarefa_id ? Number(raw.tarefa_id) : null,
            usuario_id: raw.usuario_id ? Number(raw.usuario_id) : null,
            data_trabalho: raw.data_trabalho,
            horas: Number(raw.horas),
            descricao: raw.descricao.trim(),
            faturavel: raw.faturavel === 'true'
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Horas registradas no Timesheet!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao apontar horas', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
        btn.textContent = 'Registrar Horas';
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusExportTimesheetCsv = () => {
    exportRowsToCsv(
      'nexus_timesheet_horas.csv',
      ['Data', 'Colaborador', 'Projeto', 'Tarefa', 'Atividade', 'Horas', 'Custo_Hora', 'Custo_Total'],
      filteredLogs.map((a) => [
        formatDate(a.data_trabalho),
        userMap[a.usuario_id]?.nome || a.usuario_id,
        projMap[a.projeto_id]?.titulo || a.projeto_id,
        taskMap[a.tarefa_id]?.titulo || '-',
        a.descricao,
        Number(a.horas || 0).toFixed(2),
        Number(a.custo_hora_snapshot || 0).toFixed(2),
        (Number(a.horas || 0) * Number(a.custo_hora_snapshot || 0)).toFixed(2)
      ])
    );
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Timesheet &amp; Rentabilidade de Projetos</h1>
        <span class="muted">Controle de horas investidas, custo operacional de equipe e margem real por contrato</span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button type="button" class="btn secondary" onclick="window.nexusExportTimesheetCsv()">Exportar CSV</button>
        <button type="button" class="btn" onclick="window.nexusOpenNewTimesheetModal()">${ICONS.plus}<span>Apontar Horas</span></button>
      </div>
    </div>

    <div class="grid" style="margin-bottom:18px;">
      <div class="card metric">
        <span class="title">Total de Horas Apontadas</span>
        <strong>${totalHoras.toFixed(1)}h</strong>
        <span class="pill-info">${filteredLogs.length} lançamento(s)</span>
      </div>
      <div class="card metric">
        <span class="title">Custo Técnico Apurado</span>
        <strong>${formatMoney(totalCusto)}</strong>
        <span class="pill-info">Baseado no salário/hora cadastrado</span>
      </div>
      <div class="card metric">
        <span class="title">Receita Total em Projetos</span>
        <strong>${formatMoney(profRows.reduce((a, r) => a + r.receita, 0))}</strong>
        <span class="pill-info">${profRows.length} projeto(s) monitorado(s)</span>
      </div>
      <div class="card metric">
        <span class="title">Resultado Bruto Projetos</span>
        <strong>${formatMoney(profRows.reduce((a, r) => a + r.lucro, 0))}</strong>
        <span class="pill-info">Receita - Custo Equipe &amp; Direto</span>
      </div>
    </div>

    <div class="card table-wrap" style="margin-bottom:20px;">
      <div style="padding:16px 18px 8px; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0; font-size:15.5px;">Análise de Margem &amp; Rentabilidade por Projeto</h3>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Projeto</th>
            <th>Horas (Real / Est.)</th>
            <th>Receita Contratada</th>
            <th>Custo Equipe + Direto</th>
            <th>Lucro Líquido</th>
            <th>Margem %</th>
          </tr>
        </thead>
        <tbody>
          ${profRows.map((r) => `
            <tr>
              <td><b>${esc(r.p.titulo)}</b></td>
              <td><b>${r.horasReais.toFixed(1)}h</b> <span class="muted">/ ${Number(r.p.horas_estimadas || 0).toFixed(0)}h</span></td>
              <td style="font-weight:700;">${formatMoney(r.receita)}</td>
              <td style="color:var(--danger);">${formatMoney(r.custoTotal)}</td>
              <td style="font-weight:800; color:${r.lucro >= 0 ? 'var(--ok)' : 'var(--danger)'};">${formatMoney(r.lucro)}</td>
              <td><span class="badge ${r.lucro >= 0 ? 'ativo' : 'cancelado'}">${r.margem}%</span></td>
            </tr>
          `).join('') || '<tr><td colspan="6" class="muted" style="text-align:center; padding:24px;">Nenhum projeto cadastrado.</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="card table-wrap">
      <div style="padding:16px 18px 8px;">
        <h3 style="margin:0; font-size:15.5px;">Histórico de Apontamentos de Horas</h3>
      </div>
      <table class="table">
        <thead>
          <tr><th>Data</th><th>Colaborador</th><th>Projeto</th><th>Atividade</th><th>Horas</th><th>Custo Apurado</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${filteredLogs.map((a) => `
            <tr>
              <td>${formatDate(a.data_trabalho)}</td>
              <td><b>${esc(userMap[a.usuario_id]?.nome || '-')}</b></td>
              <td>${esc(projMap[a.projeto_id]?.titulo || '-')}</td>
              <td>${esc(a.descricao)}</td>
              <td><b>${Number(a.horas || 0).toFixed(2)}h</b></td>
              <td>${formatMoney(Number(a.horas || 0) * Number(a.custo_hora_snapshot || 0))}</td>
              <td>
                <button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--danger);" data-del="/timesheet/${a.id}" data-label="${esc(a.descricao)}">Excluir</button>
              </td>
            </tr>
          `).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:28px;">Nenhum apontamento registrado. Clique em "+ Apontar Horas".</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 2. PROPOSTAS COMERCIAIS & CONTRATOS ====================
export async function renderPropostasView(ctx) {
  const { cache, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const clientMap = Object.fromEntries((cache.clientes || []).map((c) => [c.id, c.nome_empresa]));
  const propostas = (cache.propostas || []).filter((p) =>
    matchSearch([p.codigo, p.titulo, clientMap[p.cliente_id], p.status, p.escopo])
  );

  window.nexusOpenNewPropostaModal = () => {
    const clients = cache.clientes || [];
    const defaultVal = new Date(Date.now() + 15 * 86400000).toISOString().slice(0, 10);

    holeriteContainer.innerHTML = `
      <form id="new-proposta-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.fileText}</div>
            <div>
              <h2>Gerador de Proposta Comercial &amp; Contrato</h2>
              <p class="modal-subtitle">Ao ser aprovada no Portal do Cliente, cria automaticamente o Projeto, Tarefas e Faturas</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">1</span> Cliente &amp; Escopo Comercial</div>
            <div class="formgrid">
              <label>Cliente / Lead *
                <select name="cliente_id" required>
                  <option value="">Selecione o cliente</option>
                  ${clients.map((c) => `<option value="${c.id}">${esc(c.nome_empresa)} (${esc(c.contato_nome)})</option>`).join('')}
                </select>
              </label>
              <label>Título do Projeto / Proposta *
                <input type="text" name="titulo" required placeholder="Ex.: Plataforma Web Corporativa & App">
              </label>
              <label>Investimento Total (R$) *
                <input type="number" step="0.01" min="0" name="valor_total" value="5000.00" required>
              </label>
              <label>Número de Parcelas (Faturas) *
                <input type="number" min="1" max="24" name="parcelas" value="2" required>
              </label>
              <label>Condições de Pagamento
                <input type="text" name="condicoes_pagamento" value="50% na aprovação + 50% na entrega">
              </label>
              <label>Prazo de Execução (dias) *
                <input type="number" min="1" max="365" name="prazo_dias" value="30" required>
              </label>
              <label>Validade da Proposta
                <input type="date" name="validade_ate" value="${defaultVal}">
              </label>
              <label>Status de Envio
                <select name="status">
                  <option value="enviada">Enviar Agora ao Portal do Cliente</option>
                  <option value="rascunho">Salvar como Rascunho Interno</option>
                </select>
              </label>
            </div>
            <label class="field-full">Escopo Detalhado &amp; Premissas Técnicas *
              <textarea name="escopo" rows="4" required placeholder="Descreva as entregas, tecnologias, integrações e garantias inclusas na proposta..."></textarea>
            </label>
          </div>

          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">2</span> Entregáveis / Marcos (Geram Tarefas no Planner)</div>
            <label class="field-full">Lista de Etapas (uma por linha)
              <textarea name="entregaveis_texto" rows="3" placeholder="Levantamento de Requisitos e Protótipo UI/UX&#10;Desenvolvimento Back-end e Banco de Dados&#10;Homologação com Cliente e Deploy em Produção">Levantamento de Requisitos e Arquitetura&#10;Desenvolvimento e Integração dos Módulos&#10;Homologação e Implantação em Produção</textarea>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="prop-save-btn">Emitir Proposta Comercial</button>
        </div>
      </form>
    `;

    document.getElementById('new-proposta-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('prop-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      const lines = String(raw.entregaveis_texto || '')
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean);
      const prazoTotal = Number(raw.prazo_dias || 30);
      const entregaveis = lines.map((titulo, i) => ({
        titulo,
        prazo_dias: Math.max(3, Math.round(((i + 1) / Math.max(1, lines.length)) * prazoTotal))
      }));

      btn.disabled = true;
      btn.textContent = 'Emitindo...';
      try {
        await apiRequest('/propostas', {
          method: 'POST',
          body: JSON.stringify({
            cliente_id: Number(raw.cliente_id),
            titulo: raw.titulo.trim(),
            escopo: raw.escopo.trim(),
            entregaveis_json: JSON.stringify(entregaveis),
            valor_total: Number(raw.valor_total || 0),
            condicoes_pagamento: raw.condicoes_pagamento || null,
            parcelas: Number(raw.parcelas || 1),
            prazo_dias: prazoTotal,
            validade_ate: raw.validade_ate || null,
            status: raw.status
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Proposta comercial emitida com sucesso!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao emitir proposta', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
        btn.textContent = 'Emitir Proposta Comercial';
      }
    };

    holeriteDialog.showModal();
  };


  window.nexusPreviewPropostaPdf = (propId) => {
    const p = (cache.propostas || []).find((x) => x.id === propId);
    if (!p) return;
    const cfg = cache.empresa_config || {};
    const cli = (cache.clientes || []).find((c) => c.id === p.cliente_id);
    const entregaveis = safeJsonArray(p.entregaveis_json);

    holeriteContainer.innerHTML = `
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">${ICONS.fileText}</div>
          <div>
            <h2>Proposta Comercial ${esc(p.codigo)}</h2>
            <p class="modal-subtitle">Documento formatado para impressão ou exportação em PDF</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
      </div>
      <div class="modal-body">
        <div id="holerite-printable" class="holerite-slip">
          <div class="holerite-slip-header">
            <div>
              <div style="font-size:18px; font-weight:800; color:#0A1D37;">${esc((cfg.razao_social || 'NEXUS CODE BRASIL TECNOLOGIA LTDA').toUpperCase())}</div>
              <div style="font-size:12px; color:#475569;">${cfg.cnpj ? `CNPJ: ${esc(cfg.cnpj)} • ` : ''}${esc(cfg.endereco || 'Aracruz - ES')} • ${esc(cfg.email_financeiro || 'contato@nexuscodebrasil.com.br')}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-weight:800; font-size:14px; color:#0096B4;">PROPOSTA COMERCIAL</div>
              <div style="font-size:12px; color:#475569;">Código: <b>${esc(p.codigo)}</b> • Validade: ${formatDate(p.validade_ate)}</div>
            </div>
          </div>

          <div style="margin-bottom:14px; font-size:13px;">
            <div><b>Cliente:</b> ${esc(cli?.nome_empresa || clientMap[p.cliente_id] || '-')} (${esc(cli?.contato_nome || '')})</div>
            <div><b>Projeto:</b> ${esc(p.titulo)} • <b>Prazo Estimado:</b> ${p.prazo_dias} dias corridos</div>
          </div>

          <div style="margin-bottom:14px;">
            <div style="font-weight:800; color:#0A1D37; margin-bottom:6px;">1. Escopo Técnico &amp; Premissas</div>
            <div style="white-space:pre-wrap; line-height:1.55; color:#334155;">${esc(p.escopo)}</div>
          </div>

          ${entregaveis.length ? `
            <div style="margin-bottom:14px;">
              <div style="font-weight:800; color:#0A1D37; margin-bottom:6px;">2. Cronograma de Entregáveis</div>
              <table class="holerite-slip-table">
                <thead><tr><th>Etapa</th><th>Entrega</th><th>Marco</th></tr></thead>
                <tbody>
                  ${entregaveis.map((e, i) => `<tr><td>${i + 1}</td><td>${esc(e.titulo || e)}</td><td>${e.prazo_dias ? `Dia ${e.prazo_dias}` : '-'}</td></tr>`).join('')}
                </tbody>
              </table>
            </div>
          ` : ''}

          <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:12px 16px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-size:12px; color:#475569;">Condições de Pagamento (${p.parcelas}x)</div>
              <div style="font-weight:700; color:#0A1D37;">${esc(p.condicoes_pagamento || 'À combinar')}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:12px; color:#475569;">Investimento Total</div>
              <div style="font-size:20px; font-weight:900; color:#0A1D37;">${formatMoney(p.valor_total)}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn secondary" onclick="window.print()">Imprimir / Salvar PDF</button>
        <button type="button" class="btn" onclick="document.getElementById('holerite-dialog').close()">Fechar</button>
      </div>
    `;
    holeriteDialog.showModal();
  };

  window.nexusAprovarProposta = (id, codigo) => {
    showConfirmModal({
      title: `Aprovar & Converter Proposta ${codigo}`,
      message: 'Confirmar aprovação comercial? O sistema criará automaticamente o Projeto, as Tarefas no Planner e as Faturas parceladas.',
      confirmText: 'Aprovar e Gerar Projeto',
      variant: 'primary',
      onConfirm: async () => {
        await apiRequest(`/propostas/${id}/aprovar`, { method: 'POST' });
        invalidateCache();
        showToast('Proposta aprovada! Projeto, tarefas e faturas gerados.', 'success');
        await render();
      }
    });
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Propostas Comerciais &amp; Contratos</h1>
        <span class="muted">Envie propostas ao Portal do Cliente e converta aprovações em projetos e faturas com 1 clique</span>
      </div>
      <button type="button" class="btn" onclick="window.nexusOpenNewPropostaModal()">${ICONS.plus}<span>Nova Proposta Comercial</span></button>
    </div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr><th>Código</th><th>Cliente</th><th>Projeto / Escopo</th><th>Valor</th><th>Parcelas / Prazo</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${propostas.map((p) => `
            <tr>
              <td><b>${esc(p.codigo)}</b></td>
              <td><b>${esc(clientMap[p.cliente_id] || 'Cliente #' + p.cliente_id)}</b></td>
              <td>
                <b>${esc(p.titulo)}</b>
                ${p.feedback_cliente ? `<div class="muted" style="font-size:11.5px;">Retorno cliente: "${esc(p.feedback_cliente)}"</div>` : ''}
              </td>
              <td style="font-weight:800; color:var(--primary);">${formatMoney(p.valor_total)}</td>
              <td>${p.parcelas}x • ${p.prazo_dias}d</td>
              <td>
                <span class="badge ${p.status === 'aprovada' ? 'ativo' : p.status === 'recusada' ? 'cancelado' : 'pendente'}">${esc(p.status).replace('_', ' ')}</span>
                ${p.projeto_gerado_id ? `<div style="font-size:11px; color:var(--ok); font-weight:700; margin-top:3px;">✓ Projeto #${p.projeto_gerado_id}</div>` : ''}
              </td>
              <td style="white-space:nowrap;">
                <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusPreviewPropostaPdf(${p.id})">Visualizar / PDF</button>
                ${p.status !== 'aprovada' ? `<button type="button" class="btn" style="padding:5px 10px; font-size:12px;" onclick="window.nexusAprovarProposta(${p.id}, '${esc(p.codigo)}')">Aprovar &amp; Gerar Projeto</button>` : ''}
                <button type="button" class="btn secondary" style="padding:5px 9px; font-size:12px; color:var(--danger);" data-del="/propostas/${p.id}" data-label="${esc(p.codigo)}">Excluir</button>
              </td>
            </tr>
          `).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:32px;">Nenhuma proposta comercial cadastrada. Clique em "+ Nova Proposta Comercial".</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 3. CENTRAL DE SUPORTE & CHAMADOS (SERVICE DESK) ====================
export async function renderChamadosView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const clientMap = Object.fromEntries((cache.clientes || []).map((c) => [c.id, c.nome_empresa]));
  const projMap = Object.fromEntries((cache.projetos || []).map((p) => [p.id, p.titulo]));
  const userMap = Object.fromEntries((cache.usuarios || []).map((u) => [u.id, u.nome]));
  const chamados = (cache.chamados || []).filter((c) =>
    matchSearch([c.protocolo, c.titulo, clientMap[c.cliente_id], projMap[c.projeto_id], c.status, c.prioridade])
  );

  window.nexusOpenNewChamadoModal = () => {
    const clients = cache.clientes || [];
    const projs = cache.projetos || [];
    holeriteContainer.innerHTML = `
      <form id="new-chamado-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.inbox}</div>
            <div>
              <h2>Abrir Ticket de Suporte / Atendimento</h2>
              <p class="modal-subtitle">Registre chamados técnicos vinculados ao cliente e projeto</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Cliente *
                <select name="cliente_id" required>
                  <option value="">Selecione o cliente</option>
                  ${clients.map((c) => `<option value="${c.id}">${esc(c.nome_empresa)}</option>`).join('')}
                </select>
              </label>
              <label>Projeto Vinculado
                <select name="projeto_id">
                  <option value="">-- Geral --</option>
                  ${projs.map((p) => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}
                </select>
              </label>
              <label>Assunto *
                <input type="text" name="titulo" required placeholder="Resumo do atendimento">
              </label>
              <label>Prioridade &amp; SLA
                <select name="prioridade">
                  <option value="baixa">Baixa (48h)</option>
                  <option value="media" selected>Média (24h)</option>
                  <option value="alta">Alta (8h)</option>
                  <option value="critica">Crítica (4h)</option>
                </select>
              </label>
            </div>
            <label class="field-full">Descrição Inicial *
              <textarea name="descricao" rows="4" required></textarea>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="chm-save-btn">Criar Chamado</button>
        </div>
      </form>
    `;

    document.getElementById('new-chamado-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('chm-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      btn.disabled = true;
      try {
        await apiRequest('/chamados', {
          method: 'POST',
          body: JSON.stringify({
            cliente_id: Number(raw.cliente_id),
            projeto_id: raw.projeto_id ? Number(raw.projeto_id) : null,
            titulo: raw.titulo.trim(),
            prioridade: raw.prioridade,
            descricao: raw.descricao.trim()
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Chamado criado com sucesso!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao criar chamado', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusOpenChamadoThread = (id) => {
    const ch = (cache.chamados || []).find((x) => x.id === id);
    if (!ch) return;
    const msgs = safeJsonArray(ch.mensagens_json);

    holeriteContainer.innerHTML = `
      <div class="modal-header">
        <div class="modal-header-main">
          <div class="modal-header-icon">${ICONS.inbox}</div>
          <div>
            <h2>${esc(ch.protocolo)} — ${esc(ch.titulo)}</h2>
            <p class="modal-subtitle">Cliente: ${esc(clientMap[ch.cliente_id] || '-')} • SLA: ${ch.sla_horas}h</p>
          </div>
        </div>
        <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="ticket-thread" id="admin-ticket-thread">
          ${msgs.map((m) => {
            const isStaff = m.perfil !== 'cliente';
            const rowClass = isStaff ? 'staff' : 'client';
            const initial = (m.autor || 'U').charAt(0).toUpperCase();
            return `
            <div class="ticket-bubble-row ${rowClass}">
              <div class="ticket-avatar">${initial}</div>
              <div class="ticket-msg">
                <div class="ticket-msg-meta">
                  <span>${esc(m.autor)}</span>
                  <span class="ticket-msg-time">${esc(m.criado_em || '')}</span>
                </div>
                <div style="white-space:pre-wrap; word-break:break-word;">${esc(m.texto)}</div>
                ${m.anexo_data ? `
                  <a href="${m.anexo_data}" download="${esc(m.anexo_nome || 'anexo')}" class="ticket-attachment">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Baixar ${esc(m.anexo_nome || 'Anexo')}
                  </a>
                ` : ''}
              </div>
            </div>
          `}).join('') || '<p class="muted" style="text-align:center; padding:24px;">Nenhuma mensagem registrada.</p>'}
        </div>

        <form id="admin-ticket-reply-form" style="display:flex; flex-direction:column; gap:10px;">
          <div class="formgrid">
            <label>Atualizar Status do Chamado
              <select id="admin-ticket-status">
                ${['aberto', 'em_analise', 'aguardando_cliente', 'resolvido', 'fechado'].map((st) => `<option value="${st}" ${ch.status === st ? 'selected' : ''}>${st.replace('_', ' ')}</option>`).join('')}
              </select>
            </label>
            <label>Anexo Técnico (Opcional)
              <input type="file" id="admin-ticket-file" accept=".pdf,.png,.jpg,.jpeg">
            </label>
          </div>
          <textarea id="admin-ticket-msg" rows="3" required placeholder="Digite a resposta técnica para o cliente..."></textarea>
          <div style="display:flex; justify-content:flex-end; gap:10px;">
            <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Fechar</button>
            <button type="submit" class="btn" id="admin-ticket-send">Enviar Resposta ao Cliente</button>
          </div>
        </form>
      </div>
    `;

    const box = document.getElementById('admin-ticket-thread');
    if (box) box.scrollTop = box.scrollHeight;

    document.getElementById('admin-ticket-reply-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('admin-ticket-send');
      const texto = document.getElementById('admin-ticket-msg').value.trim();
      const novo_status = document.getElementById('admin-ticket-status').value;
      const fileInp = document.getElementById('admin-ticket-file');
      if (!texto) return;

      btn.disabled = true;
      btn.textContent = 'Enviando...';
      try {
        let anexo_nome = null;
        let anexo_data = null;
        if (fileInp?.files?.[0]) {
          const f = fileInp.files[0];
          if (f.size > 2.5 * 1024 * 1024) throw new Error('Anexo deve ter no máximo 2,5 MB.');
          anexo_nome = f.name;
          anexo_data = await readFileAsDataUrl(f);
        }
        const updated = await apiRequest(`/chamados/${ch.id}/mensagens`, {
          method: 'POST',
          body: JSON.stringify({ texto, novo_status, anexo_nome, anexo_data })
        });
        const idx = cache.chamados.findIndex((x) => x.id === ch.id);
        if (idx >= 0) cache.chamados[idx] = updated;
        invalidateCache();
        showToast('Resposta enviada e notificada ao cliente!', 'success');
        window.nexusOpenChamadoThread(ch.id);
      } catch (err) {
        showNoticeModal({ title: 'Erro ao responder chamado', message: err.message, variant: 'error' });
        btn.disabled = false;
        btn.textContent = 'Enviar Resposta ao Cliente';
      }
    };

    holeriteDialog.showModal();
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Central de Suporte &amp; Chamados (Service Desk)</h1>
        <span class="muted">Atendimento integrado com o Portal do Cliente, controle de SLA e histórico de mensagens</span>
      </div>
      <button type="button" class="btn" onclick="window.nexusOpenNewChamadoModal()">${ICONS.plus}<span>Abrir Chamado</span></button>
    </div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr><th>Protocolo</th><th>Cliente</th><th>Assunto</th><th>Prioridade / SLA</th><th>Responsável</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${chamados.map((c) => `
            <tr>
              <td><b>${esc(c.protocolo)}</b></td>
              <td><b>${esc(clientMap[c.cliente_id] || '-')}</b><div class="muted" style="font-size:11.5px;">${esc(projMap[c.projeto_id] || 'Geral')}</div></td>
              <td><b>${esc(c.titulo)}</b></td>
              <td><span class="prio-badge prio-${esc(c.prioridade)}">${esc(c.prioridade)}</span> <span class="muted" style="font-size:11.5px;">(${c.sla_horas}h)</span></td>
              <td>${esc(userMap[c.responsavel_id] || 'Fila Geral')}</td>
              <td><span class="badge ${c.status === 'resolvido' || c.status === 'fechado' ? 'ativo' : 'pendente'}">${esc(c.status).replace('_', ' ')}</span></td>
              <td style="white-space:nowrap;">
                <button type="button" class="btn" style="padding:5px 11px; font-size:12px;" onclick="window.nexusOpenChamadoThread(${c.id})">Atender</button>
                ${user?.perfil === 'admin' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:12px; color:var(--danger);" data-del="/chamados/${c.id}" data-label="${esc(c.protocolo)}">Excluir</button>` : ''}
              </td>
            </tr>
          `).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:32px;">Nenhum chamado de suporte registrado.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 4. DRE GERENCIAL & FLUXO DE CAIXA ====================
export async function renderDreView(ctx) {
  const { ICONS } = ctx;
  const dre = await apiRequest('/financeiro/dre');
  const serie = dre.serie_mensal || [];
  const maxVal = Math.max(100, ...serie.map((s) => Math.max(s.receitas, s.despesas)));
  const cats = Object.entries(dre.por_categoria || {});

  window.nexusExportDreCsv = () => {
    exportRowsToCsv(
      'nexus_dre_fluxo_caixa.csv',
      ['Competencia', 'Receitas_Pagas', 'Despesas_e_Folha', 'Resultado_Liquido'],
      serie.map((s) => [s.competencia, s.receitas.toFixed(2), s.despesas.toFixed(2), s.resultado.toFixed(2)])
    );
  };

  return `
    <div class="toolbar">
      <div>
        <h1>DRE Gerencial &amp; Fluxo de Caixa</h1>
        <span class="muted">Demonstrativo consolidado de receitas realizadas, despesas operacionais, folha e margem líquida</span>
      </div>
      <button type="button" class="btn secondary" onclick="window.nexusExportDreCsv()">Exportar DRE (CSV)</button>
    </div>

    <div class="grid" style="margin-bottom:20px;">
      <div class="card metric">
        <span class="title">Receita Bruta Realizada</span>
        <strong style="color:var(--ok);">${formatMoney(dre.receita_bruta_paga)}</strong>
        <span class="pill-info">A receber: ${formatMoney(dre.receita_prevista_aberta)}</span>
      </div>
      <div class="card metric">
        <span class="title">Total Despesas + Folha</span>
        <strong style="color:var(--danger);">${formatMoney(dre.total_despesas_pagas)}</strong>
        <span class="pill-info">Em aberto: ${formatMoney(dre.despesas_operacionais_abertas)}</span>
      </div>
      <div class="card metric">
        <span class="title">Lucro Líquido Realizado</span>
        <strong style="color:${dre.lucro_liquido >= 0 ? 'var(--primary)' : 'var(--danger)'};">${formatMoney(dre.lucro_liquido)}</strong>
        <span class="pill-info">Margem líquida: ${dre.margem_percent}%</span>
      </div>
      <div class="card metric">
        <span class="title">Receita Recorrente (MRR)</span>
        <strong>${formatMoney(dre.mrr_mensal)}</strong>
        <span class="pill-info">Assinaturas mensais ativas</span>
      </div>
    </div>

    <div class="dashboard-panels">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <h3 style="margin:0; font-size:16px;">Evolução Mensal: Receitas vs. Saídas (6 Meses)</h3>
          <div style="display:flex; gap:12px; font-size:12px; font-weight:600;">
            <span style="color:#0284c7;">■ Receitas</span>
            <span style="color:#dc2626;">■ Despesas + Folha</span>
          </div>
        </div>
        <div class="chart-bars-grid">
          ${serie.map((m) => {
            const hIn = Math.max(4, Math.round((m.receitas / maxVal) * 145));
            const hOut = Math.max(4, Math.round((m.despesas / maxVal) * 145));
            return `
              <div class="chart-month-col" title="${m.competencia}: Receita ${formatMoney(m.receitas)} | Saídas ${formatMoney(m.despesas)}">
                <div class="chart-bar-pair">
                  <div class="chart-bar-in" style="height:${hIn}px;"></div>
                  <div class="chart-bar-out" style="height:${hOut}px;"></div>
                </div>
                <b style="font-size:11.5px;">${esc(m.competencia)}</b>
                <span style="font-size:10.5px; font-weight:700; color:${m.resultado >= 0 ? 'var(--ok)' : 'var(--danger)'};">${formatMoney(m.resultado)}</span>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 14px; font-size:16px;">Distribuição de Custos &amp; Despesas por Categoria</h3>
        ${cats.length ? cats.map(([cat, val]) => {
          const pct = dre.total_despesas_pagas > 0 ? Math.min(100, Math.round((val / dre.total_despesas_pagas) * 100)) : 0;
          return `
            <div style="margin-bottom:12px;">
              <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px;">
                <b style="text-transform:capitalize;">${esc(cat.replace(/_/g, ' '))}</b>
                <span>${formatMoney(val)}</span>
              </div>
              <div style="height:7px; background:var(--surface2); border-radius:999px; overflow:hidden; border:1px solid var(--border);">
                <div style="width:${pct}%; height:100%; background:#0A1D37;"></div>
              </div>
            </div>
          `;
        }).join('') : '<p class="muted">Nenhuma despesa ou folha lançada até o momento.</p>'}
      </div>
    </div>
  `;
}

// ==================== 5. CONTAS A PAGAR & DESPESAS ====================
export async function renderDespesasView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const projMap = Object.fromEntries((cache.projetos || []).map((p) => [p.id, p.titulo]));
  const despesas = (cache.despesas || []).filter((d) =>
    matchSearch([d.descricao, d.categoria, d.fornecedor, d.status, projMap[d.projeto_id]])
  );

  window.nexusOpenNewDespesaModal = () => {
    const projs = cache.projetos || [];
    const todayStr = new Date().toISOString().slice(0, 10);
    holeriteContainer.innerHTML = `
      <form id="new-despesa-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.dollar}</div>
            <div>
              <h2>Lançar Conta a Pagar / Despesa</h2>
              <p class="modal-subtitle">Registre custos operacionais, servidores, impostos ou despesas de projeto</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Descrição da Despesa *
                <input type="text" name="descricao" required placeholder="Ex.: Servidor Cloud / Banco Neon">
              </label>
              <label>Categoria *
                <select name="categoria">
                  <option value="infraestrutura">Infraestrutura &amp; Cloud</option>
                  <option value="software_saas">Licenças &amp; Ferramentas SaaS</option>
                  <option value="impostos">Impostos &amp; Contabilidade</option>
                  <option value="folha_rh">Folha &amp; Benefícios RH</option>
                  <option value="marketing">Marketing &amp; Comercial</option>
                  <option value="fornecedores">Fornecedores &amp; Terceiros</option>
                  <option value="outros">Outros Custos</option>
                </select>
              </label>
              <label>Fornecedor / Favorecido
                <input type="text" name="fornecedor" placeholder="Ex.: Vercel, AWS, Receita Federal">
              </label>
              <label>Projeto Vinculado (Opcional)
                <select name="projeto_id">
                  <option value="">-- Custo Fixo da Empresa --</option>
                  ${projs.map((p) => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}
                </select>
              </label>
              <label>Valor (R$) *
                <input type="number" step="0.01" min="0.01" name="valor" required>
              </label>
              <label>Vencimento *
                <input type="date" name="vencimento" value="${todayStr}" required>
              </label>
              <label>Status
                <select name="status">
                  <option value="pendente">Pendente</option>
                  <option value="pago">Pago</option>
                </select>
              </label>
              <label>Despesa Recorrente Mensal?
                <select name="recorrente">
                  <option value="false">Não (Pontual)</option>
                  <option value="true">Sim (Mensal)</option>
                </select>
              </label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="desp-save-btn">Salvar Despesa</button>
        </div>
      </form>
    `;

    document.getElementById('new-despesa-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('desp-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      btn.disabled = true;
      try {
        await apiRequest('/despesas', {
          method: 'POST',
          body: JSON.stringify({
            descricao: raw.descricao.trim(),
            categoria: raw.categoria,
            fornecedor: raw.fornecedor || null,
            projeto_id: raw.projeto_id ? Number(raw.projeto_id) : null,
            valor: Number(raw.valor),
            vencimento: raw.vencimento,
            status: raw.status,
            recorrente: raw.recorrente === 'true'
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Despesa lançada com sucesso!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar despesa', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };


  window.nexusOpenNewReembolsoModal = () => {
    const projs = cache.projetos || [];
    const todayStr = new Date().toISOString().slice(0, 10);
    holeriteContainer.innerHTML = `
      <form id="new-reembolso-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.dollar}</div>
            <div>
              <h2>Solicitar Reembolso de Despesa</h2>
              <p class="modal-subtitle">Ao ser aprovado, o reembolso gera automaticamente o lançamento em Contas a Pagar</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Descrição da Despesa *
                <input type="text" name="descricao" required placeholder="Ex.: Deslocamento visita técnica / Certificado SSL">
              </label>
              <label>Valor (R$) *
                <input type="number" step="0.01" min="0.01" name="valor" required>
              </label>
              <label>Data do Comprovante *
                <input type="date" name="data_despesa" value="${todayStr}" required>
              </label>
              <label>Projeto Vinculado (Opcional)
                <select name="projeto_id">
                  <option value="">-- Geral --</option>
                  ${projs.map((p) => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}
                </select>
              </label>
            </div>
            <label class="field-full">Comprovante / Nota Fiscal (PDF ou Imagem, máx. 2 MB)
              <input type="file" id="reemb-file" accept=".pdf,.png,.jpg,.jpeg">
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="reemb-save-btn">Enviar Solicitação</button>
        </div>
      </form>
    `;

    document.getElementById('new-reembolso-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('reemb-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      const fInp = document.getElementById('reemb-file');
      btn.disabled = true;
      try {
        let comprovante_data = null;
        if (fInp?.files?.[0]) {
          if (fInp.files[0].size > 2 * 1024 * 1024) throw new Error('O comprovante deve ter no máximo 2 MB.');
          comprovante_data = await readFileAsDataUrl(fInp.files[0]);
        }
        await apiRequest('/reembolsos', {
          method: 'POST',
          body: JSON.stringify({
            projeto_id: raw.projeto_id ? Number(raw.projeto_id) : null,
            descricao: raw.descricao.trim(),
            valor: Number(raw.valor),
            data_despesa: raw.data_despesa,
            comprovante_data
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Solicitação de reembolso enviada!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao solicitar reembolso', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusJulgarReembolso = async (id, status) => {
    try {
      await apiRequest(`/reembolsos/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status })
      });
      invalidateCache();
      showToast(status === 'aprovado' ? 'Reembolso aprovado e lançado em Contas a Pagar!' : 'Reembolso recusado.', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro', message: err.message, variant: 'error' });
    }
  };

  window.nexusPayDespesa = (id) => {
    showConfirmModal({
      title: 'Confirmar Pagamento de Despesa',
      message: 'Deseja marcar esta conta a pagar como Paga?',
      confirmText: 'Confirmar Baixa',
      variant: 'primary',
      onConfirm: async () => {
        await apiRequest(`/despesas/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'pago' }) });
        invalidateCache();
        showToast('Baixa registrada com sucesso!', 'success');
        await render();
      }
    });
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Contas a Pagar &amp; Despesas</h1>
        <span class="muted">Controle de saídas financeiras, fornecedores, infraestrutura e custos por projeto</span>
      </div>
      <button type="button" class="btn" onclick="window.nexusOpenNewDespesaModal()">${ICONS.plus}<span>Nova Despesa</span></button>
    </div>

    <div class="card table-wrap" style="margin-bottom:22px;">
      <table class="table">
        <thead>
          <tr><th>Descrição</th><th>Categoria</th><th>Fornecedor</th><th>Projeto</th><th>Valor</th><th>Vencimento</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${despesas.map((d) => `
            <tr>
              <td><b>${esc(d.descricao)}</b>${d.recorrente ? ' <span class="badge" style="font-size:10px;">Recorrente</span>' : ''}</td>
              <td style="text-transform:capitalize;">${esc(d.categoria.replace(/_/g, ' '))}</td>
              <td>${esc(d.fornecedor || '-')}</td>
              <td>${esc(projMap[d.projeto_id] || 'Empresa (Fixo)')}</td>
              <td style="font-weight:700; color:var(--danger);">${formatMoney(d.valor)}</td>
              <td>${formatDate(d.vencimento)}</td>
              <td><span class="badge ${esc(d.status)}">${esc(d.status)}</span></td>
              <td style="white-space:nowrap;">
                ${d.status !== 'pago' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--ok);" onclick="window.nexusPayDespesa(${d.id})">Pagar</button>` : ''}
                ${user?.perfil === 'admin' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--danger);" data-del="/despesas/${d.id}" data-label="${esc(d.descricao)}">Excluir</button>` : ''}
              </td>
            </tr>
          `).join('') || '<tr><td colspan="8" class="muted" style="text-align:center; padding:32px;">Nenhuma despesa cadastrada.</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="card table-wrap">
      <div style="padding:16px 18px 8px; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0; font-size:15.5px;">Solicitações de Reembolso da Equipe (${(cache.reembolsos || []).length})</h3>
        <button type="button" class="btn secondary" style="padding:6px 12px; font-size:12px;" onclick="window.nexusOpenNewReembolsoModal()">+ Solicitar Reembolso</button>
      </div>
      <table class="table">
        <thead>
          <tr><th>Colaborador</th><th>Descrição</th><th>Projeto</th><th>Data</th><th>Valor</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${(cache.reembolsos || []).map((rb) => {
            const uName = (cache.usuarios || []).find((u) => u.id === rb.usuario_id)?.nome || ('Colaborador #' + rb.usuario_id);
            return `
              <tr>
                <td><b>${esc(uName)}</b></td>
                <td>${esc(rb.descricao)}</td>
                <td>${esc(projMap[rb.projeto_id] || 'Geral')}</td>
                <td>${formatDate(rb.data_despesa)}</td>
                <td style="font-weight:700;">${formatMoney(rb.valor)}</td>
                <td><span class="badge ${rb.status === 'aprovado' || rb.status === 'pago' ? 'ativo' : rb.status === 'recusado' ? 'cancelado' : 'pendente'}">${esc(rb.status)}</span></td>
                <td style="white-space:nowrap;">
                  ${user?.perfil === 'admin' && rb.status === 'pendente' ? `
                    <button type="button" class="btn" style="padding:5px 10px; font-size:11.5px;" onclick="window.nexusJulgarReembolso(${rb.id}, 'aprovado')">Aprovar</button>
                    <button type="button" class="btn secondary" style="padding:5px 10px; font-size:11.5px; color:var(--danger);" onclick="window.nexusJulgarReembolso(${rb.id}, 'recusado')">Recusar</button>
                  ` : '-'}
                </td>
              </tr>
            `;
          }).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:24px;">Nenhuma solicitação de reembolso registrada.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 6. CONTRATOS RECORRENTES (MRR) ====================
export async function renderContratosView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const clientMap = Object.fromEntries((cache.clientes || []).map((c) => [c.id, c.nome_empresa]));
  const contratos = (cache.contratos || []).filter((ct) =>
    matchSearch([ct.titulo, clientMap[ct.cliente_id], ct.status])
  );

  window.nexusOpenNewContratoModal = () => {
    const clients = cache.clientes || [];
    const todayStr = new Date().toISOString().slice(0, 10);
    holeriteContainer.innerHTML = `
      <form id="new-contrato-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.sparkles}</div>
            <div>
              <h2>Novo Contrato Recorrente (MRR / Mensalidade)</h2>
              <p class="modal-subtitle">Assinaturas de suporte, manutenção ou licença SaaS com faturamento mensal</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Cliente *
                <select name="cliente_id" required>
                  <option value="">Selecione o cliente</option>
                  ${clients.map((c) => `<option value="${c.id}">${esc(c.nome_empresa)}</option>`).join('')}
                </select>
              </label>
              <label>Título do Plano / Contrato *
                <input type="text" name="titulo" required placeholder="Ex.: Suporte & Hospedagem Cloud Mensal">
              </label>
              <label>Valor Mensal (R$) *
                <input type="number" step="0.01" min="1" name="valor_mensal" required>
              </label>
              <label>Dia de Vencimento (1 a 28) *
                <input type="number" min="1" max="28" name="dia_vencimento" value="10" required>
              </label>
              <label>Data de Início *
                <input type="date" name="data_inicio" value="${todayStr}" required>
              </label>
              <label>Status
                <select name="status">
                  <option value="ativo">Ativo</option>
                  <option value="pausado">Pausado</option>
                </select>
              </label>
            </div>
            <label class="field-full">Descrição dos Serviços Inclusos
              <textarea name="descricao" rows="2"></textarea>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="ct-save-btn">Criar Assinatura</button>
        </div>
      </form>
    `;

    document.getElementById('new-contrato-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('ct-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      btn.disabled = true;
      try {
        await apiRequest('/contratos-recorrentes', {
          method: 'POST',
          body: JSON.stringify({
            cliente_id: Number(raw.cliente_id),
            titulo: raw.titulo.trim(),
            valor_mensal: Number(raw.valor_mensal),
            dia_vencimento: Number(raw.dia_vencimento || 10),
            data_inicio: raw.data_inicio,
            status: raw.status,
            descricao: raw.descricao || null
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Contrato recorrente criado!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar contrato', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusFaturarContratosMes = () => {
    showConfirmModal({
      title: 'Faturar Contratos Recorrentes do Mês',
      message: 'Deseja gerar automaticamente as faturas mensais de todos os contratos recorrentes ativos que ainda não foram faturados nesta competência?',
      confirmText: 'Gerar Faturas do Mês',
      variant: 'primary',
      onConfirm: async () => {
        const res = await apiRequest('/contratos-recorrentes/gerar-faturas-mes', { method: 'POST' });
        invalidateCache();
        showToast(`${res.faturas_geradas} fatura(s) gerada(s) para ${res.competencia}!`, 'success');
        await render();
      }
    });
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Contratos Recorrentes &amp; Assinaturas (MRR)</h1>
        <span class="muted">Gestão de mensalidades de suporte, manutenção e geração automática de cobranças</span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button type="button" class="btn secondary" onclick="window.nexusFaturarContratosMes()">${ICONS.sparkles}<span>Faturar Assinaturas do Mês</span></button>
        <button type="button" class="btn" onclick="window.nexusOpenNewContratoModal()">${ICONS.plus}<span>Novo Contrato MRR</span></button>
      </div>
    </div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr><th>Cliente</th><th>Plano / Contrato</th><th>Valor Mensal</th><th>Vencimento</th><th>Último Faturamento</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${contratos.map((ct) => `
            <tr>
              <td><b>${esc(clientMap[ct.cliente_id] || '-')}</b></td>
              <td><b>${esc(ct.titulo)}</b></td>
              <td style="font-weight:800; color:var(--ok);">${formatMoney(ct.valor_mensal)}/mês</td>
              <td>Todo dia ${ct.dia_vencimento}</td>
              <td>${esc(ct.ultima_geracao || 'Ainda não faturado')}</td>
              <td><span class="badge ${ct.status === 'ativo' ? 'ativo' : 'pendente'}">${esc(ct.status)}</span></td>
              <td>
                ${user?.perfil === 'admin' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--danger);" data-del="/contratos-recorrentes/${ct.id}" data-label="${esc(ct.titulo)}">Excluir</button>` : ''}
              </td>
            </tr>
          `).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:32px;">Nenhum contrato recorrente ativo.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 7. ATIVOS, DOMÍNIOS & COFRE DE ACESSOS ====================
export async function renderAtivosView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const clientMap = Object.fromEntries((cache.clientes || []).map((c) => [c.id, c.nome_empresa]));
  const ativos = (cache.ativos || []).filter((a) =>
    matchSearch([a.nome, a.tipo, a.provedor, clientMap[a.cliente_id], a.url_acesso])
  );

  window.nexusOpenNewAtivoModal = () => {
    const clients = cache.clientes || [];
    holeriteContainer.innerHTML = `
      <form id="new-ativo-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.building}</div>
            <div>
              <h2>Cadastrar Ativo, Domínio ou Credencial</h2>
              <p class="modal-subtitle">Controle de vencimentos de domínios, servidores cloud, licenças e acessos</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Tipo de Ativo *
                <select name="tipo">
                  <option value="dominio">Domínio Web (.com.br / .com)</option>
                  <option value="hospedagem_cloud">Hospedagem / Servidor Cloud / Banco</option>
                  <option value="licenca_software">Licença de Software / API</option>
                  <option value="equipamento">Equipamento / Hardware</option>
                  <option value="credencial_acesso">Credencial / Acesso Técnico</option>
                </select>
              </label>
              <label>Nome / Identificação *
                <input type="text" name="nome" required placeholder="Ex.: nexuscodebrasil.com.br">
              </label>
              <label>Cliente Vinculado (vazio = Interno)
                <select name="cliente_id">
                  <option value="">-- Ativo Interno Nexus Code --</option>
                  ${clients.map((c) => `<option value="${c.id}">${esc(c.nome_empresa)}</option>`).join('')}
                </select>
              </label>
              <label>Provedor / Fornecedor
                <input type="text" name="provedor" placeholder="Ex.: Registro.br, Vercel, Neon, AWS">
              </label>
              <label>URL de Acesso / Painel
                <input type="text" name="url_acesso" placeholder="https://...">
              </label>
              <label>Usuário / Login
                <input type="text" name="usuario_acesso">
              </label>
              <label>Senha / Chave / Token
                <input type="text" name="segredo_acesso">
              </label>
              <label>Data de Renovação / Vencimento
                <input type="date" name="data_vencimento">
              </label>
              <label>Valor de Renovação (R$)
                <input type="number" step="0.01" name="valor_renovacao" value="0.00">
              </label>
              <label>Status
                <select name="status">
                  <option value="ativo">Ativo</option>
                  <option value="vencendo">Vencendo em breve</option>
                  <option value="expirado">Expirado</option>
                </select>
              </label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="ativo-save-btn">Salvar Ativo</button>
        </div>
      </form>
    `;

    document.getElementById('new-ativo-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('ativo-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      btn.disabled = true;
      try {
        await apiRequest('/ativos', {
          method: 'POST',
          body: JSON.stringify({
            cliente_id: raw.cliente_id ? Number(raw.cliente_id) : null,
            tipo: raw.tipo,
            nome: raw.nome.trim(),
            provedor: raw.provedor || null,
            url_acesso: raw.url_acesso || null,
            usuario_acesso: raw.usuario_acesso || null,
            segredo_acesso: raw.segredo_acesso || null,
            valor_renovacao: Number(raw.valor_renovacao || 0),
            data_vencimento: raw.data_vencimento || null,
            status: raw.status
          })
        });
        holeriteDialog.close();
        invalidateCache();
        showToast('Ativo registrado com sucesso!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar ativo', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusCopySecret = (val) => {
    navigator.clipboard?.writeText(val || '');
    showToast('Credencial copiada para a área de transferência!', 'info');
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Ativos, Domínios &amp; Cofre de Acessos</h1>
        <span class="muted">Inventário técnico da empresa e clientes, datas de renovação e credenciais seguras</span>
      </div>
      <button type="button" class="btn" onclick="window.nexusOpenNewAtivoModal()">${ICONS.plus}<span>Novo Ativo / Domínio</span></button>
    </div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr><th>Ativo / Nome</th><th>Tipo</th><th>Vínculo</th><th>Provedor</th><th>Acesso / Credencial</th><th>Renovação</th><th>Status</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${ativos.map((a) => `
            <tr>
              <td>
                <b>${esc(a.nome)}</b>
                ${a.url_acesso ? `<div><a href="${esc(a.url_acesso)}" target="_blank" rel="noopener" style="font-size:11.5px; color:var(--primary);">Abrir painel ↗</a></div>` : ''}
              </td>
              <td style="text-transform:capitalize;">${esc(a.tipo.replace(/_/g, ' '))}</td>
              <td>${esc(a.cliente_id ? (clientMap[a.cliente_id] || 'Cliente') : 'Nexus Code (Interno)')}</td>
              <td>${esc(a.provedor || '-')}</td>
              <td>
                ${a.usuario_acesso ? `<div style="font-size:12px;">User: <b>${esc(a.usuario_acesso)}</b></div>` : ''}
                ${a.segredo_acesso ? `<button type="button" class="btn secondary" style="padding:3px 8px; font-size:11px; margin-top:3px;" onclick="window.nexusCopySecret('${esc(a.segredo_acesso)}')">Copiar Senha/Chave</button>` : '<span class="muted">-</span>'}
              </td>
              <td>
                <div>${formatDate(a.data_vencimento)}</div>
                ${Number(a.valor_renovacao) > 0 ? `<div class="muted" style="font-size:11.5px;">${formatMoney(a.valor_renovacao)}</div>` : ''}
              </td>
              <td><span class="badge ${a.status === 'ativo' ? 'ativo' : 'pendente'}">${esc(a.status)}</span></td>
              <td>
                ${user?.perfil === 'admin' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--danger);" data-del="/ativos/${a.id}" data-label="${esc(a.nome)}">Excluir</button>` : ''}
              </td>
            </tr>
          `).join('') || '<tr><td colspan="8" class="muted" style="text-align:center; padding:32px;">Nenhum ativo ou domínio cadastrado.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}

// ==================== 8. CONFIGURAÇÕES DA EMPRESA, WHITE-LABEL & PERMISSÕES ====================
export async function renderEmpresaView(ctx) {
  const { cache, user, invalidateCache, render, ICONS } = ctx;
  const cfg = cache.empresa_config || await apiRequest('/empresa');
  const org = cache.organizacao || {};
  const brand = org.branding || {};
  const isAdmin = user?.perfil === 'admin';
  const canCustomDomain = Boolean(org.is_master || (org.plano || '').toLowerCase() === 'enterprise');

  let perms = {
    colaborador: {
      projetos: true, tarefas: true, timesheet: true, orcamentos: true,
      propostas: true, clientes: true, chamados: true, financeiro_dre: false,
      faturas: true, despesas: false, contratos: false, ponto: true,
      holerite: true, ativos: true, usuarios: false, auditoria: false
    }
  };
  if (cfg?.permissoes_json) {
    try {
      const parsed = JSON.parse(cfg.permissoes_json);
      if (parsed?.colaborador) perms.colaborador = { ...perms.colaborador, ...parsed.colaborador };
    } catch (_) {}
  }

  const modulosLista = [
    ['projetos', 'Projetos & Homologação'],
    ['tarefas', 'Tarefas & Planner Kanban'],
    ['timesheet', 'Timesheet & Apontamento de Horas'],
    ['orcamentos', 'Solicitações & Orçamentos'],
    ['propostas', 'Propostas Comerciais & Contratos'],
    ['clientes', 'Clientes, Leads & Funil de Vendas'],
    ['chamados', 'Suporte & Chamados (Service Desk)'],
    ['financeiro_dre', 'DRE Gerencial & Fluxo de Caixa'],
    ['faturas', 'Faturas & Cobranças'],
    ['despesas', 'Contas a Pagar & Despesas'],
    ['contratos', 'Contratos Recorrentes (MRR)'],
    ['ponto', 'Gestão de Ponto'],
    ['holerite', 'Holerite & Rendimentos'],
    ['ativos', 'Ativos, Domínios & Cofre'],
    ['usuarios', 'Usuários & CBO'],
    ['auditoria', 'Logs de Auditoria']
  ];

  setTimeout(() => {
    const logoFileInp = document.getElementById('wl-logo-file');
    logoFileInp?.addEventListener('change', async (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      if (f.size > 1.5 * 1024 * 1024) {
        showToast('O arquivo do logotipo deve ter no máximo 1,5 MB.', 'error');
        return;
      }
      const dataUrl = await readFileAsDataUrl(f);
      document.getElementById('wl-logo-url').value = dataUrl;
      const prev = document.getElementById('wl-logo-preview');
      if (prev) prev.innerHTML = `<img src="${dataUrl}" alt="Logotipo" style="max-height:36px; max-width:160px; object-fit:contain;">`;
      showToast('Logotipo carregado. Clique em "Salvar Identidade & Domínio" para aplicar.', 'info');
    });

    const brandForm = document.getElementById('whitelabel-branding-form');
    if (brandForm) {
      brandForm.onsubmit = async (e) => {
        e.preventDefault();
        if (!isAdmin) {
          showNoticeModal({ title: 'Acesso Restrito', message: 'Apenas administradores podem alterar a identidade visual e o domínio da organização.', variant: 'warning' });
          return;
        }
        const btn = document.getElementById('save-wl-btn');
        const raw = Object.fromEntries(new FormData(brandForm));
        btn.disabled = true;
        btn.textContent = 'Aplicando Configurações...';
        try {
          const payload = {
            nome_plataforma: raw.nome_plataforma.trim(),
            subtitulo_plataforma: raw.subtitulo_plataforma.trim(),
            logo_url: raw.logo_url.trim(),
            cor_primaria: raw.cor_primaria,
            cor_secundaria: raw.cor_secundaria,
            cor_sidebar: raw.cor_sidebar,
            tema_padrao: raw.tema_padrao,
            ocultar_powered_by: Boolean(brandForm.querySelector('[name="ocultar_powered_by"]')?.checked),
            ...(canCustomDomain ? { dominio_customizado: (raw.dominio_customizado || '').trim() } : {})
          };
          const res = await apiRequest('/empresa/branding', {
            method: 'PUT',
            body: JSON.stringify(payload)
          });
          if (cache.organizacao) {
            cache.organizacao.branding = res.branding;
            if ('dominio_customizado' in res) {
              cache.organizacao.dominio_customizado = res.dominio_customizado;
            }
            applyWhiteLabelBranding(cache.organizacao);
          }
          invalidateCache();
          showToast('Identidade visual e configurações de domínio atualizadas!', 'success');
          render();
        } catch (err) {
          showNoticeModal({ title: 'Erro ao salvar configurações', message: err.message, variant: 'error' });
        } finally {
          btn.disabled = false;
          btn.textContent = 'Salvar Identidade & Domínio';
        }
      };
    }

    const form = document.getElementById('empresa-config-form');
    if (!form) return;
    form.onsubmit = async (e) => {
      e.preventDefault();
      if (!isAdmin) {
        showNoticeModal({ title: 'Acesso Restrito', message: 'Apenas administradores podem salvar configurações institucionais.', variant: 'warning' });
        return;
      }
      const btn = document.getElementById('save-empresa-btn');
      const raw = Object.fromEntries(new FormData(form));
      const colabPerms = {};
      modulosLista.forEach(([key]) => {
        colabPerms[key] = Boolean(form.querySelector(`[name="perm_colab_${key}"]`)?.checked);
      });

      btn.disabled = true;
      btn.textContent = 'Salvando...';
      try {
        await apiRequest('/empresa', {
          method: 'PUT',
          body: JSON.stringify({
            razao_social: raw.razao_social,
            nome_fantasia: raw.nome_fantasia,
            cnpj: raw.cnpj,
            inscricao_estadual: raw.inscricao_estadual || null,
            email_financeiro: raw.email_financeiro || null,
            telefone: raw.telefone || null,
            endereco: raw.endereco || null,
            cidade: raw.cidade || null,
            estado: raw.estado || null,
            cep: raw.cep || null,
            banco_nome: raw.banco_nome || null,
            agencia: raw.agencia || null,
            conta: raw.conta || null,
            chave_pix: raw.chave_pix || null,
            titular_pix: raw.titular_pix || null,
            multa_atraso_percent: Number(raw.multa_atraso_percent || 2),
            juros_mensal_percent: Number(raw.juros_mensal_percent || 1),
            permissoes_json: JSON.stringify({ admin: true, colaborador: colabPerms })
          })
        });
        invalidateCache();
        showToast('Configurações institucionais e permissões atualizadas!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar configurações', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
        btn.textContent = 'Salvar Configurações da Empresa';
      }
    };
  }, 30);

  const defaultTlds = [
    { ext: '.com.br', label: 'Nacional Brasil (.com.br)', custo: 40.00, venda: 79.90 },
    { ext: '.com', label: 'Global Comercial (.com)', custo: 58.00, venda: 109.90 },
    { ext: '.net', label: 'Infraestrutura & Rede (.net)', custo: 64.00, venda: 119.90 },
    { ext: '.org', label: 'Organizações (.org)', custo: 62.00, venda: 114.90 },
    { ext: '.tech', label: 'Tecnologia & Startups (.tech)', custo: 45.00, venda: 99.90 },
    { ext: '.online', label: 'Presença Digital (.online)', custo: 25.00, venda: 69.90 },
    { ext: '.app', label: 'Aplicativos & SaaS (.app)', custo: 78.00, venda: 139.90 },
    { ext: '.io', label: 'Tech & Sistemas (.io)', custo: 195.00, venda: 299.90 }
  ];
  let savedTlds = {};
  if (cfg?.dominio_precos_json) {
    try { savedTlds = JSON.parse(cfg.dominio_precos_json) || {}; } catch (_) {}
  }

  window.nexusSetEmpresaTab = (tab) => {
    document.querySelectorAll('.empresa-tab-view').forEach((el) => { el.style.display = 'none'; });
    const target = document.getElementById(`empresa-tab-${tab}`);
    if (target) target.style.display = 'block';
    document.querySelectorAll('#empresa-tabs-bar .filter-pill').forEach((b) => b.classList.remove('active'));
    const btn = document.getElementById(`tab-btn-${tab}`);
    if (btn) btn.classList.add('active');
  };

  
  window.nexusTestarGithubConexao = async () => {
    const token = document.getElementById('cfg-gh-token')?.value || '';
    const orgName = document.getElementById('cfg-gh-org')?.value || '';
    try {
      const res = await apiRequest('/integracoes/github/testar', {
        method: 'POST',
        body: JSON.stringify({ github_token: token, github_org: orgName })
      });
      showToast(`Conectado ao GitHub: ${res.organizacao} (${res.tipo_conta} • @${res.usuario_github})`, 'success');
    } catch (err) {
      showNoticeModal({ title: 'Falha na Conexão GitHub', message: err.message, variant: 'error' });
    }
  };

  window.nexusSaveIntegracoesApi = async () => {
    const frm = document.getElementById('empresa-integracoes-form');
    const btn = document.getElementById('save-integrations-btn');
    if (!frm || !btn) return;
    const raw = Object.fromEntries(new FormData(frm));

    const precosMap = {};
    defaultTlds.forEach((t) => {
      const slugKey = t.ext.replace(/\./g, '_');
      const custoVal = Number(raw[`tld_custo_${slugKey}`] ?? t.custo);
      const vendaVal = Number(raw[`tld_venda_${slugKey}`] ?? t.venda);
      precosMap[t.ext] = {
        label: t.label,
        custo: custoVal,
        venda: vendaVal,
        destaque: ['.com.br', '.com', '.tech'].includes(t.ext),
        ativo: true
      };
    });

    btn.disabled = true;
    btn.textContent = 'Salvando Integrações...';
    try {
      await apiRequest('/empresa', {
        method: 'PUT',
        body: JSON.stringify({
          mp_ativo: raw.mp_ativo === 'true',
          mp_api_tipo: raw.mp_api_tipo || 'orders',
          mp_ambiente: raw.mp_ambiente || 'producao',
          mp_public_key: (raw.mp_public_key || '').trim() || null,
          mp_access_token: (raw.mp_access_token || '').trim() || null,
          mp_webhook_secret: (raw.mp_webhook_secret || '').trim() || null,
          registrar_provedor: raw.registrar_provedor || 'sandbox',
          registrar_api_user: (raw.registrar_api_user || '').trim() || null,
          registrar_api_key: (raw.registrar_api_key || '').trim() || null,
          registrar_client_ip: (raw.registrar_client_ip || '').trim() || null,
          github_ativo: raw.github_ativo === 'true',
          github_org: (raw.github_org || '').trim() || 'Nexus-Code-Brasil',
          github_token: (raw.github_token || '').trim() || null,
          github_visibilidade_padrao: raw.github_visibilidade_padrao || 'private',
          vercel_token: (raw.vercel_token || '').trim() || null,
          vercel_project_id: (raw.vercel_project_id || '').trim() || null,
          vercel_team_id: (raw.vercel_team_id || '').trim() || null,
          dominio_precos_json: JSON.stringify(precosMap)
        })
      });
      invalidateCache();
      showToast('Integrações Mercado Pago (Orders API), Registrador e Vercel salvas com sucesso!', 'success');
    } catch (err) {
      showNoticeModal({ title: 'Erro ao salvar integrações', message: err.message, variant: 'error' });
    } finally {
      btn.disabled = false;
      btn.textContent = 'Salvar Todas as Integrações';
    }
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Empresa, White-Label &amp; Integrações</h1>
        <span class="muted">Gerencie a identidade corporativa, permissões, Mercado Pago (Orders API) e venda automática de domínios</span>
      </div>
      ${org.slug ? `
        <div style="display:flex; align-items:center; gap:8px; background:var(--surface); border:1px solid var(--border); padding:8px 14px; border-radius:10px; font-size:12.5px;">
          <span class="muted">Plano Ativo:</span>
          <span class="badge ativo" style="text-transform:uppercase;">${esc(org.plano || 'Enterprise')}</span>
        </div>
      ` : ''}
    </div>

    <div class="filter-bar" id="empresa-tabs-bar">
      <button type="button" id="tab-btn-geral" class="filter-pill active" onclick="window.nexusSetEmpresaTab('geral')">Geral, Marca &amp; Permissões</button>
      <button type="button" id="tab-btn-integracoes" class="filter-pill" onclick="window.nexusSetEmpresaTab('integracoes')">Integrações Mercado Pago &amp; Domínios</button>
    </div>

    <!-- TAB 1: GERAL & WHITE LABEL -->
    <div id="empresa-tab-geral" class="empresa-tab-view">
    <div class="toolbar">
      <div>
        <h1>Empresa, White-Label &amp; Permissões</h1>
        <span class="muted">Gerencie a identidade visual corporativa, domínio de acesso, parâmetros fiscais, dados bancários e permissões</span>
      </div>
      ${org.slug ? `
        <div style="display:flex; align-items:center; gap:8px; background:var(--surface); border:1px solid var(--border); padding:8px 14px; border-radius:10px; font-size:12.5px;">
          <span class="muted">Plano Ativo:</span>
          <span class="badge ativo" style="text-transform:uppercase;">${esc(org.plano || 'Enterprise')}</span>
        </div>
      ` : ''}
    </div>

    <!-- Card White-Label (Logotipo, Cores, Nome & Domínio Corporativo) -->
    <form id="whitelabel-branding-form" class="card" style="margin-bottom:20px; border-left:4px solid var(--primary);">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
        <div>
          <h4 class="profile-section-title" style="font-size:16px;">Identidade Visual White-Label &amp; Domínio de Acesso</h4>
          <p class="profile-section-sub" style="margin:0;">Personalize o logotipo, a paleta cromática e o endereço de acesso da tela de login, painel administrativo e Portal do Cliente.</p>
        </div>
        <div id="wl-logo-preview" style="background:${esc(brand.cor_sidebar || '#0A1D37')}; color:#fff; padding:8px 14px; border-radius:10px; display:flex; align-items:center; gap:10px;">
          ${brand.logo_url
            ? `<img src="${esc(brand.logo_url)}" alt="Logotipo" style="max-height:32px; max-width:140px; object-fit:contain;">`
            : `<span style="font-weight:800; letter-spacing:0.04em;">${esc(brand.nome_plataforma || org.nome || 'PORTAL')}</span>`}
        </div>
      </div>

      <div class="formgrid-3" style="margin-bottom:14px;">
        <label class="field-full">Nome da Plataforma / Marca *
          <input type="text" name="nome_plataforma" value="${esc(brand.nome_plataforma || org.nome || '')}" required class="nc-input" placeholder="Ex.: Minha Organização ERP">
        </label>
        <label class="field-full">Subtítulo Institucional
          <input type="text" name="subtitulo_plataforma" value="${esc(brand.subtitulo_plataforma || '')}" class="nc-input" placeholder="Ex.: GESTÃO CORPORATIVA">
        </label>
        <label class="field-full">Tema Padrão da Interface
          <select name="tema_padrao" class="nc-input">
            <option value="light" ${(brand.tema_padrao || 'light') === 'light' ? 'selected' : ''}>Claro Executivo (Light)</option>
            <option value="dark" ${brand.tema_padrao === 'dark' ? 'selected' : ''}>Escuro Enterprise (Dark)</option>
          </select>
        </label>
      </div>

      <div class="formgrid-3" style="margin-bottom:14px;">
        <label class="field-full">Cor Primária (Ações &amp; Destaques)
          <div style="display:flex; gap:8px; align-items:center;">
            <input type="color" name="cor_primaria" value="${esc(brand.cor_primaria || '#0096B4')}" style="width:46px; height:38px; padding:2px; border:1px solid var(--border); border-radius:8px; cursor:pointer;">
            <span class="muted" style="font-size:12px;">${esc(brand.cor_primaria || '#0096B4')}</span>
          </div>
        </label>
        <label class="field-full">Cor Secundária / Hover
          <div style="display:flex; gap:8px; align-items:center;">
            <input type="color" name="cor_secundaria" value="${esc(brand.cor_secundaria || '#0A1D37')}" style="width:46px; height:38px; padding:2px; border:1px solid var(--border); border-radius:8px; cursor:pointer;">
            <span class="muted" style="font-size:12px;">${esc(brand.cor_secundaria || '#0A1D37')}</span>
          </div>
        </label>
        <label class="field-full">Cor do Menu Lateral (Sidebar)
          <div style="display:flex; gap:8px; align-items:center;">
            <input type="color" name="cor_sidebar" value="${esc(brand.cor_sidebar || '#0A1D37')}" style="width:46px; height:38px; padding:2px; border:1px solid var(--border); border-radius:8px; cursor:pointer;">
            <span class="muted" style="font-size:12px;">${esc(brand.cor_sidebar || '#0A1D37')}</span>
          </div>
        </label>
      </div>

      <div class="formgrid" style="margin-bottom:14px;">
        <label class="field-full">URL do Logotipo (ou selecione um arquivo ao lado)
          <input type="text" name="logo_url" id="wl-logo-url" value="${esc(brand.logo_url || '')}" class="nc-input" placeholder="https://... ou vazio para monograma institucional">
        </label>
        <label class="field-full">Enviar Arquivo de Logotipo (PNG, JPG ou SVG, máx. 1,5 MB)
          <input type="file" id="wl-logo-file" accept="image/*,.svg" class="nc-input">
        </label>
      </div>

      <!-- Configuração de Endereço & Domínio Próprio (Exclusivo Enterprise Full) -->
      <div style="padding:14px 16px; border:1px solid var(--border); border-radius:12px; background:var(--surface2); margin-bottom:14px;">
        <div class="formgrid">
          <label class="field-full">Subdomínio Gerenciado (Infraestrutura Nexus Code)
            <input type="text" value="${esc(org.slug || 'portal')}.nexuscodebrasil.com.br" readonly class="nc-input" style="font-weight:700; color:var(--primary);">
            <span class="muted" style="font-size:11.5px;">Endereço padrão ativo com certificado SSL gerenciado.</span>
          </label>
          ${canCustomDomain ? `
            <label class="field-full">Domínio Corporativo Próprio — CNAME (Plano Enterprise Full)
              <input type="text" name="dominio_customizado" value="${esc(org.dominio_customizado || '')}" class="nc-input" placeholder="Ex.: portal.suaempresa.com.br">
              <span class="muted" style="font-size:11.5px;">Para ativar, crie um registro <b>CNAME</b> no DNS do seu domínio apontando para <code>cname.vercel-dns.com</code>.</span>
            </label>
          ` : `
            <div class="field-full" style="display:flex; flex-direction:column; justify-content:center; gap:4px;">
              <span style="font-size:12.5px; font-weight:700;">Domínio Corporativo Próprio (CNAME)</span>
              <span class="muted" style="font-size:12px; line-height:1.45;">
                No plano <b>${esc((org.plano || 'Starter').toUpperCase())}</b>, o portal opera exclusivamente sob o subdomínio gerenciado <code>.nexuscodebrasil.com.br</code>. O apontamento de domínio próprio está disponível no plano <b>Enterprise Full</b>.
              </span>
            </div>
          `}
        </div>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <label style="display:flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600; cursor:pointer;">
          <input type="checkbox" name="ocultar_powered_by" ${brand.ocultar_powered_by ? 'checked' : ''} style="width:16px; height:16px; accent-color:var(--primary);">
          <span>Modo White-Label Integral (ocultar referência tecnológica no rodapé de autenticação)</span>
        </label>
        <button type="submit" class="btn" id="save-wl-btn">Salvar Identidade &amp; Domínio</button>
      </div>
    </form>

    <form id="empresa-config-form" class="profile-columns">
      <div class="card profile-col-card">
        <div>
          <h4 class="profile-section-title">1. Dados Institucionais &amp; Fiscais</h4>
          <p class="profile-section-sub">Informações exibidas nas propostas comerciais, holerites, recibos e Portal do Cliente.</p>
          <div class="profile-grid">
            <label class="field-full">Razão Social *
              <input type="text" name="razao_social" value="${esc(cfg?.razao_social || org.nome || 'Nexus Code Brasil Tecnologia Ltda')}" required class="nc-input">
            </label>
            <label class="field-full">Nome Fantasia *
              <input type="text" name="nome_fantasia" value="${esc(cfg?.nome_fantasia || org.nome || 'Nexus Code Brasil')}" required class="nc-input">
            </label>
            <label class="field-full">CNPJ
              <input type="text" name="cnpj" value="${esc(cfg?.cnpj || '')}" class="nc-input">
            </label>
            <label class="field-full">Inscrição Estadual / Municipal
              <input type="text" name="inscricao_estadual" value="${esc(cfg?.inscricao_estadual || '')}" class="nc-input">
            </label>
            <label class="field-full">E-mail Financeiro / Comercial
              <input type="email" name="email_financeiro" value="${esc(cfg?.email_financeiro || '')}" class="nc-input">
            </label>
            <label class="field-full">Telefone Corporativo
              <input type="text" name="telefone" value="${esc(cfg?.telefone || '')}" class="nc-input">
            </label>
            <label class="field-full">Endereço
              <input type="text" name="endereco" value="${esc(cfg?.endereco || '')}" class="nc-input">
            </label>
            <label class="field-full">Cidade / UF
              <div style="display:grid; grid-template-columns:1fr 70px; gap:8px;">
                <input type="text" name="cidade" value="${esc(cfg?.cidade || '')}" class="nc-input">
                <input type="text" name="estado" value="${esc(cfg?.estado || '')}" maxlength="2" class="nc-input">
              </div>
            </label>
          </div>
        </div>

        <div class="profile-section">
          <h4 class="profile-section-title">2. Dados Bancários &amp; Chave PIX (Portal do Cliente)</h4>
          <p class="profile-section-sub">Parâmetros exibidos automaticamente ao cliente na liquidação de faturas.</p>
          <div class="profile-grid">
            <label class="field-full">Chave PIX Oficial *
              <input type="text" name="chave_pix" value="${esc(cfg?.chave_pix || '')}" class="nc-input">
            </label>
            <label class="field-full">Favorecido / Titular PIX
              <input type="text" name="titular_pix" value="${esc(cfg?.titular_pix || '')}" class="nc-input">
            </label>
            <label class="field-full">Instituição Bancária
              <input type="text" name="banco_nome" value="${esc(cfg?.banco_nome || '')}" class="nc-input">
            </label>
            <label class="field-full">Agência / Conta
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <input type="text" name="agencia" placeholder="Agência" value="${esc(cfg?.agencia || '')}" class="nc-input">
                <input type="text" name="conta" placeholder="Conta" value="${esc(cfg?.conta || '')}" class="nc-input">
              </div>
            </label>
            <label class="field-full">Multa por Atraso (%)
              <input type="number" step="0.1" name="multa_atraso_percent" value="${cfg?.multa_atraso_percent ?? 2.0}" class="nc-input">
            </label>
            <label class="field-full">Juros Mensais (%)
              <input type="number" step="0.1" name="juros_mensal_percent" value="${cfg?.juros_mensal_percent ?? 1.0}" class="nc-input">
            </label>
          </div>
        </div>
      </div>

      <div class="card profile-col-card">
        <div>
          <h4 class="profile-section-title">3. Matriz de Permissões Granulares por Perfil</h4>
          <p class="profile-section-sub">Administradores possuem acesso irrestrito aos módulos contratados. Defina os módulos visíveis para o perfil <b>Colaborador</b>.</p>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            ${modulosLista.map(([key, label]) => `
              <label style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid var(--border); border-radius:8px; background:var(--surface2); font-size:12.5px; font-weight:600; cursor:pointer;">
                <input type="checkbox" name="perm_colab_${key}" ${perms.colaborador[key] ? 'checked' : ''} style="width:16px; height:16px; accent-color:var(--primary);">
                <span>${esc(label)}</span>
              </label>
            `).join('')}
          </div>
        </div>

        <div class="profile-footer-actions">
          <button type="submit" class="btn" id="save-empresa-btn">Salvar Configurações da Empresa</button>
        </div>
      </div>
    </form>
    </div>

    <!-- TAB 2: INTEGRAÇÕES & APIS -->
    <div id="empresa-tab-integracoes" class="empresa-tab-view" style="display:none;">
      <form id="empresa-integracoes-form" style="display:flex; flex-direction:column; gap:20px;">
        <div class="profile-columns">
          <div class="card profile-col-card">
            <div>
              <h4 class="profile-section-title">1. Mercado Pago (Checkout, PIX &amp; Folha Payouts)</h4>
              <p class="profile-section-sub">Compatível nativamente com a nova <b>API de Orders (/v1/orders)</b> do Mercado Pago e com a API de Payments.</p>
              <div class="profile-grid">
                <label class="field-full">Status do Gateway *
                  <select name="mp_ativo" class="nc-input">
                    <option value="false" ${!cfg?.mp_ativo ? 'selected' : ''}>Desativado</option>
                    <option value="true" ${cfg?.mp_ativo ? 'selected' : ''}>Ativo e Operacional</option>
                  </select>
                </label>
                <label class="field-full">Tipo de API Mercado Pago *
                  <select name="mp_api_tipo" class="nc-input">
                    <option value="orders" ${(cfg?.mp_api_tipo || 'orders') === 'orders' ? 'selected' : ''}>API de Orders (/v1/orders) — Nova API Recomendada</option>
                    <option value="payments" ${cfg?.mp_api_tipo === 'payments' ? 'selected' : ''}>API de Payments (/v1/payments) — Legado</option>
                  </select>
                </label>
                <label class="field-full">Ambiente de Operação
                  <select name="mp_ambiente" class="nc-input">
                    <option value="producao" ${(cfg?.mp_ambiente || 'producao') === 'producao' ? 'selected' : ''}>Produção (Recebimentos Reais)</option>
                    <option value="sandbox" ${cfg?.mp_ambiente === 'sandbox' ? 'selected' : ''}>Sandbox (Credenciais de Teste)</option>
                  </select>
                </label>
                <label class="field-full">Public Key
                  <input type="text" name="mp_public_key" value="${esc(cfg?.mp_public_key || '')}" placeholder="APP_USR-..." class="nc-input">
                </label>
                <label class="field-full">Access Token *
                  <input type="password" name="mp_access_token" value="${esc(cfg?.mp_access_token || '')}" placeholder="APP_USR-..." class="nc-input">
                </label>
                <label class="field-full">Webhook Secret (Assinatura Secreta HMAC)
                  <input type="password" name="mp_webhook_secret" value="${esc(cfg?.mp_webhook_secret || '')}" placeholder="Cole a assinatura secreta do Webhook" class="nc-input">
                </label>
              </div>
              <div style="background:rgba(0,180,216,0.09); border:1px solid rgba(0,180,216,0.35); border-radius:10px; padding:12px 14px; margin-top:14px; font-size:12px; line-height:1.5;">
                <div><b>URL de Notificação Webhook:</b></div>
                <code style="display:block; margin:4px 0; font-weight:700; color:var(--primary);">https://www.nexuscodebrasil.com.br/api/webhooks/mercadopago?org_id=${org.id || 1}</code>
                <span class="muted">No painel Webhooks do Mercado Pago, marque o evento <b>Orders</b> (se usar API de Orders) ou <b>Pagamentos</b> (se usar API de Payments).</span>
              </div>
            </div>
          </div>

          <div class="card profile-col-card">
            <div>
              <h4 class="profile-section-title">2. Registrador de Domínios &amp; Auto-SSL Vercel</h4>
              <p class="profile-section-sub">Após o pagamento confirmado no Mercado Pago, o sistema registra o domínio e emite o certificado HTTPS sozinho.</p>
              <div class="profile-grid">
                <label class="field-full">Provedor Registrador (Revenda)
                  <select name="registrar_provedor" class="nc-input">
                    <option value="sandbox" ${(cfg?.registrar_provedor || 'sandbox') === 'sandbox' ? 'selected' : ''}>Sandbox (Homologação / Registro Simulado)</option>
                    <option value="namecheap" ${cfg?.registrar_provedor === 'namecheap' ? 'selected' : ''}>Namecheap API (Registro + DNS Automático)</option>
                    <option value="resellerclub" ${cfg?.registrar_provedor === 'resellerclub' ? 'selected' : ''}>ResellerClub API</option>
                  </select>
                </label>
                <label class="field-full">API User / Auth-ID (Registrador)
                  <input type="text" name="registrar_api_user" value="${esc(cfg?.registrar_api_user || '')}" class="nc-input">
                </label>
                <label class="field-full">API Key / Token (Registrador)
                  <input type="password" name="registrar_api_key" value="${esc(cfg?.registrar_api_key || '')}" class="nc-input">
                </label>
                <label class="field-full">Client IP Autorizado (Namecheap)
                  <input type="text" name="registrar_client_ip" value="${esc(cfg?.registrar_client_ip || '')}" placeholder="Ex.: 177.x.x.x" class="nc-input">
                </label>
                <label class="field-full">Vercel API Token (Para SSL/HTTPS Automático)
                  <input type="password" name="vercel_token" value="${esc(cfg?.vercel_token || '')}" class="nc-input">
                </label>
                <label class="field-full">Vercel Project ID
                  <input type="text" name="vercel_project_id" value="${esc(cfg?.vercel_project_id || '')}" placeholder="prj_..." class="nc-input">
                </label>
                <label class="field-full">Vercel Team ID (Opcional)
                  <input type="text" name="vercel_team_id" value="${esc(cfg?.vercel_team_id || '')}" placeholder="team_..." class="nc-input">
                </label>
              </div>
            </div>
          </div>
        </div>

                <div class="card profile-col-card" style="border-left: 4px solid #00B4D8;">
          <div>
            <h4 class="profile-section-title">GitHub Enterprise &amp; Automação de Repositórios</h4>
            <p class="profile-section-sub">Cria repositórios automaticamente na organização GitHub da empresa ao criar projetos e habilita a IDE VS Code / Codespaces integrada.</p>
            <div class="profile-grid">
              <label class="field-full">Status Integração GitHub *
                <select name="github_ativo" class="nc-input">
                  <option value="false" ${!cfg?.github_ativo ? 'selected' : ''}>Desativado</option>
                  <option value="true" ${cfg?.github_ativo ? 'selected' : ''}>Ativo (Criar Repos &amp; IDE Automáticos)</option>
                </select>
              </label>
              <label class="field-full">Organização / Usuário GitHub da Empresa *
                <input type="text" name="github_org" id="cfg-gh-org" value="${esc(cfg?.github_org || 'Nexus-Code-Brasil')}" placeholder="Ex.: Nexus-Code-Brasil" class="nc-input">
              </label>
              <label class="field-full">GitHub Personal Access Token (PAT) *
                <input type="password" name="github_token" id="cfg-gh-token" value="${esc(cfg?.github_token || '')}" placeholder="ghp_... ou github_pat_..." class="nc-input">
              </label>
              <label class="field-full">Visibilidade Padrão dos Novos Projetos
                <select name="github_visibilidade_padrao" class="nc-input">
                  <option value="private" ${(cfg?.github_visibilidade_padrao || 'private') === 'private' ? 'selected' : ''}>Privado (Recomendado para Clientes)</option>
                  <option value="public" ${cfg?.github_visibilidade_padrao === 'public' ? 'selected' : ''}>Público</option>
                </select>
              </label>
            </div>
            <div style="margin-top:12px; display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
              <span class="muted" style="font-size:11.5px;">Escopos necessários no token: <code>repo</code> e <code>workflow</code>.</span>
              <button type="button" class="btn secondary" style="padding:6px 12px; font-size:12px;" onclick="window.nexusTestarGithubConexao()">Testar Conexão GitHub</button>
            </div>
          </div>
        </div>

        <div class="card">
          <h4 class="profile-section-title">3. Tabela de Preços Anuais por Extensão de Domínio (Sua Margem de Lucro)</h4>
          <p class="profile-section-sub">Defina o custo base no registrador e o preço anual cobrado do cliente no site e no Portal do Cliente.</p>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Extensão</th>
                  <th>Descrição Comercial</th>
                  <th>Custo Registrador (R$/ano)</th>
                  <th>Preço Venda Cliente (R$/ano)</th>
                </tr>
              </thead>
              <tbody>
                ${defaultTlds.map((t) => {
                  const cur = savedTlds[t.ext] || t;
                  const slugKey = t.ext.replace(/\./g, '_');
                  return `
                    <tr>
                      <td><b style="color:var(--primary);">${esc(t.ext)}</b></td>
                      <td>${esc(t.label)}</td>
                      <td><input type="number" step="0.01" min="0" name="tld_custo_${slugKey}" value="${Number(cur.custo ?? t.custo).toFixed(2)}" class="nc-input" style="max-width:140px;"></td>
                      <td><input type="number" step="0.01" min="0" name="tld_venda_${slugKey}" value="${Number(cur.venda ?? t.venda).toFixed(2)}" class="nc-input" style="max-width:140px; font-weight:700;"></td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
          <div class="profile-footer-actions" style="margin-top:16px;">
            <button type="button" class="btn" id="save-integrations-btn" onclick="window.nexusSaveIntegracoesApi()">Salvar Todas as Integrações</button>
          </div>
        </div>
      </form>
    </div>
  `;
}

// ==================== 8B. GESTÃO MASTER SAAS: PORTAIS COMPRADORES, SUBDOMÍNIOS & MÓDULOS ====================
let saasMasterTab = 'portais'; // 'portais' | 'planos'

export async function renderSaasMasterView(ctx) {
  const { matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const data = await apiRequest('/saas/dashboard');
  const kpi = data.kpi || {};
  const orgs = (data.organizacoes || []).filter((o) =>
    matchSearch([o.nome, o.slug, o.dominio_customizado, o.plano, o.status_assinatura])
  );
  const planos = data.planos || [];

  const allSaasModules = [
    ['dashboard', 'Dashboard Executivo'],
    ['projetos', 'Projetos & Homologação'],
    ['tarefas', 'Tarefas & Quadro Planner'],
    ['timesheet', 'Timesheet & Rentabilidade'],
    ['orcamentos', 'Solicitações & Orçamentos'],
    ['propostas', 'Propostas Comerciais'],
    ['clientes', 'Clientes, Leads & Funil'],
    ['chamados', 'Suporte & Chamados'],
    ['financeiro_dre', 'DRE Gerencial & Fluxo'],
    ['faturas', 'Faturas & Cobranças'],
    ['despesas', 'Contas a Pagar & Reembolsos'],
    ['contratos', 'Contratos Recorrentes MRR'],
    ['ponto', 'Gestão de Ponto Eletrônico'],
    ['holerite', 'Holerite & Folha Automática'],
    ['ativos', 'Ativos, Domínios & Cofre'],
    ['usuarios', 'Usuários & CBO'],
    ['empresa', 'Configurações & White-Label'],
    ['auditoria', 'Logs de Auditoria'],
    ['portal_cliente', 'Portal do Cliente Externo']
  ];

  window.nexusSetSaasTab = (t) => {
    saasMasterTab = t;
    render();
  };

  window.nexusImpersonateTenant = async (orgId, orgName) => {
    try {
      const res = await apiRequest(`/saas/organizacoes/${orgId}/impersonate`, { method: 'POST' });
      setSession(res.access_token, res.usuario, res.tenant_slug);
      showToast(`Conectado ao ambiente "${orgName}" como Administrador.`, 'success');
      setTimeout(() => {
        window.location.href = `./index.html?tenant=${encodeURIComponent(res.tenant_slug)}`;
      }, 400);
    } catch (err) {
      showNoticeModal({ title: 'Falha ao acessar ambiente', message: err.message, variant: 'error' });
    }
  };

  window.nexusQuickToggleTenantStatus = async (orgId, nextStatus) => {
    try {
      await apiRequest(`/saas/organizacoes/${orgId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status_assinatura: nextStatus })
      });
      showToast(`Status da assinatura atualizado para "${nextStatus.toUpperCase()}".`, 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro ao atualizar status', message: err.message, variant: 'error' });
    }
  };

  window.nexusOpenTenantModal = (orgObj = null) => {
    const isEdit = Boolean(orgObj && orgObj.id);
    const initialPlano = (orgObj?.plano || 'pro').toLowerCase();
    const isEntInitial = initialPlano === 'enterprise' || Boolean(orgObj?.is_master);

    let mods = {};
    allSaasModules.forEach(([k]) => { mods[k] = true; });
    if (orgObj?.modulos_json) {
      try { mods = { ...mods, ...JSON.parse(orgObj.modulos_json) }; } catch (_) {}
    }
    let brand = {
      nome_plataforma: orgObj?.nome || '',
      subtitulo_plataforma: 'GESTÃO EMPRESARIAL',
      logo_url: '',
      cor_primaria: '#0096B4',
      cor_secundaria: '#0A1D37',
      cor_sidebar: '#0A1D37',
      tema_padrao: 'light',
      ocultar_powered_by: false
    };
    if (orgObj?.branding_json) {
      try { brand = { ...brand, ...JSON.parse(orgObj.branding_json) }; } catch (_) {}
    }

    holeriteContainer.innerHTML = `
      <form id="saas-tenant-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.sparkles}</div>
            <div>
              <h2>${isEdit ? `Gerenciar Ambiente — ${esc(orgObj.nome)}` : 'Provisionar Novo Ambiente Corporativo'}</h2>
              <p class="modal-subtitle">Configure identificador de subdomínio, plano contratado, módulos habilitados e identidade White-Label</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>

        <div class="modal-body">
          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">1</span> Organização Contratante &amp; Endereçamento</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
              <label>Razão / Nome da Organização *
                <input type="text" name="nome" id="st-nome" required value="${esc(orgObj?.nome || '')}" placeholder="Ex.: Alpha Soluções Ltda">
              </label>
              <label>Subdomínio Gerenciado *
                <div style="display:flex; align-items:center; gap:4px;">
                  <input type="text" name="slug" id="st-slug" required value="${esc(orgObj?.slug || '')}" placeholder="alpha" style="font-weight:700;">
                  <span class="muted" style="font-size:12px; white-space:nowrap;">.nexuscodebrasil.com.br</span>
                </div>
              </label>
              <label>Plano Contratado *
                <select name="plano" id="st-plano">
                  ${planos.map((pl) => `<option value="${esc(pl.codigo)}" data-price="${pl.preco_mensal}" data-users="${pl.limite_usuarios}" data-clients="${pl.limite_clientes}" data-mods='${esc(pl.modulos_json || "{}")}' ${initialPlano === pl.codigo ? 'selected' : ''}>${esc(pl.nome)} (${formatMoney(pl.preco_mensal)}/mês)</option>`).join('')}
                </select>
              </label>
              <label>Domínio Corporativo Próprio — CNAME (Exclusivo Enterprise Full)
                <input type="text" name="dominio_customizado" id="st-dominio-custom" ${isEntInitial ? '' : 'disabled'} value="${esc(isEntInitial ? (orgObj?.dominio_customizado || '') : '')}" placeholder="${isEntInitial ? 'Ex.: portal.empresa.com.br' : 'Exclusivo do plano Enterprise Full'}">
                <span id="st-dominio-hint" class="muted" style="font-size:11px;">
                  ${isEntInitial
                    ? 'Habilitado: cliente pode apontar domínio próprio via CNAME para cname.vercel-dns.com.'
                    : 'Planos Starter e Pro operam exclusivamente sob subdomínio .nexuscodebrasil.com.br.'}
                </span>
              </label>
              <label>Status da Assinatura *
                <select name="status_assinatura">
                  <option value="ativo" ${(orgObj?.status_assinatura || 'ativo') === 'ativo' ? 'selected' : ''}>Ativo (Operação Liberada)</option>
                  <option value="trial" ${orgObj?.status_assinatura === 'trial' ? 'selected' : ''}>Avaliação (Trial 14 dias)</option>
                  <option value="inadimplente" ${orgObj?.status_assinatura === 'inadimplente' ? 'selected' : ''}>Inadimplente (Aviso Financeiro)</option>
                  <option value="suspenso" ${orgObj?.status_assinatura === 'suspenso' ? 'selected' : ''}>Suspenso (Acesso Bloqueado)</option>
                </select>
              </label>
              <label>Mensalidade Contratada (R$) *
                <input type="number" step="0.01" min="0" name="valor_mensal" id="st-valor" value="${orgObj ? Number(orgObj.valor_mensal).toFixed(2) : '397.00'}" required>
              </label>
              <label>Limite de Usuários Internos *
                <input type="number" min="1" name="limite_usuarios" id="st-lim-users" value="${orgObj?.limite_usuarios ?? 15}" required>
              </label>
              <label>Limite de Clientes/Leads *
                <input type="number" min="1" name="limite_clientes" id="st-lim-clients" value="${orgObj?.limite_clientes ?? 1000}" required>
              </label>
            </div>
          </div>

          ${!isEdit ? `
            <div class="modal-section-card">
              <div class="modal-section-title"><span class="modal-section-step">2</span> Administrador Inicial &amp; Integração Financeira</div>
              <div class="formgrid">
                <label>Nome do Administrador *
                  <input type="text" name="admin_nome" required placeholder="Responsável administrativo">
                </label>
                <label>E-mail Corporativo de Acesso *
                  <input type="email" name="admin_email" required placeholder="admin@organizacao.com.br">
                </label>
                <label>Senha Provisória *
                  <input type="text" name="admin_senha" required minlength="6" value="Mudar@2026">
                </label>
                <label>Telefone / WhatsApp
                  <input type="text" name="telefone" placeholder="(27) 99999-9999">
                </label>
              </div>
              <label style="display:flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600; cursor:pointer; margin-top:4px;">
                <input type="checkbox" name="gerar_contrato_master" checked style="width:16px; height:16px; accent-color:var(--primary);">
                <span>Implantação Assistida: Cadastrar automaticamente como Cliente, Contrato Recorrente MRR e Fatura inicial no Financeiro Master</span>
              </label>
            </div>
          ` : ''}

          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">${isEdit ? '2' : '3'}</span> Controle Granular de Módulos Habilitados</div>
            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px;">
              ${allSaasModules.map(([k, label]) => `
                <label style="display:flex; align-items:center; gap:7px; padding:7px 9px; border:1px solid var(--border); border-radius:8px; background:var(--surface); font-size:12px; font-weight:600; cursor:pointer;">
                  <input type="checkbox" name="tenant_mod_${k}" ${mods[k] !== false ? 'checked' : ''} style="width:15px; height:15px; accent-color:var(--primary);">
                  <span>${esc(label)}</span>
                </label>
              `).join('')}
            </div>
          </div>

          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">${isEdit ? '3' : '4'}</span> Identidade Visual White-Label (Logotipo &amp; Paleta)</div>
            <div class="formgrid-3">
              <label>Nome Exibido no Portal
                <input type="text" name="wl_nome" id="st-wl-nome" value="${esc(brand.nome_plataforma || '')}" placeholder="Nome da Organização">
              </label>
              <label>Cor Primária
                <input type="color" name="wl_cor_primaria" value="${esc(brand.cor_primaria || '#0096B4')}" style="height:40px; padding:2px;">
              </label>
              <label>Cor do Menu Lateral
                <input type="color" name="wl_cor_sidebar" value="${esc(brand.cor_sidebar || '#0A1D37')}" style="height:40px; padding:2px;">
              </label>
            </div>
            <div class="formgrid">
              <label>URL do Logotipo (Opcional)
                <input type="text" name="wl_logo_url" id="st-wl-logo-url" value="${esc(brand.logo_url || '')}" placeholder="https://...">
              </label>
              <label>Ou Enviar Arquivo de Logotipo
                <input type="file" id="st-wl-logo-file" accept="image/*,.svg">
              </label>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="st-save-btn">${isEdit ? 'Salvar Alterações' : 'Provisionar Ambiente'}</button>
        </div>
      </form>
    `;

    const nomeInp = document.getElementById('st-nome');
    const slugInp = document.getElementById('st-slug');
    const wlNomeInp = document.getElementById('st-wl-nome');
    if (!isEdit && nomeInp && slugInp) {
      nomeInp.addEventListener('input', () => {
        const autoSlug = nomeInp.value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 35);
        slugInp.value = autoSlug;
        if (wlNomeInp) wlNomeInp.value = nomeInp.value.toUpperCase();
      });
    }

    const planoSel = document.getElementById('st-plano');
    const domInp = document.getElementById('st-dominio-custom');
    const domHint = document.getElementById('st-dominio-hint');
    planoSel?.addEventListener('change', () => {
      const opt = planoSel.selectedOptions[0];
      if (!opt) return;
      const isEnt = opt.value.toLowerCase() === 'enterprise' || Boolean(orgObj?.is_master);
      if (domInp) {
        domInp.disabled = !isEnt;
        if (!isEnt) {
          domInp.value = '';
          domInp.placeholder = 'Exclusivo do plano Enterprise Full';
        } else {
          domInp.placeholder = 'Ex.: portal.empresa.com.br';
        }
      }
      if (domHint) {
        domHint.textContent = isEnt
          ? 'Habilitado: cliente pode apontar domínio próprio via CNAME para cname.vercel-dns.com.'
          : 'Planos Starter e Pro operam exclusivamente sob subdomínio .nexuscodebrasil.com.br.';
      }

      document.getElementById('st-valor').value = Number(opt.dataset.price || 0).toFixed(2);
      document.getElementById('st-lim-users').value = opt.dataset.users || 10;
      document.getElementById('st-lim-clients').value = opt.dataset.clients || 200;
      try {
        const pMods = JSON.parse(opt.dataset.mods || '{}');
        allSaasModules.forEach(([k]) => {
          const cb = document.querySelector(`[name="tenant_mod_${k}"]`);
          if (cb && typeof pMods[k] === 'boolean') cb.checked = pMods[k];
        });
      } catch (_) {}
    });

    document.getElementById('st-wl-logo-file')?.addEventListener('change', async (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      if (f.size > 1.5 * 1024 * 1024) {
        showToast('Imagem deve ter no máximo 1,5 MB.', 'error');
        return;
      }
      document.getElementById('st-wl-logo-url').value = await readFileAsDataUrl(f);
      showToast('Logotipo carregado.', 'info');
    });

    document.getElementById('saas-tenant-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('st-save-btn');
      const formEl = e.target;
      const raw = Object.fromEntries(new FormData(formEl));
      const isEntSelected = (raw.plano || '').toLowerCase() === 'enterprise' || Boolean(orgObj?.is_master);

      const selectedMods = {};
      allSaasModules.forEach(([k]) => {
        selectedMods[k] = Boolean(formEl.querySelector(`[name="tenant_mod_${k}"]`)?.checked);
      });

      const brandingObj = {
        ...brand,
        nome_plataforma: (raw.wl_nome || raw.nome).trim().toUpperCase(),
        logo_url: (raw.wl_logo_url || '').trim(),
        cor_primaria: raw.wl_cor_primaria || '#0096B4',
        cor_secundaria: raw.wl_cor_sidebar || '#0A1D37',
        cor_sidebar: raw.wl_cor_sidebar || '#0A1D37'
      };

      const customDomainVal = isEntSelected && raw.dominio_customizado
        ? raw.dominio_customizado.trim()
        : null;

      btn.disabled = true;
      btn.textContent = isEdit ? 'Salvando...' : 'Provisionando Ambiente...';
      try {
        if (isEdit) {
          await apiRequest(`/saas/organizacoes/${orgObj.id}`, {
            method: 'PATCH',
            body: JSON.stringify({
              nome: raw.nome.trim(),
              slug: raw.slug.trim(),
              dominio_customizado: customDomainVal,
              plano: raw.plano,
              status_assinatura: raw.status_assinatura,
              valor_mensal: Number(raw.valor_mensal || 0),
              limite_usuarios: Number(raw.limite_usuarios || 10),
              limite_clientes: Number(raw.limite_clientes || 200),
              modulos_json: JSON.stringify(selectedMods),
              branding_json: JSON.stringify(brandingObj)
            })
          });
          showToast('Ambiente corporativo atualizado com sucesso!', 'success');
        } else {
          await apiRequest('/saas/organizacoes', {
            method: 'POST',
            body: JSON.stringify({
              nome: raw.nome.trim(),
              slug: raw.slug.trim(),
              dominio_customizado: customDomainVal,
              plano: raw.plano,
              status_assinatura: raw.status_assinatura,
              valor_mensal: Number(raw.valor_mensal || 0),
              limite_usuarios: Number(raw.limite_usuarios || 10),
              limite_clientes: Number(raw.limite_clientes || 200),
              modulos_json: JSON.stringify(selectedMods),
              branding_json: JSON.stringify(brandingObj),
              admin_nome: raw.admin_nome.trim(),
              admin_email: raw.admin_email.trim(),
              admin_senha: raw.admin_senha,
              telefone: raw.telefone || null,
              gerar_contrato_master: Boolean(formEl.querySelector('[name="gerar_contrato_master"]')?.checked)
            })
          });
          invalidateCache();
          showToast('Novo ambiente corporativo provisionado!', 'success');
        }
        holeriteDialog.close();
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar ambiente', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusOpenPlanoSaasModal = (plObj = null) => {
    const isEdit = Boolean(plObj && plObj.id);
    let mods = {};
    allSaasModules.forEach(([k]) => { mods[k] = true; });
    if (plObj?.modulos_json) {
      try { mods = { ...mods, ...JSON.parse(plObj.modulos_json) }; } catch (_) {}
    }
    const recursosTxt = safeJsonArray(plObj?.recursos_json).join('\n');

    holeriteContainer.innerHTML = `
      <form id="saas-plano-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.dollar}</div>
            <div>
              <h2>${isEdit ? `Editar Plano — ${esc(plObj.nome)}` : 'Novo Plano Corporativo'}</h2>
              <p class="modal-subtitle">Os planos ativos são sincronizados automaticamente com a vitrine institucional</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>

        <div class="modal-body">
          <div class="modal-section-card">
            <div class="formgrid">
              <label>Código Interno (Slug) *
                <input type="text" name="codigo" ${isEdit ? 'readonly' : 'required'} value="${esc(plObj?.codigo || '')}" placeholder="ex.: enterprise">
              </label>
              <label>Nome Comercial do Plano *
                <input type="text" name="nome" required value="${esc(plObj?.nome || '')}" placeholder="Ex.: Enterprise Full ERP + RH">
              </label>
              <label>Mensalidade (R$) *
                <input type="number" step="0.01" min="0" name="preco_mensal" required value="${plObj ? Number(plObj.preco_mensal).toFixed(2) : '397.00'}">
              </label>
              <label>Ordem de Exibição
                <input type="number" min="1" name="ordem" value="${plObj?.ordem ?? (planos.length + 1)}">
              </label>
              <label>Limite de Usuários *
                <input type="number" min="1" name="limite_usuarios" required value="${plObj?.limite_usuarios ?? 15}">
              </label>
              <label>Limite de Clientes *
                <input type="number" min="1" name="limite_clientes" required value="${plObj?.limite_clientes ?? 1000}">
              </label>
              <label>Destaque Comercial
                <select name="destaque">
                  <option value="false" ${!plObj?.destaque ? 'selected' : ''}>Padrão</option>
                  <option value="true" ${plObj?.destaque ? 'selected' : ''}>Destaque ("Mais Vendido")</option>
                </select>
              </label>
              <label>Visibilidade
                <select name="ativo">
                  <option value="true" ${plObj?.ativo !== false ? 'selected' : ''}>Ativo na Vitrine</option>
                  <option value="false" ${plObj?.ativo === false ? 'selected' : ''}>Oculto</option>
                </select>
              </label>
            </div>
            <label class="field-full">Descrição Executiva
              <input type="text" name="subtitulo" value="${esc(plObj?.subtitulo || '')}" placeholder="Posicionamento comercial do plano">
            </label>
            <label class="field-full">Recursos &amp; Diferenciais Listados (1 por linha)
              <textarea name="recursos_txt" rows="3">${esc(recursosTxt)}</textarea>
            </label>
          </div>

          <div class="modal-section-card">
            <div class="modal-section-title">Módulos Inclusos por Padrão neste Plano</div>
            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px;">
              ${allSaasModules.map(([k, label]) => `
                <label style="display:flex; align-items:center; gap:7px; padding:7px 9px; border:1px solid var(--border); border-radius:8px; background:var(--surface); font-size:12px; font-weight:600; cursor:pointer;">
                  <input type="checkbox" name="plan_mod_${k}" ${mods[k] !== false ? 'checked' : ''} style="width:15px; height:15px; accent-color:var(--primary);">
                  <span>${esc(label)}</span>
                </label>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="pl-save-btn">Salvar Plano</button>
        </div>
      </form>
    `;

    document.getElementById('saas-plano-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('pl-save-btn');
      const formEl = e.target;
      const raw = Object.fromEntries(new FormData(formEl));
      const pMods = {};
      allSaasModules.forEach(([k]) => {
        pMods[k] = Boolean(formEl.querySelector(`[name="plan_mod_${k}"]`)?.checked);
      });
      const recArr = String(raw.recursos_txt || '').split('\n').map((l) => l.trim()).filter(Boolean);

      btn.disabled = true;
      try {
        const payload = {
          codigo: raw.codigo.trim(),
          nome: raw.nome.trim(),
          subtitulo: raw.subtitulo || null,
          preco_mensal: Number(raw.preco_mensal || 0),
          limite_usuarios: Number(raw.limite_usuarios || 10),
          limite_clientes: Number(raw.limite_clientes || 500),
          destaque: raw.destaque === 'true',
          ativo: raw.ativo === 'true',
          ordem: Number(raw.ordem || 1),
          modulos_json: JSON.stringify(pMods),
          recursos_json: JSON.stringify(recArr)
        };
        await apiRequest(isEdit ? `/saas/planos/${plObj.id}` : '/saas/planos', {
          method: isEdit ? 'PATCH' : 'POST',
          body: JSON.stringify(payload)
        });
        holeriteDialog.close();
        showToast('Plano salvo com sucesso!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar plano', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Portais &amp; Clientes SaaS (White-Label Multi-Tenant)</h1>
        <span class="muted">Provisione ambientes corporativos isolados, gerencie subdomínios, domínios Enterprise (CNAME) e planos</span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button type="button" class="btn secondary" onclick="window.nexusOpenPlanoSaasModal(null)">${ICONS.plus}<span>Novo Plano</span></button>
        <button type="button" class="btn" onclick="window.nexusOpenTenantModal(null)">${ICONS.plus}<span>Novo Ambiente Corporativo</span></button>
      </div>
    </div>

    <div class="grid" style="margin-bottom:20px;">
      <div class="card metric">
        <span class="title">MRR SaaS Mensal</span>
        <strong style="color:var(--ok);">${formatMoney(kpi.mrr_saas || 0)}</strong>
        <span class="pill-info">Receita recorrente dos contratos ativos</span>
      </div>
      <div class="card metric">
        <span class="title">Ambientes Provisionados</span>
        <strong>${kpi.total_portais || 0}</strong>
        <span class="pill-info">${kpi.portais_ativos || 0} ativo(s) • ${kpi.portais_trial || 0} em avaliação</span>
      </div>
      <div class="card metric">
        <span class="title">Em Período de Avaliação</span>
        <strong style="color:var(--primary);">${kpi.portais_trial || 0}</strong>
        <span class="pill-info">Onboarding comercial (14 dias)</span>
      </div>
      <div class="card metric">
        <span class="title">Inadimplentes / Suspensos</span>
        <strong style="color:${(kpi.portais_inadimplentes || 0) > 0 ? 'var(--danger)' : 'var(--text)'};">${kpi.portais_inadimplentes || 0}</strong>
        <span class="pill-info">Bloqueio preventivo automático</span>
      </div>
    </div>

    <div class="filter-bar">
      <button type="button" class="filter-pill ${saasMasterTab === 'portais' ? 'active' : ''}" onclick="window.nexusSetSaasTab('portais')">
        Ambientes Contratantes (${orgs.length})
      </button>
      <button type="button" class="filter-pill ${saasMasterTab === 'planos' ? 'active' : ''}" onclick="window.nexusSetSaasTab('planos')">
        Planos Comercializados (${planos.length})
      </button>
    </div>

    ${saasMasterTab === 'portais' ? `
      <div class="card table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Organização</th>
              <th>Endereçamento &amp; Domínio</th>
              <th>Plano &amp; Mensalidade</th>
              <th>Capacidade (Usuários / Clientes)</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            ${orgs.map((o) => {
              const previewUrl = `../login.html?tenant=${encodeURIComponent(o.slug)}`;
              const activeModsCount = o.modulos_json
                ? Object.values(JSON.parse(o.modulos_json)).filter(Boolean).length
                : allSaasModules.length;
              const isEnt = (o.plano || '').toLowerCase() === 'enterprise' || o.is_master;
              return `
                <tr>
                  <td>
                    <b>${esc(o.nome)}</b> ${o.is_master ? '<span class="badge ativo" style="font-size:10px;">MASTER</span>' : ''}
                    <div class="muted" style="font-size:11.5px;">${activeModsCount} módulo(s) ativo(s)</div>
                  </td>
                  <td>
                    <div style="font-weight:700; color:var(--primary); font-size:12.5px;">${esc(o.slug)}.nexuscodebrasil.com.br</div>
                    ${isEnt && o.dominio_customizado
                      ? `<div style="font-size:11.5px; color:var(--ok); font-weight:700;">Domínio Próprio (CNAME): ${esc(o.dominio_customizado)}</div>`
                      : `<div class="muted" style="font-size:11px;">${isEnt ? 'Domínio próprio disponível (não configurado)' : 'Subdomínio gerenciado'}</div>`}
                    <a href="${previewUrl}" target="_blank" rel="noopener" style="font-size:11px; color:var(--text-light);">Abrir autenticação White-Label ↗</a>
                  </td>
                  <td>
                    <span class="badge">${esc(o.plano).toUpperCase()}</span>
                    <div style="font-weight:800; margin-top:3px;">${o.is_master ? 'Proprietário' : formatMoney(o.valor_mensal) + '/mês'}</div>
                  </td>
                  <td>
                    <div style="font-size:12.5px;"><b>${o.usuarios_count}</b> / ${o.limite_usuarios} usuários</div>
                    <div class="muted" style="font-size:11.5px;"><b>${o.clientes_count}</b> / ${o.limite_clientes} clientes</div>
                  </td>
                  <td>
                    <span class="badge ${o.status_assinatura === 'ativo' ? 'ativo' : o.status_assinatura === 'suspenso' || o.status_assinatura === 'inadimplente' ? 'cancelado' : 'pendente'}">
                      ${esc(o.status_assinatura)}
                    </span>
                    ${o.status_assinatura === 'trial' && o.trial_ate ? `<div class="muted" style="font-size:11px;">Até ${formatDate(o.trial_ate)}</div>` : ''}
                  </td>
                  <td style="white-space:nowrap;">
                    <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick='window.nexusOpenTenantModal(${JSON.stringify(o).replace(/'/g, "&apos;")})'>Módulos &amp; Marca</button>
                    ${!o.is_master ? `
                      <button type="button" class="btn" style="padding:5px 10px; font-size:12px;" onclick="window.nexusImpersonateTenant(${o.id}, '${esc(o.nome)}')">Acessar Portal</button>
                      ${o.status_assinatura === 'suspenso'
                        ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--ok);" onclick="window.nexusQuickToggleTenantStatus(${o.id}, 'ativo')">Reativar</button>`
                        : `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:#b45309;" onclick="window.nexusQuickToggleTenantStatus(${o.id}, 'suspenso')">Suspender</button>`}
                      <button type="button" class="btn secondary" style="padding:5px 9px; font-size:11.5px; color:var(--danger);" data-del="/saas/organizacoes/${o.id}" data-label="${esc(o.nome)}">Excluir</button>
                    ` : ''}
                  </td>
                </tr>
              `;
            }).join('') || '<tr><td colspan="6" class="muted" style="text-align:center; padding:32px;">Nenhum ambiente cadastrado.</td></tr>'}
          </tbody>
        </table>
      </div>
    ` : `
      <div class="grid">
        ${planos.map((pl) => {
          const recs = safeJsonArray(pl.recursos_json);
          return `
            <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; border:${pl.destaque ? '2px solid var(--primary)' : '1px solid var(--border)'};">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <span class="badge ${pl.ativo ? 'ativo' : 'inativo'}">${pl.ativo ? 'Ativo na Vitrine' : 'Oculto'}</span>
                  ${pl.destaque ? '<span class="badge em_andamento">Mais Vendido</span>' : ''}
                </div>
                <h3 style="margin:0 0 4px;">${esc(pl.nome)}</h3>
                <p class="muted" style="font-size:12.5px; margin:0 0 12px;">${esc(pl.subtitulo || '')}</p>
                <div style="font-size:26px; font-weight:900; color:var(--primary); margin-bottom:12px;">${formatMoney(pl.preco_mensal)}<span style="font-size:13px; font-weight:500; color:var(--text-light);">/mês</span></div>
                <ul style="padding-left:18px; margin:0 0 16px; font-size:13px; line-height:1.6;">
                  ${recs.map((r) => `<li>${esc(r)}</li>`).join('')}
                </ul>
              </div>
              <div style="display:flex; gap:8px;">
                <button type="button" class="btn secondary" style="flex:1; justify-content:center;" onclick='window.nexusOpenPlanoSaasModal(${JSON.stringify(pl).replace(/'/g, "&apos;")})'>Editar Plano</button>
                <button type="button" class="btn secondary" style="color:var(--danger);" data-del="/saas/planos/${pl.id}" data-label="${esc(pl.nome)}">Excluir</button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `}
  `;
}

// ==================== 9. LOJA & VITRINE DO SITE (SINCRONIZADO COM INDEX.HTML) ====================
export async function renderLojaView(ctx) {
  const { cache, user, matchSearch, invalidateCache, render, holeriteDialog, holeriteContainer, ICONS } = ctx;
  const produtos = (cache.produtos_loja || []).filter((p) =>
    matchSearch([p.nome, p.descricao, p.badge, p.spec_label, p.slug])
  );
  const pedidos = cache.pedidos_loja || [];
  const cfg = cache.empresa_config || {};
  const locText = cfg.cidade && cfg.estado
    ? `${cfg.cidade}, ${cfg.estado} - Brasil`
    : (cfg.endereco || 'Aracruz, ES - Brasil');

  window.nexusOpenProdutoLojaModal = (prodObj = null) => {
    const isEdit = Boolean(prodObj && prodObj.id);
    const tamanhosArr = safeJsonArray(prodObj?.tamanhos_json);
    const coresArr = safeJsonArray(prodObj?.cores_json);
    const tamanhosStr = tamanhosArr.length ? tamanhosArr.join(', ') : 'P, M, G, GG';
    const coresStr = coresArr.length ? coresArr.join(', ') : 'Preto, Azul Enterprise';
    const curImg = prodObj?.imagem_url || 'assets/brand/Estampa_Negativa_Branca.svg';

    holeriteContainer.innerHTML = `
      <form id="loja-produto-form">
        <div class="modal-header">
          <div class="modal-header-main">
            <div class="modal-header-icon">${ICONS.briefcase}</div>
            <div>
              <h2>${isEdit ? `Editar Produto — ${esc(prodObj.nome)}` : 'Novo Produto na Loja do Site'}</h2>
              <p class="modal-subtitle">As alterações publicadas aparecem imediatamente na seção "Produtos Exclusivos" de index.html</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="document.getElementById('holerite-dialog').close()">&times;</button>
        </div>

        <div class="modal-body">
          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">1</span> Informações do Produto</div>
            <div class="formgrid">
              <label>Nome do Produto *
                <input type="text" name="nome" required value="${esc(prodObj?.nome || '')}" placeholder="Ex.: Camiseta Polo Nexus Code">
              </label>
              <label>Preço de Venda (R$) *
                <input type="number" step="0.01" min="0" name="preco" required value="${prodObj ? Number(prodObj.preco).toFixed(2) : '49.90'}">
              </label>
              <label>Etiqueta / Badge Superior
                <input type="text" name="badge" value="${esc(prodObj?.badge || 'Novo')}" placeholder="Ex.: Novo, Destaque, Eco, Enterprise">
              </label>
              <label>Texto de Especificação (ao lado do preço)
                <input type="text" name="spec_label" value="${esc(prodObj?.spec_label || 'Tamanhos: P ao GG')}" placeholder="Ex.: Tamanhos: P ao GG, 500ml Inox">
              </label>
              <label>Ordem de Exibição no Site
                <input type="number" min="0" name="ordem" value="${prodObj?.ordem ?? (produtos.length + 1)}">
              </label>
              <label>Visibilidade na Vitrine
                <select name="ativo">
                  <option value="true" ${prodObj?.ativo !== false ? 'selected' : ''}>Ativo (Visível no site)</option>
                  <option value="false" ${prodObj?.ativo === false ? 'selected' : ''}>Oculto (Rascunho)</option>
                </select>
              </label>
            </div>
            <label class="field-full">Descrição Curta do Card *
              <textarea name="descricao" rows="2" required placeholder="Descreva o material, acabamento e diferenciais do produto...">${esc(prodObj?.descricao || '')}</textarea>
            </label>
          </div>

          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">2</span> Variações (Tamanhos &amp; Cores)</div>
            <div class="formgrid">
              <label>Tamanhos Disponíveis (separados por vírgula)
                <input type="text" name="tamanhos_csv" value="${esc(tamanhosStr)}" placeholder="Ex.: P, M, G, GG">
              </label>
              <label>Cores Disponíveis (separadas por vírgula)
                <input type="text" name="cores_csv" value="${esc(coresStr)}" placeholder="Ex.: Preto, Azul Enterprise">
              </label>
            </div>
          </div>

          <div class="modal-section-card">
            <div class="modal-section-title"><span class="modal-section-step">3</span> Imagem / Estampa Oficial do Card</div>
            <div class="formgrid">
              <label>Selecionar Estampa ou Mockup Oficial
                <select id="prod-preset-img">
                  <option value="">-- Personalizado / Upload abaixo --</option>
                  <option value="assets/brand/Estampa_Negativa_Branca.svg" ${curImg === 'assets/brand/Estampa_Negativa_Branca.svg' ? 'selected' : ''}>Estampa Negativa Branca (SVG Oficial)</option>
                  <option value="assets/brand/Estampa_Padrao.svg" ${curImg === 'assets/brand/Estampa_Padrao.svg' ? 'selected' : ''}>Estampa Padrão Azul/Ciano (SVG Oficial)</option>
                  <option value="img/blusa.png" ${curImg === 'img/blusa.png' ? 'selected' : ''}>Mockup Blusa Preta (img/blusa.png)</option>
                  <option value="img/moleton.png" ${curImg === 'img/moleton.png' ? 'selected' : ''}>Mockup Moletom (img/moleton.png)</option>
                  <option value="img/garrafa.png" ${curImg === 'img/garrafa.png' ? 'selected' : ''}>Mockup Garrafa Térmica (img/garrafa.png)</option>
                  <option value="img/mochila.png" ${curImg === 'img/mochila.png' ? 'selected' : ''}>Mockup Mochila Executiva (img/mochila.png)</option>
                </select>
              </label>
              <label>Estilo de Fundo da Vitrine
                <select name="fundo_escuro">
                  <option value="true" ${prodObj?.fundo_escuro !== false ? 'selected' : ''}>Fundo Azul Enterprise Escuro (#0A1D37)</option>
                  <option value="false" ${prodObj?.fundo_escuro === false ? 'selected' : ''}>Fundo Claro / Branco (#FFFFFF)</option>
                </select>
              </label>
              <label>Caminho / URL da Imagem
                <input type="text" name="imagem_url" id="prod-img-url" value="${esc(curImg)}" placeholder="assets/brand/Estampa_Padrao.svg">
              </label>
              <label>Ou Enviar Nova Foto (PNG/JPG/SVG, máx. 1,5 MB)
                <input type="file" id="prod-img-file" accept="image/*">
              </label>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn secondary" onclick="document.getElementById('holerite-dialog').close()">Cancelar</button>
          <button type="submit" class="btn" id="prod-save-btn">${isEdit ? 'Salvar Alterações' : 'Publicar Produto no Site'}</button>
        </div>
      </form>
    `;

    document.getElementById('prod-preset-img')?.addEventListener('change', (e) => {
      if (e.target.value) {
        document.getElementById('prod-img-url').value = e.target.value;
      }
    });

    document.getElementById('prod-img-file')?.addEventListener('change', async (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      if (f.size > 1.5 * 1024 * 1024) {
        showToast('A imagem deve ter no máximo 1,5 MB.', 'error');
        return;
      }
      const dataUrl = await readFileAsDataUrl(f);
      document.getElementById('prod-img-url').value = dataUrl;
      showToast('Imagem carregada! Clique em salvar para publicar.', 'info');
    });

    document.getElementById('loja-produto-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('prod-save-btn');
      const raw = Object.fromEntries(new FormData(e.target));
      const tamanhos = String(raw.tamanhos_csv || 'Único').split(',').map((s) => s.trim()).filter(Boolean);
      const cores = String(raw.cores_csv || 'Padrão').split(',').map((s) => s.trim()).filter(Boolean);

      btn.disabled = true;
      btn.textContent = 'Salvando...';
      try {
        const payload = {
          nome: raw.nome.trim(),
          descricao: raw.descricao.trim(),
          preco: Number(raw.preco || 0),
          badge: raw.badge ? raw.badge.trim() : null,
          spec_label: raw.spec_label ? raw.spec_label.trim() : null,
          imagem_url: raw.imagem_url ? raw.imagem_url.trim() : 'assets/brand/Estampa_Padrao.svg',
          fundo_escuro: raw.fundo_escuro === 'true',
          tamanhos_json: JSON.stringify(tamanhos.length ? tamanhos : ['Único']),
          cores_json: JSON.stringify(cores.length ? cores : ['Padrão']),
          ordem: Number(raw.ordem || 0),
          ativo: raw.ativo === 'true'
        };

        await apiRequest(isEdit ? `/loja/produtos/${prodObj.id}` : '/loja/produtos', {
          method: isEdit ? 'PATCH' : 'POST',
          body: JSON.stringify(payload)
        });
        holeriteDialog.close();
        invalidateCache();
        showToast(isEdit ? 'Produto atualizado e publicado no site!' : 'Novo produto publicado na loja do site!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar produto', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
      }
    };

    holeriteDialog.showModal();
  };

  window.nexusToggleProdutoAtivo = async (id, nextAtivo) => {
    try {
      await apiRequest(`/loja/produtos/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ativo: nextAtivo })
      });
      invalidateCache();
      showToast(nextAtivo ? 'Produto ativado na vitrine do site.' : 'Produto ocultado da vitrine.', 'info');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro', message: err.message, variant: 'error' });
    }
  };

  window.nexusUpdatePedidoStatus = async (id, status) => {
    try {
      await apiRequest(`/pedidos-loja/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status })
      });
      invalidateCache();
      showToast('Status do pedido atualizado!', 'success');
      render();
    } catch (err) {
      showNoticeModal({ title: 'Erro', message: err.message, variant: 'error' });
    }
  };

  return `
    <div class="toolbar">
      <div>
        <h1>Loja &amp; Vitrine do Site Principal</h1>
        <span class="muted">Gerencie os produtos exclusivos e canais de contato exibidos diretamente em <code>index.html</code></span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <a href="../index.html#loja" target="_blank" rel="noopener" class="btn secondary" style="text-decoration:none;">Abrir Site em Nova Aba ↗</a>
        <button type="button" class="btn" onclick="window.nexusOpenProdutoLojaModal(null)">${ICONS.plus}<span>Novo Produto</span></button>
      </div>
    </div>

    <!-- Resumo dos Canais de Atendimento Sincronizados -->
    <div class="card" style="margin-bottom:20px; border-left:4px solid #00B4D8;">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap;">
        <div>
          <span style="font-size:11px; font-weight:800; text-transform:uppercase; color:var(--primary); letter-spacing:0.05em;">Canais de Atendimento Ativos no Site Principal</span>
          <div style="display:flex; gap:24px; flex-wrap:wrap; margin-top:8px; font-size:13.5px;">
            <div><b>E-mail Corporativo:</b> ${esc(cfg.email_financeiro || 'contato@nexuscodebrasil.com.br')}</div>
            <div><b>Telefone / WhatsApp:</b> ${esc(cfg.telefone || '(27) 99999-9999')}</div>
            <div><b>Localização:</b> ${esc(locText)}</div>
          </div>
        </div>
        <button type="button" class="btn secondary" onclick="window.nexusGo('empresa')">Editar Canais de Atendimento</button>
      </div>
    </div>

    <!-- Catálogo de Produtos Exclusivos -->
    <div class="card table-wrap" style="margin-bottom:22px;">
      <div style="padding:16px 18px 8px; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0; font-size:16px;">Catálogo de Produtos Exclusivos (${produtos.length})</h3>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Ordem</th>
            <th>Produto</th>
            <th>Etiqueta</th>
            <th>Preço</th>
            <th>Variações</th>
            <th>Status no Site</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          ${produtos.map((p) => {
            const tams = safeJsonArray(p.tamanhos_json).join(', ') || '-';
            const cors = safeJsonArray(p.cores_json).join(', ') || '-';
            const imgSrc = p.imagem_url && !p.imagem_url.startsWith('data:') && !p.imagem_url.startsWith('http')
              ? `../${p.imagem_url}`
              : (p.imagem_url || '../assets/brand/Estampa_Padrao.svg');
            return `
              <tr>
                <td><b>#${p.ordem}</b></td>
                <td>
                  <div class="row-entity">
                    <div style="width:44px; height:44px; border-radius:10px; background:${p.fundo_escuro ? '#0A1D37' : '#f1f5f9'}; padding:6px; display:flex; align-items:center; justify-content:center; flex-shrink:0; border:1px solid var(--border);">
                      <img src="${esc(imgSrc)}" alt="${esc(p.nome)}" style="max-width:100%; max-height:100%; object-fit:contain;">
                    </div>
                    <div>
                      <b>${esc(p.nome)}</b>
                      <div class="muted" style="font-size:12px; max-width:340px;">${esc(p.descricao || '')}</div>
                    </div>
                  </div>
                </td>
                <td>${p.badge ? `<span class="badge">${esc(p.badge)}</span>` : '-'}</td>
                <td style="font-weight:800; color:var(--primary);">${formatMoney(p.preco)}</td>
                <td>
                  <div style="font-size:12px;"><b>Tam:</b> ${esc(tams)}</div>
                  <div class="muted" style="font-size:11.5px;"><b>Cores:</b> ${esc(cors)}</div>
                </td>
                <td>
                  <span class="badge ${p.ativo ? 'ativo' : 'inativo'}">${p.ativo ? 'Publicado' : 'Oculto'}</span>
                </td>
                <td style="white-space:nowrap;">
                  <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick='window.nexusOpenProdutoLojaModal(${JSON.stringify(p).replace(/'/g, "&apos;")})'>Editar</button>
                  <button type="button" class="btn secondary" style="padding:5px 10px; font-size:12px;" onclick="window.nexusToggleProdutoAtivo(${p.id}, ${!p.ativo})">${p.ativo ? 'Ocultar' : 'Publicar'}</button>
                  ${user?.perfil === 'admin' ? `<button type="button" class="btn secondary" style="padding:5px 9px; font-size:12px; color:var(--danger);" data-del="/loja/produtos/${p.id}" data-label="${esc(p.nome)}">Excluir</button>` : ''}
                </td>
              </tr>
            `;
          }).join('') || '<tr><td colspan="7" class="muted" style="text-align:center; padding:32px;">Nenhum produto cadastrado.</td></tr>'}
        </tbody>
      </table>
    </div>

    <!-- Pedidos Recebidos pela Loja do Site -->
    <div class="card table-wrap">
      <div style="padding:16px 18px 8px;">
        <h3 style="margin:0; font-size:16px;">Pedidos Recebidos pelo Site (${pedidos.length})</h3>
      </div>
      <table class="table">
        <thead>
          <tr><th>Código</th><th>Comprador</th><th>Itens</th><th>Total</th><th>Status</th><th>Data</th></tr>
        </thead>
        <tbody>
          ${pedidos.map((ped) => {
            const itens = safeJsonArray(ped.itens_json);
            const resumoItens = itens.map((it) => `${it.quantidade}x ${it.name || it.nome} (${it.size || '-'})`).join(', ');
            return `
              <tr>
                <td><b>${esc(ped.codigo)}</b></td>
                <td>
                  <b>${esc(ped.nome_comprador)}</b>
                  <div class="muted" style="font-size:11.5px;">${esc(ped.email_comprador)} ${ped.telefone_comprador ? '• ' + esc(ped.telefone_comprador) : ''}</div>
                </td>
                <td style="font-size:12.5px;">${esc(resumoItens || '-')}</td>
                <td style="font-weight:800;">${formatMoney(ped.valor_total)}</td>
                <td>
                  <select class="nc-input" style="height:32px; padding:2px 8px; font-size:12px; width:auto;" onchange="window.nexusUpdatePedidoStatus(${ped.id}, this.value)">
                    ${['aguardando_pagamento', 'pago', 'enviado', 'cancelado'].map((st) => `<option value="${st}" ${ped.status === st ? 'selected' : ''}>${st.replace('_', ' ')}</option>`).join('')}
                  </select>
                </td>
                <td>${formatDateTime(ped.criado_em)}</td>
              </tr>
            `;
          }).join('') || '<tr><td colspan="6" class="muted" style="text-align:center; padding:28px;">Nenhum pedido realizado pela loja virtual ainda.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
}
