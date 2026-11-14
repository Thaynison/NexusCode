import { apiRequest, getToken } from './config.js';

if (!getToken()) {
  window.location.href = '../login.html';
}

const params = new URLSearchParams(window.location.search);
const projetoId = Number(params.get('projeto_id') || 0);

let state = {
  projeto: null,
  fullName: '',
  branch: 'main',
  branches: ['main'],
  tree: [],
  commits: [],
  openTabs: [],
  activePath: null
};

const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function termPrint(msg, color = '#d1d5db') {
  const out = $('#vsc-terminal-out');
  if (!out) return;
  const line = document.createElement('div');
  line.style.color = color;
  line.textContent = msg;
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

function detectLanguage(path) {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const map = {
    js: 'JavaScript', mjs: 'JavaScript', ts: 'TypeScript', py: 'Python',
    html: 'HTML', css: 'CSS', json: 'JSON', md: 'Markdown', sql: 'SQL', yml: 'YAML', yaml: 'YAML'
  };
  return map[ext] || 'Plain Text';
}

function highlightCode(code, path) {
  let html = esc(code);
  const ext = (path.split('.').pop() || '').toLowerCase();
  if (['js', 'mjs', 'ts', 'py'].includes(ext)) {
    html = html
      .replace(/(\/\/.*$|#.*$)/gm, '<span class="tok-com">$1</span>')
      .replace(/(&quot;.*?&quot;|&#39;.*?&#39;|`.*?`)/g, '<span class="tok-str">$1</span>')
      .replace(/\b(const|let|var|function|return|if|else|for|while|async|await|import|from|export|default|class|def|try|except|raise|True|False|None)\b/g, '<span class="tok-kw">$1</span>')
      .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="tok-num">$1</span>');
  } else if (ext === 'html') {
    html = html.replace(/(&lt;\/?[a-zA-Z0-9-]+)(.*?)(\/?&gt;)/g, '<span class="tok-tag">$1</span>$2<span class="tok-tag">$3</span>');
  } else if (ext === 'json') {
    html = html
      .replace(/(&quot;[^&]+?&quot;)(\s*:)/g, '<span class="tok-kw">$1</span>$2')
      .replace(/:\s*(&quot;.*?&quot;)/g, ': <span class="tok-str">$1</span>');
  }
  return html + '\n';
}

function updateDirtyBadges() {
  const dirtyTabs = state.openTabs.filter((t) => t.dirty);
  const count = dirtyTabs.length;
  const b1 = $('#vsc-dirty-badge');
  const b2 = $('#vsc-git-badge');
  const b3 = $('#vsc-changes-count');
  if (b1) { b1.textContent = count; b1.style.display = count ? 'inline' : 'none'; }
  if (b2) { b2.textContent = count; b2.style.display = count ? 'inline' : 'none'; }
  if (b3) b3.textContent = count;

  const list = $('#vsc-changes-list');
  if (list) {
    list.innerHTML = dirtyTabs.length
      ? dirtyTabs.map((t) => `<div class="vsc-tree-item" onclick="window.ideSelectTab('${esc(t.path)}')"><span style="color:#eab308;font-weight:800;">M</span> ${esc(t.path)}</div>`).join('')
      : '<div style="color:#6b7280;font-size:11.5px;">Nenhuma alteração pendente.</div>';
  }
}

function renderTabs() {
  const bar = $('#vsc-tabs-bar');
  bar.innerHTML = state.openTabs.map((t) => `
    <div class="vsc-tab ${t.path === state.activePath ? 'active' : ''}" onclick="window.ideSelectTab('${esc(t.path)}')">
      <span>${esc(t.name)}</span>
      ${t.dirty ? '<span style="color:#00B4D8;">&#9679;</span>' : ''}
      <button type="button" class="vsc-tab-close" onclick="event.stopPropagation(); window.ideCloseTab('${esc(t.path)}')">&times;</button>
    </div>
  `).join('');
  updateDirtyBadges();
}

function syncEditorView() {
  const tab = state.openTabs.find((t) => t.path === state.activePath);
  if (!tab) {
    $('#vsc-welcome').style.display = 'block';
    $('#vsc-editor-stage').style.display = 'none';
    $('#vsc-breadcrumbs').textContent = 'Selecione um arquivo no explorador';
    $('#vsc-lang-mode').textContent = 'Plain Text';
    return;
  }

  $('#vsc-welcome').style.display = 'none';
  $('#vsc-editor-stage').style.display = 'flex';
  $('#vsc-breadcrumbs').textContent = `${state.fullName} > ${state.branch} > ${tab.path.split('/').join(' > ')}`;
  $('#vsc-lang-mode').textContent = detectLanguage(tab.path);

  const ta = $('#vsc-textarea');
  const hl = $('#vsc-code-highlight');
  const gutter = $('#vsc-gutter');

  ta.value = tab.content;
  ta.readOnly = Boolean(tab.isBinary);
  hl.innerHTML = highlightCode(tab.content, tab.path);

  const linesCount = Math.max(1, tab.content.split('\n').length);
  gutter.innerHTML = Array.from({ length: linesCount }, (_, i) => i + 1).join('<br>');

  if ($('#vsc-preview-pane').style.display === 'flex') {
    $('#vsc-preview-frame').srcdoc = tab.content;
  }
}

window.ideSelectTab = (path) => {
  state.activePath = path;
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideCloseTab = (path) => {
  state.openTabs = state.openTabs.filter((t) => t.path !== path);
  if (state.activePath === path) {
    state.activePath = state.openTabs[state.openTabs.length - 1]?.path || null;
  }
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideOpenFile = async (path) => {
  const existing = state.openTabs.find((t) => t.path === path);
  if (existing) {
    window.ideSelectTab(path);
    return;
  }
  $('#vsc-output-status').textContent = `LENDO ${path}...`;
  try {
    const file = await apiRequest(`/projetos/${projetoId}/ide/file?path=${encodeURIComponent(path)}&branch=${encodeURIComponent(state.branch)}`);
    state.openTabs.push({
      path: file.path,
      name: file.name,
      content: file.content,
      originalContent: file.content,
      sha: file.sha,
      dirty: false,
      isBinary: file.is_binary
    });
    state.activePath = file.path;
    renderTabs();
    renderTree();
    syncEditorView();
    $('#vsc-output-status').textContent = 'SAÍDA: PRONTO';
  } catch (err) {
    termPrint(`[Erro] ${err.message}`, '#f87171');
  }
};

function renderTree() {
  const container = $('#vsc-file-tree');
  const blobs = state.tree.filter((n) => n.type === 'blob');
  if (!blobs.length) {
    container.innerHTML = '<div style="padding:12px; color:#858585;">Repositório vazio. Clique em "+ Arquivo" para criar o primeiro arquivo.</div>';
    return;
  }
  container.innerHTML = blobs.map((n) => {
    const depth = n.path.split('/').length - 1;
    const isActive = n.path === state.activePath;
    return `
      <div class="vsc-tree-item ${isActive ? 'active' : ''}" style="padding-left:${12 + depth * 12}px;" onclick="window.ideOpenFile('${esc(n.path)}')">
        <span style="color:#00B4D8;">&#128196;</span>
        <span>${esc(n.path)}</span>
      </div>
    `;
  }).join('');
}

function renderCommits() {
  const box = $('#vsc-commits-list');
  if (!box) return;
  box.innerHTML = state.commits.map((c) => `
    <div class="vsc-commit-card">
      <div style="font-weight:700; color:#e2e8f0;">${esc(c.message)}</div>
      <div style="color:#94a3b8; margin-top:2px;"><code>${esc(c.sha)}</code> • ${esc(c.author)}</div>
    </div>
  `).join('') || '<div style="color:#6b7280;">Sem commits recentes.</div>';
}

async function loadRepositoryTree(branch = null) {
  const qs = branch ? `?branch=${encodeURIComponent(branch)}` : '';
  const data = await apiRequest(`/projetos/${projetoId}/ide/tree${qs}`);
  state.projeto = data.projeto;
  state.fullName = data.full_name;
  state.branch = data.branch;
  state.branches = data.branches || [data.branch];
  state.tree = data.tree || [];
  state.commits = data.commits || [];

  document.title = `${data.projeto.titulo} — Nexus Code Studio`;
  $('#vsc-repo-name').textContent = data.full_name;
  $('#vsc-cmd-title').textContent = `${data.projeto.titulo} [${data.branch}] — Ctrl+P`;
  $('#vsc-branch-name').textContent = data.branch;
  $('#vsc-link-github').href = data.html_url;
  $('#vsc-term-prompt').textContent = `nexus@codespaces:~/${data.full_name.split('/').pop()}$`;

  renderTree();
  renderCommits();

  if (!state.openTabs.length) {
    const readme = state.tree.find((n) => n.type === 'blob' && n.path.toLowerCase() === 'readme.md') || state.tree.find((n) => n.type === 'blob');
    if (readme) await window.ideOpenFile(readme.path);
  }
}

async function commitDirtyFiles(customMsg = null) {
  const dirtyTabs = state.openTabs.filter((t) => t.dirty && !t.isBinary);
  if (!dirtyTabs.length) {
    termPrint('[Git] Nenhuma alteração pendente para commit.', '#94a3b8');
    return;
  }
  const msg = (customMsg || $('#vsc-commit-msg')?.value || '').trim() || `feat: atualiza ${dirtyTabs.map((d) => d.name).join(', ')}`;
  $('#vsc-sync-status').textContent = 'Sincronizando com GitHub...';

  for (const tab of dirtyTabs) {
    const res = await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'PUT',
      body: JSON.stringify({
        path: tab.path,
        content: tab.content,
        message: msg,
        branch: state.branch,
        sha: tab.sha
      })
    });
    tab.sha = res.sha;
    tab.originalContent = tab.content;
    tab.dirty = false;
    termPrint(`[Git Push] ${tab.path} -> commit ${res.commit_sha} (${state.branch})`, '#34d399');
  }

  if ($('#vsc-commit-msg')) $('#vsc-commit-msg').value = '';
  $('#vsc-sync-status').textContent = '✓ Sincronizado';
  renderTabs();
  await loadRepositoryTree(state.branch);
}

async function triggerDeploy(target = 'production') {
  termPrint(`[Vercel] Disparando deploy (${target}) da branch ${state.branch}...`, '#38bdf8');
  try {
    const res = await apiRequest(`/projetos/${projetoId}/deploy`, {
      method: 'POST',
      body: JSON.stringify({ target, branch: state.branch })
    });
    termPrint(`[Vercel] Deploy iniciado! Status: ${res.deploy.status} | URL: ${res.deploy.url}`, '#34d399');
    if (res.deploy.url) window.open(res.deploy.url, '_blank', 'noopener');
  } catch (err) {
    termPrint(`[Vercel Erro] ${err.message}`, '#f87171');
  }
}

const ta = $('#vsc-textarea');
const hl = $('#vsc-code-highlight');
const gutter = $('#vsc-gutter');

ta?.addEventListener('input', () => {
  const tab = state.openTabs.find((t) => t.path === state.activePath);
  if (!tab) return;
  tab.content = ta.value;
  tab.dirty = tab.content !== tab.originalContent;
  hl.innerHTML = highlightCode(tab.content, tab.path);
  const linesCount = Math.max(1, tab.content.split('\n').length);
  gutter.innerHTML = Array.from({ length: linesCount }, (_, i) => i + 1).join('<br>');
  if ($('#vsc-preview-pane').style.display === 'flex') {
    $('#vsc-preview-frame').srcdoc = tab.content;
  }
  renderTabs();
});

ta?.addEventListener('scroll', () => {
  hl.scrollTop = ta.scrollTop;
  hl.scrollLeft = ta.scrollLeft;
  gutter.scrollTop = ta.scrollTop;
});

ta?.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    ta.value = ta.value.substring(0, start) + '  ' + ta.value.substring(end);
    ta.selectionStart = ta.selectionEnd = start + 2;
    ta.dispatchEvent(new Event('input'));
  }
});

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    commitDirtyFiles();
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p') {
    e.preventDefault();
    $('#vsc-quickopen').style.display = 'flex';
    $('#vsc-quickopen-input').value = '';
    $('#vsc-quickopen-input').focus();
    renderQuickOpen('');
  } else if (e.key === 'Escape') {
    $('#vsc-quickopen').style.display = 'none';
  }
});

