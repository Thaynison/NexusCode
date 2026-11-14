import { apiRequest } from './config.js';
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
          ${msgs.map((m) => `
            <div class="ticket-msg ${m.perfil === 'cliente' ? 'client' : 'staff'}">
              <div style="display:flex; justify-content:space-between; gap:12px; font-size:11px; color:var(--text-light); margin-bottom:4px;">
                <b>${esc(m.autor)} (${esc(m.perfil)})</b>
                <span>${esc(m.criado_em || '')}</span>
              </div>
              <div style="font-size:13.5px; line-height:1.5; white-space:pre-wrap;">${esc(m.texto)}</div>
              ${m.anexo_data ? `<div style="margin-top:6px;"><a href="${m.anexo_data}" download="${esc(m.anexo_nome || 'anexo')}" class="btn secondary" style="padding:4px 8px; font-size:11px; text-decoration:none;">Baixar ${esc(m.anexo_nome || 'Anexo')}</a></div>` : ''}
            </div>
          `).join('') || '<p class="muted">Sem mensagens.</p>'}
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

    <div class="card table-wrap">
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

// ==================== 8. CONFIGURAÇÕES DA EMPRESA & PERMISSÕES ====================
export async function renderEmpresaView(ctx) {
  const { cache, user, invalidateCache, render } = ctx;
  const cfg = cache.empresa_config || await apiRequest('/empresa');
  const isAdmin = user?.perfil === 'admin';

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
    const form = document.getElementById('empresa-config-form');
    if (!form) return;
    form.onsubmit = async (e) => {
      e.preventDefault();
      if (!isAdmin) {
        showNoticeModal({ title: 'Acesso Restrito', message: 'Apenas administradores podem salvar configurações da empresa.', variant: 'warning' });
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
        showToast('Configurações da empresa e permissões atualizadas!', 'success');
        render();
      } catch (err) {
        showNoticeModal({ title: 'Erro ao salvar configurações', message: err.message, variant: 'error' });
      } finally {
        btn.disabled = false;
        btn.textContent = 'Salvar Configurações da Empresa';
      }
    };
  }, 30);

  return `
    <div class="toolbar">
      <div>
        <h1>Configurações da Empresa &amp; Permissões</h1>
        <span class="muted">Dados fiscais, chave PIX exibida no Portal do Cliente e matriz de permissões por perfil</span>
      </div>
    </div>

    <form id="empresa-config-form" class="profile-columns">
      <div class="card profile-col-card">
        <div>
          <h4 class="profile-section-title">1. Dados Institucionais &amp; Fiscais</h4>
          <p class="profile-section-sub">Informações exibidas em propostas comerciais, recibos e portal do cliente.</p>
          <div class="profile-grid">
            <label class="field-full">Razão Social *
              <input type="text" name="razao_social" value="${esc(cfg?.razao_social || 'Nexus Code Brasil Tecnologia Ltda')}" required class="nc-input">
            </label>
            <label class="field-full">Nome Fantasia *
              <input type="text" name="nome_fantasia" value="${esc(cfg?.nome_fantasia || 'Nexus Code Brasil')}" required class="nc-input">
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
          <p class="profile-section-sub">Estes dados aparecem automaticamente para o cliente na tela de pagamento de faturas.</p>
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
          <p class="profile-section-sub">Administradores possuem acesso irrestrito. Defina abaixo os módulos visíveis para o perfil <b>Colaborador</b>.</p>
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
  `;
}