function renderQuickOpen(q) {
  const list = $('#vsc-quickopen-list');
  const matches = state.tree.filter((n) => n.type === 'blob' && n.path.toLowerCase().includes(q.toLowerCase()));
  list.innerHTML = matches.slice(0, 20).map((m) => `
    <div class="vsc-tree-item" style="padding:8px 14px;" onclick="document.getElementById('vsc-quickopen').style.display='none'; window.ideOpenFile('${esc(m.path)}')">
      &#128196; ${esc(m.path)}
    </div>
  `).join('');
}

$('#vsc-quickopen-input')?.addEventListener('input', (e) => renderQuickOpen(e.target.value));
$('#vsc-quickopen-trigger')?.addEventListener('click', () => {
  $('#vsc-quickopen').style.display = 'flex';
  $('#vsc-quickopen-input').focus();
  renderQuickOpen('');
});
$('#vsc-quickopen')?.addEventListener('click', (e) => { if (e.target.id === 'vsc-quickopen') $('#vsc-quickopen').style.display = 'none'; });

document.querySelectorAll('[data-side-tab]').forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll('[data-side-tab]').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.vsc-side-pane').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $(`#pane-${btn.dataset.sideTab}`)?.classList.add('active');
  };
});

$('#vsc-new-file-btn')?.addEventListener('click', async () => {
  const path = prompt('Informe o caminho do novo arquivo (ex.: src/service.js):');
  if (!path || !path.trim()) return;
  await apiRequest(`/projetos/${projetoId}/ide/file`, {
    method: 'POST',
    body: JSON.stringify({ path: path.trim(), content: `// ${path.trim()}\n`, branch: state.branch })
  });
  termPrint(`[Git] Arquivo criado: ${path.trim()}`, '#34d399');
  await loadRepositoryTree(state.branch);
  await window.ideOpenFile(path.trim());
});

$('#vsc-refresh-tree-btn')?.addEventListener('click', () => loadRepositoryTree(state.branch));
$('#vsc-btn-commit')?.addEventListener('click', () => commitDirtyFiles());
$('#vsc-git-commit-btn')?.addEventListener('click', () => commitDirtyFiles());
$('#vsc-btn-deploy')?.addEventListener('click', () => triggerDeploy('production'));
$('#vsc-side-deploy-prod')?.addEventListener('click', () => triggerDeploy('production'));
$('#vsc-side-deploy-prev')?.addEventListener('click', () => triggerDeploy('preview'));

$('#vsc-btn-preview')?.addEventListener('click', () => {
  const pane = $('#vsc-preview-pane');
  const open = pane.style.display !== 'flex';
  pane.style.display = open ? 'flex' : 'none';
  const tab = state.openTabs.find((t) => t.path === state.activePath);
  if (open && tab) $('#vsc-preview-frame').srcdoc = tab.content;
});
$('#vsc-close-preview')?.addEventListener('click', () => { $('#vsc-preview-pane').style.display = 'none'; });

$('#vsc-toggle-terminal-btn')?.addEventListener('click', () => {
  const p = $('#vsc-bottom-panel');
  p.style.display = p.style.display === 'none' ? 'flex' : 'none';
});
$('#vsc-hide-terminal')?.addEventListener('click', () => { $('#vsc-bottom-panel').style.display = 'none'; });

$('#vsc-branch-btn')?.addEventListener('click', async () => {
  const next = prompt(`Branches disponíveis: ${state.branches.join(', ')}\nDigite o nome da branch para trocar ou criar nova:`, state.branch);
  if (!next || !next.trim() || next.trim() === state.branch) return;
  const bName = next.trim();
  if (!state.branches.includes(bName)) {
    await apiRequest(`/projetos/${projetoId}/ide/branch`, {
      method: 'POST',
      body: JSON.stringify({ new_branch: bName, from_branch: state.branch })
    });
    termPrint(`[Git] Nova branch '${bName}' criada a partir de '${state.branch}'.`, '#34d399');
  }
  await loadRepositoryTree(bName);
});

$('#vsc-term-input')?.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const cmd = e.target.value.trim();
  e.target.value = '';
  if (!cmd) return;
  termPrint(`$ ${cmd}`, '#00B4D8');

  if (cmd === 'help') {
    termPrint('Comandos disponíveis: ls | git status | git branch | git checkout -b <branch> | git commit -m "msg" | nexus deploy | clear');
  } else if (cmd === 'clear') {
    $('#vsc-terminal-out').innerHTML = '';
  } else if (cmd === 'ls') {
    termPrint(state.tree.filter((n) => n.type === 'blob').map((n) => n.path).join('   ') || '(vazio)');
  } else if (cmd === 'git status') {
    const dirty = state.openTabs.filter((t) => t.dirty).map((t) => t.path);
    termPrint(`On branch ${state.branch}\n${dirty.length ? 'Modified: ' + dirty.join(', ') : 'nothing to commit, working tree clean'}`);
  } else if (cmd === 'git branch') {
    termPrint(state.branches.map((b) => (b === state.branch ? `* ${b}` : `  ${b}`)).join('\n'));
  } else if (cmd.startsWith('git checkout -b ')) {
    const nb = cmd.replace('git checkout -b ', '').trim();
    await apiRequest(`/projetos/${projetoId}/ide/branch`, { method: 'POST', body: JSON.stringify({ new_branch: nb, from_branch: state.branch }) });
    await loadRepositoryTree(nb);
    termPrint(`Switched to a new branch '${nb}'`, '#34d399');
  } else if (cmd.startsWith('git commit')) {
    const m = cmd.match(/-m\s+["'](.+?)["']/);
    await commitDirtyFiles(m ? m[1] : null);
  } else if (cmd === 'nexus deploy') {
    await triggerDeploy('production');
  } else {
    termPrint(`bash: ${cmd}: comando não reconhecido (digite 'help')`, '#f87171');
  }
});

if (!projetoId) {
  termPrint('Erro: projeto_id não informado na URL.', '#f87171');
} else {
  termPrint('Inicializando container Nexus Code Studio (Codespaces Cloud)...', '#00B4D8');
  loadRepositoryTree()
    .then(() => termPrint(`Repositório ${state.fullName} montado com sucesso na branch '${state.branch}'.`, '#34d399'))
    .catch((err) => termPrint(`[Erro ao conectar GitHub] ${err.message}`, '#f87171'));
}
