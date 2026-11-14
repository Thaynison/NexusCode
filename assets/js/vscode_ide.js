import { apiRequest, getToken } from './config.js';

if (!getToken()) {
  window.location.href = '../login.html';
}

const params = new URLSearchParams(window.location.search);
const projetoId = Number(params.get('projeto_id') || 0);

const state = {
  user: null,
  projeto: null,
  fullName: '',
  htmlUrl: '',
  branch: 'main',
  branches: ['main'],
  tree: [],
  commits: [],
  deployments: [],
  actionsRuns: [],
  openTabs: [],
  activePath: null,
  splitTabs: [],
  splitActivePath: null,
  splitOpen: false,
  selectedTreePath: null,
  selectedTreeType: null,
  fileClipboard: null, // { mode: 'copy' | 'cut', path: string }
  navHistory: [],
  navIndex: -1,
  expandedFolders: new Set(['src', 'app', 'public', 'assets', '.github', '.github/workflows']),
  diffMode: false,
  searchCaseSensitive: false,
  cwd: '',
  termHistory: [],
  termHistIdx: -1,
  prefs: {
    theme: 'nexus-codespaces-dark',
    fontSize: 14,
    tabSize: 2,
    minimap: true,
    wordWrap: 'off'
  }
};

let monacoApi = null;
let monacoEditor = null;
let monacoSplitEditor = null;
let monacoDiffEditor = null;
let monacoReady = false;
let suppressMonacoChange = false;

const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

/* ==================== LOGGING & TERMINAL ==================== */
function outputLog(msg) {
  const el = $('#ncs-output-log');
  if (!el) return;
  const line = document.createElement('div');
  const ts = new Date().toLocaleTimeString('pt-BR');
  line.textContent = `[${ts}] ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function termPrint(msg, color = '#e6edf3') {
  const out = $('#ncs-terminal-out');
  if (!out) return;
  const line = document.createElement('div');
  line.style.color = color;
  line.style.whiteSpace = 'pre-wrap';
  line.textContent = msg;
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

function updatePromptDisplay() {
  const repoShort = state.fullName.split('/').pop() || 'repo';
  const sub = state.cwd ? `/${state.cwd}` : '';
  const el = $('#ncs-term-prompt');
  if (el) el.textContent = `nexus@codespaces:~/${repoShort}${sub}$`;
}

/* ==================== LANGUAGE & FILE ICONS ==================== */
function getMonacoLanguage(path) {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const base = path.split('/').pop().toLowerCase();
  if (base === 'dockerfile') return 'dockerfile';
  const map = {
    js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    py: 'python',
    html: 'html', htm: 'html',
    css: 'css', scss: 'scss', less: 'less',
    json: 'json',
    md: 'markdown', markdown: 'markdown',
    sql: 'sql',
    yml: 'yaml', yaml: 'yaml',
    xml: 'xml', svg: 'xml',
    sh: 'shell', bash: 'shell',
    php: 'php', java: 'java', go: 'go', rs: 'rust', cpp: 'cpp', c: 'c', cs: 'csharp'
  };
  return map[ext] || 'plaintext';
}

function getLanguageLabel(path) {
  const lang = getMonacoLanguage(path);
  const labels = {
    javascript: 'JavaScript', typescript: 'TypeScript', python: 'Python',
    html: 'HTML', css: 'CSS', scss: 'SCSS', json: 'JSON', markdown: 'Markdown',
    sql: 'SQL', yaml: 'YAML', xml: 'XML', shell: 'Shell Script', dockerfile: 'Dockerfile',
    plaintext: 'Plain Text'
  };
  return labels[lang] || lang.toUpperCase();
}

function getFileBadge(path) {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const map = {
    js: ['JS', 'fi-js'], mjs: ['JS', 'fi-js'], jsx: ['JSX', 'fi-js'],
    ts: ['TS', 'fi-ts'], tsx: ['TSX', 'fi-ts'],
    py: ['PY', 'fi-py'],
    html: ['<>', 'fi-html'],
    css: ['#', 'fi-css'], scss: ['#', 'fi-css'],
    json: ['{}', 'fi-json'],
    md: ['M↓', 'fi-md'],
    yml: ['YML', 'fi-yml'], yaml: ['YML', 'fi-yml'],
    sql: ['DB', 'fi-sql'],
    sh: ['$_', 'fi-txt']
  };
  const [badge, cls] = map[ext] || ['≡', 'fi-txt'];
  return `<span class="ncs-ficon ${cls}">${badge}</span>`;
}

/* ==================== CUSTOM MODAL DIALOGS ==================== */
function openInputDialog({ title, desc = '', defaultValue = '', placeholder = '', confirmText = 'Confirmar', showInput = true, danger = false }) {
  return new Promise((resolve) => {
    const backdrop = $('#ncs-input-modal');
    const titleEl = $('#ncs-dlg-title');
    const descEl = $('#ncs-dlg-desc');
    const inp = $('#ncs-dlg-input');
    const okBtn = $('#ncs-dlg-ok');
    const cancelBtn = $('#ncs-dlg-cancel');

    titleEl.textContent = title;
    descEl.textContent = desc;
    descEl.style.display = desc ? 'block' : 'none';
    inp.style.display = showInput ? 'block' : 'none';
    inp.value = defaultValue;
    inp.placeholder = placeholder;
    okBtn.textContent = confirmText;
    okBtn.style.background = danger ? '#da3633' : '';

    backdrop.style.display = 'flex';
    if (showInput) {
      inp.focus();
      const dotIdx = defaultValue.lastIndexOf('.');
      const slashIdx = defaultValue.lastIndexOf('/');
      if (dotIdx > slashIdx + 1) {
        inp.setSelectionRange(slashIdx + 1, dotIdx);
      } else {
        inp.select();
      }
    } else {
      okBtn.focus();
    }

    const cleanup = (val) => {
      backdrop.style.display = 'none';
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      inp.onkeydown = null;
      backdrop.onclick = null;
      resolve(val);
    };

    okBtn.onclick = () => cleanup(showInput ? inp.value : true);
    cancelBtn.onclick = () => cleanup(null);
    backdrop.onclick = (e) => { if (e.target === backdrop) cleanup(null); };
    inp.onkeydown = (e) => {
      if (e.key === 'Enter') { e.preventDefault(); cleanup(inp.value); }
      if (e.key === 'Escape') { e.preventDefault(); cleanup(null); }
    };
  });
}

/* ==================== MONACO EDITOR ENGINE (VS CODE CORE API) ==================== */
function initMonacoEditor() {
  return new Promise((resolve) => {
    if (!window.require) {
      resolve(false);
      return;
    }
    const cdnBase = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min';
    window.MonacoEnvironment = {
      getWorkerUrl: function () {
        const proxyCode = `self.MonacoEnvironment = { baseUrl: '${cdnBase}/' }; importScripts('${cdnBase}/vs/base/worker/workerMain.js');`;
        return 'data:text/javascript;charset=utf-8,' + encodeURIComponent(proxyCode);
      }
    };

    const timer = setTimeout(() => resolve(false), 6000);
    try {
      window.require.config({ paths: { vs: `${cdnBase}/vs` } });
      window.require(['vs/editor/editor.main'], () => {
        clearTimeout(timer);
        monacoApi = window.monaco;

        // Configura Language Servers nativos do VS Code (TS/JS, HTML, CSS, JSON)
        if (monacoApi.languages?.typescript) {
          monacoApi.languages.typescript.javascriptDefaults.setDiagnosticsOptions({
            noSemanticValidation: false,
            noSyntaxValidation: false
          });
          monacoApi.languages.typescript.javascriptDefaults.setCompilerOptions({
            target: monacoApi.languages.typescript.ScriptTarget.ES2022,
            allowNonTsExtensions: true,
            allowJs: true,
            checkJs: false
          });
          monacoApi.languages.typescript.typescriptDefaults.setCompilerOptions({
            target: monacoApi.languages.typescript.ScriptTarget.ES2022,
            allowNonTsExtensions: true
          });
        }
        if (monacoApi.languages?.json?.jsonDefaults) {
          monacoApi.languages.json.jsonDefaults.setDiagnosticsOptions({
            validate: true,
            allowComments: true
          });
        }

        monacoApi.editor.defineTheme('nexus-codespaces-dark', {
          base: 'vs-dark',
          inherit: true,
          rules: [
            { token: 'comment', foreground: '8b949e', fontStyle: 'italic' },
            { token: 'keyword', foreground: 'ff7b72' },
            { token: 'string', foreground: 'a5d6ff' },
            { token: 'number', foreground: '79c0ff' },
            { token: 'type', foreground: 'ffa657' },
            { token: 'identifier', foreground: 'e6edf3' },
            { token: 'tag', foreground: '7ee787' },
            { token: 'attribute.name', foreground: '79c0ff' },
            { token: 'attribute.value', foreground: 'a5d6ff' }
          ],
          colors: {
            'editor.background': '#0d1117',
            'editor.foreground': '#e6edf3',
            'editor.lineHighlightBackground': '#161b22',
            'editor.selectionBackground': '#264f78',
            'editorCursor.foreground': '#58a6ff',
            'editorLineNumber.foreground': '#6e7681',
            'editorLineNumber.activeForeground': '#e6edf3',
            'editorIndentGuide.background': '#21262d',
            'editorIndentGuide.activeBackground': '#30363d',
            'editorWidget.background': '#1f242c',
            'editorWidget.border': '#454c56',
            'menu.background': '#252526',
            'menu.foreground': '#cccccc',
            'menu.selectionBackground': '#04395e',
            'menu.selectionForeground': '#ffffff',
            'menu.separatorBackground': '#3c3c3c'
          }
        });

        monacoEditor = monacoApi.editor.create($('#ncs-monaco-container'), {
          value: '',
          language: 'plaintext',
          theme: state.prefs.theme,
          fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
          fontSize: state.prefs.fontSize,
          tabSize: state.prefs.tabSize,
          insertSpaces: true,
          minimap: { enabled: state.prefs.minimap },
          wordWrap: state.prefs.wordWrap,
          automaticLayout: true,
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          bracketPairColorization: { enabled: true },
          autoClosingBrackets: 'always',
          autoClosingQuotes: 'always',
          autoClosingTags: true,
          formatOnPaste: true,
          renderLineHighlight: 'all',
          padding: { top: 10, bottom: 10 }
        });

        monacoEditor.onDidChangeModelContent(() => {
          if (suppressMonacoChange) return;
          const tab = state.openTabs.find((t) => t.path === state.activePath);
          if (!tab) return;
          tab.content = monacoEditor.getValue();
          tab.dirty = tab.content !== tab.originalContent;
          renderTabs();
          renderOpenEditorsAccordion();
          if ($('#ncs-preview-pane').style.display === 'flex') {
            refreshLivePreview();
          }
        });

        monacoEditor.onDidChangeCursorPosition((e) => {
          const pos = e.position;
          $('#ncs-cursor-pos').textContent = `Ln ${pos.lineNumber}, Col ${pos.column}`;
        });

        monacoApi.editor.onDidChangeMarkers(() => {
          updateProblemsPanel();
        });

        monacoEditor.addCommand(monacoApi.KeyMod.CtrlCmd | monacoApi.KeyCode.KeyS, () => {
          commitDirtyFiles();
        });
        monacoEditor.addCommand(monacoApi.KeyMod.CtrlCmd | monacoApi.KeyCode.Backslash, () => {
          if (state.activePath) window.ideOpenSplit(state.activePath);
        });

        monacoReady = true;
        outputLog('VS Code Core Engine (Monaco + Language Workers) inicializado.');
        resolve(true);
      }, () => {
        clearTimeout(timer);
        resolve(false);
      });
    } catch {
      clearTimeout(timer);
      resolve(false);
    }
  });
}

function updateProblemsPanel() {
  if (!monacoReady || !monacoApi) return;
  const markers = monacoApi.editor.getModelMarkers({});
  const errors = markers.filter((m) => m.severity === monacoApi.MarkerSeverity.Error);
  const warnings = markers.filter((m) => m.severity === monacoApi.MarkerSeverity.Warning);
  $('#ncs-problems-count').textContent = errors.length + warnings.length;
  $('#ncs-prob-stat-num').textContent = errors.length;
  if ($('#ncs-warn-stat-num')) $('#ncs-warn-stat-num').textContent = warnings.length;

  const list = $('#ncs-problems-list');
  if (!list) return;
  const all = [...errors, ...warnings];
  if (!all.length) {
    list.innerHTML = '<div class="ncs-muted-xs" style="padding:12px;">Nenhum problema detectado no workspace.</div>';
    return;
  }
  list.innerHTML = all.map((m) => {
    const file = m.resource?.path?.replace(/^\//, '') || '';
    const isErr = m.severity === monacoApi.MarkerSeverity.Error;
    return `
      <div class="ncs-tree-row" style="padding-left:14px;" onclick="window.ideOpenFile('${esc(file)}', ${m.startLineNumber})">
        <span style="color:${isErr ? 'var(--gh-red)' : 'var(--gh-yellow)'};">${isErr ? '&#8855;' : '&#9888;'}</span>
        <span>${esc(m.message)}</span>
        <span class="ncs-muted-xs" style="margin-left:auto;">${esc(file)} [${m.startLineNumber}:${m.startColumn}]</span>
      </div>
    `;
  }).join('');
}

/* ==================== FALLBACK EDITOR HIGHLIGHT ==================== */
function fallbackHighlight(code, path) {
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

/* ==================== TABS, SPLIT EDITOR, BREADCRUMBS & DIFF VIEWER ==================== */
function updateDirtyBadges() {
  const dirtyTabs = state.openTabs.filter((t) => t.dirty);
  const count = dirtyTabs.length;
  const b1 = $('#ncs-dirty-badge');
  const b2 = $('#ncs-git-badge');
  const b3 = $('#ncs-changes-count');
  if (b1) { b1.textContent = count; b1.style.display = count ? 'inline-block' : 'none'; }
  if (b2) { b2.textContent = count; b2.style.display = count ? 'flex' : 'none'; }
  if (b3) b3.textContent = count;

  const syncEl = $('#ncs-sync-status');
  if (syncEl) {
    syncEl.innerHTML = count
      ? `<span style="color:#d29922; font-weight:700;">&#8593; ${count} alteração(ões) pendente(s)</span>`
      : '&#10003; Sincronizado';
  }

  const list = $('#ncs-changes-list');
  if (list) {
    list.innerHTML = dirtyTabs.length
      ? dirtyTabs.map((t) => `
          <div class="ncs-tree-row" style="padding-left:6px;" onclick="window.ideOpenDiff('${esc(t.path)}')">
            <span style="color:#d29922; font-weight:800; font-family:monospace;">M</span>
            ${getFileBadge(t.path)}
            <span class="ncs-tree-name" title="${esc(t.path)}">${esc(t.path)}</span>
            <div class="ncs-tree-row-actions" style="display:flex;">
              <button type="button" title="Comparar Diff" onclick="event.stopPropagation(); window.ideOpenDiff('${esc(t.path)}')">&#8644;</button>
              <button type="button" title="Descartar Alterações" onclick="event.stopPropagation(); window.ideDiscardChanges('${esc(t.path)}')">&#8634;</button>
            </div>
          </div>
        `).join('')
      : '<div class="ncs-muted-xs" style="padding:4px 2px;">Nenhuma alteração pendente.</div>';
  }
}

function renderOpenEditorsAccordion() {
  const countEl = $('#ncs-open-count');
  const bodyEl = $('#acc-open-editors-body');
  if (countEl) countEl.textContent = state.openTabs.length;
  if (!bodyEl) return;

  bodyEl.innerHTML = state.openTabs.map((t) => `
    <div class="ncs-tree-row ${t.path === state.activePath ? 'active' : ''}"
         data-ctx-type="file" data-ctx-path="${esc(t.path)}"
         style="padding-left:14px;" onclick="window.ideSelectTab('${esc(t.path)}')">
      ${getFileBadge(t.path)}
      <span class="ncs-tree-name">${esc(t.name)}</span>
      ${t.dirty ? '<span style="color:var(--gh-accent); font-size:11px;">&#9679;</span>' : ''}
      <div class="ncs-tree-row-actions" style="display:flex;">
        <button type="button" title="Fechar" onclick="event.stopPropagation(); window.ideCloseTab('${esc(t.path)}')">&times;</button>
      </div>
    </div>
  `).join('') || '<div class="ncs-muted-xs" style="padding:6px 14px;">Nenhum arquivo aberto</div>';
}

function renderTabs() {
  const bar = $('#ncs-tabs-bar');
  bar.innerHTML = state.openTabs.map((t) => `
    <div class="ncs-tab ${t.path === state.activePath ? 'active' : ''}"
         data-ctx-type="tab" data-ctx-path="${esc(t.path)}"
         onclick="window.ideSelectTab('${esc(t.path)}')"
         onauxclick="if(event.button===1) window.ideCloseTab('${esc(t.path)}')">
      ${getFileBadge(t.path)}
      <span>${esc(t.name)}${state.diffMode && t.path === state.activePath ? ' (Diff)' : ''}</span>
      ${t.dirty ? '<span style="color:#58a6ff; font-size:12px;">&#9679;</span>' : ''}
      <button type="button" class="ncs-tab-close" title="Fechar (Ctrl+W)" onclick="event.stopPropagation(); window.ideCloseTab('${esc(t.path)}')">&times;</button>
    </div>
  `).join('');

  const actions = $('#ncs-tabs-actions');
  if (actions) actions.style.display = state.openTabs.length ? 'flex' : 'none';
  updateDirtyBadges();
  renderOpenEditorsAccordion();
  renderSplitTabs();
}

function renderSplitTabs() {
  const grp = $('#ncs-split-group');
  if (!grp) return;
  if (!state.splitOpen || !state.splitTabs.length) {
    grp.style.display = 'none';
    if (monacoEditor) monacoEditor.layout();
    return;
  }
  grp.style.display = 'flex';
  const bar = $('#ncs-split-tabs-bar');
  bar.innerHTML = state.splitTabs.map((p) => {
    const t = state.openTabs.find((x) => x.path === p);
    const name = p.split('/').pop();
    return `
      <div class="ncs-tab ${p === state.splitActivePath ? 'active' : ''}" onclick="window.ideOpenSplit('${esc(p)}')">
        ${getFileBadge(p)}
        <span>${esc(name)}</span>
        ${t?.dirty ? '<span style="color:#58a6ff; font-size:12px;">&#9679;</span>' : ''}
        <button type="button" class="ncs-tab-close" onclick="event.stopPropagation(); window.ideCloseSplitTab('${esc(p)}')">&times;</button>
      </div>
    `;
  }).join('');

  const cur = state.openTabs.find((x) => x.path === state.splitActivePath);
  if (cur && monacoReady && monacoApi) {
    const repoShort = state.fullName.split('/').pop() || 'repo';
    $('#ncs-split-breadcrumbs').innerHTML = [repoShort, ...cur.path.split('/')].map((c, idx, arr) =>
      `<span>${esc(c)}</span>${idx < arr.length - 1 ? '<span style="color:var(--gh-fg-subtle);">&#8250;</span>' : ''}`
    ).join('');

    if (!monacoSplitEditor) {
      monacoSplitEditor = monacoApi.editor.create($('#ncs-monaco-split-container'), {
        value: '',
        language: 'plaintext',
        theme: state.prefs.theme,
        fontFamily: "'JetBrains Mono', Consolas, monospace",
        fontSize: state.prefs.fontSize,
        tabSize: state.prefs.tabSize,
        minimap: { enabled: false },
        wordWrap: state.prefs.wordWrap,
        automaticLayout: true,
        scrollBeyondLastLine: false,
        padding: { top: 10, bottom: 10 }
      });
    }
    const uri = monacoApi.Uri.parse(`file:///${cur.path}`);
    let model = monacoApi.editor.getModel(uri);
    if (!model) {
      model = monacoApi.editor.createModel(cur.content, getMonacoLanguage(cur.path), uri);
    }
    monacoSplitEditor.setModel(model);
    monacoSplitEditor.layout();
  }
  if (monacoEditor) monacoEditor.layout();
}

window.ideOpenSplit = async (path) => {
  await window.ideOpenFile(path, null, false);
  if (!state.splitTabs.includes(path)) state.splitTabs.push(path);
  state.splitActivePath = path;
  state.splitOpen = true;
  renderTabs();
};

window.ideCloseSplitTab = (path) => {
  state.splitTabs = state.splitTabs.filter((p) => p !== path);
  if (state.splitActivePath === path) {
    state.splitActivePath = state.splitTabs[state.splitTabs.length - 1] || null;
  }
  if (!state.splitTabs.length) state.splitOpen = false;
  renderTabs();
};

function syncEditorView(targetLine = null) {
  const tab = state.openTabs.find((t) => t.path === state.activePath);
  const welcome = $('#ncs-welcome');
  const monacoHost = $('#ncs-monaco-container');
  const diffHost = $('#ncs-diff-container');
  const fallbackHost = $('#ncs-fallback-stage');

  if (!tab) {
    welcome.style.display = 'block';
    monacoHost.style.display = 'none';
    diffHost.style.display = 'none';
    fallbackHost.style.display = 'none';
    $('#ncs-breadcrumbs').innerHTML = '<span>Nexus CodeSpaces</span>';
    $('#ncs-lang-mode').textContent = 'Plain Text';
    return;
  }

  welcome.style.display = 'none';
  const repoShort = state.fullName.split('/').pop() || 'repo';
  const crumbs = [repoShort, state.branch, ...tab.path.split('/')];
  $('#ncs-breadcrumbs').innerHTML = crumbs.map((c, idx) =>
    `<span class="ncs-crumb-item">${esc(c)}</span>${idx < crumbs.length - 1 ? '<span style="color:var(--gh-fg-subtle);">&#8250;</span>' : ''}`
  ).join('');
  $('#ncs-lang-mode').textContent = getLanguageLabel(tab.path);

  if (state.diffMode && monacoReady && monacoApi) {
    monacoHost.style.display = 'none';
    fallbackHost.style.display = 'none';
    diffHost.style.display = 'block';
    if (!monacoDiffEditor) {
      monacoDiffEditor = monacoApi.editor.createDiffEditor(diffHost, {
        theme: state.prefs.theme,
        automaticLayout: true,
        readOnly: false,
        renderSideBySide: true,
        fontFamily: "'JetBrains Mono', Consolas, monospace",
        fontSize: state.prefs.fontSize
      });
    }
    const lang = getMonacoLanguage(tab.path);
    const origModel = monacoApi.editor.createModel(tab.originalContent, lang);
    const modModel = monacoApi.editor.createModel(tab.content, lang);
    monacoDiffEditor.setModel({ original: origModel, modified: modModel });
    monacoDiffEditor.getModifiedEditor().onDidChangeModelContent(() => {
      tab.content = monacoDiffEditor.getModifiedEditor().getValue();
      tab.dirty = tab.content !== tab.originalContent;
      renderTabs();
    });
    return;
  }

  diffHost.style.display = 'none';

  if (monacoReady && monacoApi && monacoEditor) {
    fallbackHost.style.display = 'none';
    monacoHost.style.display = 'block';
    const uri = monacoApi.Uri.parse(`file:///${tab.path}`);
    let model = monacoApi.editor.getModel(uri);
    const lang = getMonacoLanguage(tab.path);
    if (!model) {
      model = monacoApi.editor.createModel(tab.content, lang, uri);
    } else {
      monacoApi.editor.setModelLanguage(model, lang);
      if (model.getValue() !== tab.content) {
        suppressMonacoChange = true;
        model.setValue(tab.content);
        suppressMonacoChange = false;
      }
    }
    monacoEditor.setModel(model);
    monacoEditor.updateOptions({ readOnly: Boolean(tab.isBinary) });
    monacoEditor.layout();
    if (targetLine && targetLine > 0) {
      monacoEditor.revealLineInCenter(targetLine);
      monacoEditor.setPosition({ lineNumber: targetLine, column: 1 });
    }
    monacoEditor.focus();
  } else {
    monacoHost.style.display = 'none';
    fallbackHost.style.display = 'flex';
    const ta = $('#ncs-textarea');
    const hl = $('#ncs-code-highlight');
    const gutter = $('#ncs-gutter');
    ta.value = tab.content;
    ta.readOnly = Boolean(tab.isBinary);
    hl.innerHTML = fallbackHighlight(tab.content, tab.path);
    const linesCount = Math.max(1, tab.content.split('\n').length);
    gutter.innerHTML = Array.from({ length: linesCount }, (_, i) => i + 1).join('<br>');
  }

  if ($('#ncs-preview-pane').style.display === 'flex') {
    refreshLivePreview();
  }
}

function pushNavHistory(path) {
  if (state.navHistory[state.navIndex] === path) return;
  state.navHistory = state.navHistory.slice(0, state.navIndex + 1);
  state.navHistory.push(path);
  state.navIndex = state.navHistory.length - 1;
  updateNavButtons();
}

function updateNavButtons() {
  const bBack = $('#ncs-nav-back');
  const bFwd = $('#ncs-nav-fwd');
  if (bBack) bBack.disabled = state.navIndex <= 0;
  if (bFwd) bFwd.disabled = state.navIndex >= state.navHistory.length - 1;
}

window.ideSelectTab = (path, targetLine = null, recordHist = true) => {
  state.activePath = path;
  state.selectedTreePath = path;
  state.selectedTreeType = 'file';
  if (recordHist) pushNavHistory(path);
  renderTabs();
  renderTree();
  syncEditorView(targetLine);
};

window.ideCloseTab = (path) => {
  state.openTabs = state.openTabs.filter((t) => t.path !== path);
  if (state.activePath === path) {
    state.diffMode = false;
    state.activePath = state.openTabs[state.openTabs.length - 1]?.path || null;
  }
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideCloseOtherTabs = (keepPath) => {
  state.openTabs = state.openTabs.filter((t) => t.path === keepPath);
  state.activePath = keepPath;
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideCloseTabsToRight = (pivotPath) => {
  const idx = state.openTabs.findIndex((t) => t.path === pivotPath);
  if (idx >= 0) {
    state.openTabs = state.openTabs.slice(0, idx + 1);
    if (!state.openTabs.some((t) => t.path === state.activePath)) {
      state.activePath = pivotPath;
    }
    renderTabs();
    renderTree();
    syncEditorView();
  }
};

window.ideCloseSavedTabs = () => {
  state.openTabs = state.openTabs.filter((t) => t.dirty);
  if (!state.openTabs.some((t) => t.path === state.activePath)) {
    state.activePath = state.openTabs[state.openTabs.length - 1]?.path || null;
  }
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideCloseAllTabs = () => {
  state.openTabs = [];
  state.activePath = null;
  state.diffMode = false;
  renderTabs();
  renderTree();
  syncEditorView();
};

window.ideOpenDiff = async (path) => {
  state.diffMode = true;
  await window.ideOpenFile(path);
};

window.ideDiscardChanges = async (path) => {
  const tab = state.openTabs.find((t) => t.path === path);
  if (!tab) return;
  const ok = await openInputDialog({
    title: 'Descartar Alterações',
    desc: `Deseja reverter todas as alterações não enviadas em "${path}"?`,
    confirmText: 'Descartar',
    showInput: false,
    danger: true
  });
  if (!ok) return;
  tab.content = tab.originalContent;
  tab.dirty = false;
  state.diffMode = false;
  renderTabs();
  syncEditorView();
  outputLog(`Alterações descartadas em ${path}.`);
};

window.ideOpenFile = async (path, targetLine = null, focusPrimary = true) => {
  const existing = state.openTabs.find((t) => t.path === path);
  if (existing) {
    if (focusPrimary) window.ideSelectTab(path, targetLine);
    return;
  }
  outputLog(`Abrindo ${path}...`);
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
    const parts = file.path.split('/');
    for (let i = 1; i < parts.length; i++) {
      state.expandedFolders.add(parts.slice(0, i).join('/'));
    }
    if (focusPrimary) window.ideSelectTab(file.path, targetLine);
    else renderTabs();
  } catch (err) {
    termPrint(`[Erro ao abrir arquivo] ${err.message}`, '#f85149');
  }
};

/* ==================== HIERARCHICAL COLLAPSIBLE FOLDER TREE ==================== */
function buildTreeStructure(blobs) {
  const root = { folders: {}, files: [] };
  for (const item of blobs) {
    const parts = item.path.split('/');
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const seg = parts[i];
      const fullFolder = parts.slice(0, i + 1).join('/');
      if (!node.folders[seg]) {
        node.folders[seg] = { name: seg, path: fullFolder, folders: {}, files: [] };
      }
      node = node.folders[seg];
    }
    if (!item.path.endsWith('/.gitkeep')) {
      node.files.push({
        name: parts[parts.length - 1],
        path: item.path,
        sha: item.sha,
        size: item.size
      });
    }
  }
  return root;
}

function renderTreeNode(node, depth = 0) {
  let html = '';
  const folderNames = Object.keys(node.folders).sort((a, b) => a.localeCompare(b));
  for (const fname of folderNames) {
    const folder = node.folders[fname];
    const isOpen = state.expandedFolders.has(folder.path);
    const isFocused = state.selectedTreePath === folder.path;
    const pad = 10 + depth * 13;
    html += `
      <div class="ncs-tree-row ${isFocused ? 'focused' : ''}"
           data-ctx-type="folder" data-ctx-path="${esc(folder.path)}"
           style="padding-left:${pad}px;"
           onclick="window.ideToggleFolder('${esc(folder.path)}')">
        <span class="ncs-chevron">${isOpen ? '&#9662;' : '&#9656;'}</span>
        <span style="color:#8b949e;">${isOpen ? '&#128194;' : '&#128193;'}</span>
        <span class="ncs-tree-name" style="font-weight:600;">${esc(folder.name)}</span>
        <div class="ncs-tree-row-actions">
          <button type="button" title="Novo Arquivo em ${esc(folder.path)}" onclick="event.stopPropagation(); window.ideCreateNewFile('${esc(folder.path)}/')">+</button>
        </div>
      </div>
    `;
    if (isOpen) {
      html += renderTreeNode(folder, depth + 1);
    }
  }

  const filesSorted = [...node.files].sort((a, b) => a.name.localeCompare(b.name));
  for (const file of filesSorted) {
    const isActive = file.path === state.activePath;
    const isFocused = file.path === state.selectedTreePath;
    const isCut = state.fileClipboard?.mode === 'cut' && state.fileClipboard?.path === file.path;
    const pad = 22 + depth * 13;
    html += `
      <div class="ncs-tree-row ${isActive ? 'active' : ''} ${isFocused ? 'focused' : ''} ${isCut ? 'cut' : ''}"
           data-ctx-type="file" data-ctx-path="${esc(file.path)}" data-ctx-sha="${esc(file.sha)}"
           style="padding-left:${pad}px;"
           onclick="window.ideOpenFile('${esc(file.path)}')">
        ${getFileBadge(file.path)}
        <span class="ncs-tree-name" title="${esc(file.path)}">${esc(file.name)}</span>
        <div class="ncs-tree-row-actions">
          <button type="button" title="Renomear (F2)" onclick="event.stopPropagation(); window.ideRenameFile('${esc(file.path)}', '${esc(file.sha)}')">&#9998;</button>
          <button type="button" title="Excluir (Del)" style="color:#f85149;" onclick="event.stopPropagation(); window.ideDeleteFile('${esc(file.path)}', '${esc(file.sha)}')">&#128465;</button>
        </div>
      </div>
    `;
  }
  return html;
}

window.ideToggleFolder = (folderPath) => {
  state.selectedTreePath = folderPath;
  state.selectedTreeType = 'folder';
  if (state.expandedFolders.has(folderPath)) {
    state.expandedFolders.delete(folderPath);
  } else {
    state.expandedFolders.add(folderPath);
  }
  renderTree();
};

function renderTree() {
  const container = $('#ncs-file-tree');
  const blobs = state.tree.filter((n) => n.type === 'blob');
  if (!blobs.length) {
    container.innerHTML = '<div class="ncs-muted-xs" style="padding:14px;">Repositório vazio. Clique com o botão direito ou em "+ Novo Arquivo" acima.</div>';
    return;
  }
  const treeStruct = buildTreeStructure(blobs);
  container.innerHTML = renderTreeNode(treeStruct, 0);
}

/* ==================== FILE CRUD, CLIPBOARD & VS CODE CONTEXT MENU ==================== */
window.ideCreateNewFile = async (prefix = '') => {
  const path = await openInputDialog({
    title: 'Novo Arquivo no Repositório',
    desc: 'Informe o caminho do arquivo (pastas intermediárias são criadas automaticamente):',
    defaultValue: prefix,
    placeholder: 'Ex.: src/controllers/authController.js',
    confirmText: 'Criar Arquivo'
  });
  if (!path || !path.trim()) return;
  const clean = path.trim().replace(/^\/+/, '');
  try {
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({
        path: clean,
        content: `// ${clean}\n`,
        message: `feat: cria ${clean} via Nexus CodeSpaces`,
        branch: state.branch
      })
    });
    termPrint(`[Nexus CodeSpaces] Arquivo criado: ${clean}`, '#3fb950');
    outputLog(`Arquivo criado no GitHub: ${clean}`);
    await loadRepositoryTree(state.branch);
    await window.ideOpenFile(clean);
  } catch (err) {
    termPrint(`[Erro ao criar arquivo] ${err.message}`, '#f85149');
  }
};

window.ideCreateNewFolder = async (prefix = '') => {
  const folder = await openInputDialog({
    title: 'Nova Pasta no Repositório',
    desc: 'Informe o caminho da nova pasta (será inicializada com .gitkeep):',
    defaultValue: prefix,
    placeholder: 'Ex.: src/services',
    confirmText: 'Criar Pasta'
  });
  if (!folder || !folder.trim()) return;
  const cleanFolder = folder.trim().replace(/^\/+|\/+$/g, '');
  const gitkeepPath = `${cleanFolder}/.gitkeep`;
  try {
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({
        path: gitkeepPath,
        content: '',
        message: `chore: cria diretório ${cleanFolder}`,
        branch: state.branch
      })
    });
    state.expandedFolders.add(cleanFolder);
    termPrint(`[Nexus CodeSpaces] Pasta criada: ${cleanFolder}/`, '#3fb950');
    await loadRepositoryTree(state.branch);
  } catch (err) {
    termPrint(`[Erro ao criar pasta] ${err.message}`, '#f85149');
  }
};

window.ideRenameFile = async (oldPath, sha = null) => {
  const node = state.tree.find((n) => n.path === oldPath);
  const effectiveSha = sha || node?.sha;
  const newPath = await openInputDialog({
    title: 'Renomear ou Mover Arquivo (F2)',
    desc: `Caminho atual: ${oldPath}`,
    defaultValue: oldPath,
    confirmText: 'Renomear'
  });
  if (!newPath || !newPath.trim() || newPath.trim() === oldPath) return;
  const cleanNew = newPath.trim().replace(/^\/+/, '');
  try {
    let tab = state.openTabs.find((t) => t.path === oldPath);
    let contentToMove = tab ? tab.content : null;
    let currentSha = tab ? tab.sha : effectiveSha;
    if (contentToMove === null) {
      const f = await apiRequest(`/projetos/${projetoId}/ide/file?path=${encodeURIComponent(oldPath)}&branch=${encodeURIComponent(state.branch)}`);
      contentToMove = f.content;
      currentSha = f.sha;
    }
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({
        path: cleanNew,
        content: contentToMove,
        message: `refactor: renomeia ${oldPath} para ${cleanNew}`,
        branch: state.branch
      })
    });
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'DELETE',
      body: JSON.stringify({
        path: oldPath,
        sha: currentSha,
        message: `chore: remove antigo ${oldPath}`,
        branch: state.branch
      })
    });
    window.ideCloseTab(oldPath);
    termPrint(`[Git] Renomeado: ${oldPath} -> ${cleanNew}`, '#3fb950');
    await loadRepositoryTree(state.branch);
    await window.ideOpenFile(cleanNew);
  } catch (err) {
    termPrint(`[Erro ao renomear] ${err.message}`, '#f85149');
  }
};

window.ideDeleteFile = async (path, sha = null) => {
  const node = state.tree.find((n) => n.path === path);
  const effectiveSha = sha || node?.sha;
  if (!effectiveSha) return;
  const ok = await openInputDialog({
    title: 'Excluir Arquivo do GitHub',
    desc: `Tem certeza que deseja excluir permanentemente "${path}" da branch ${state.branch}?`,
    confirmText: 'Excluir Arquivo',
    showInput: false,
    danger: true
  });
  if (!ok) return;
  try {
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'DELETE',
      body: JSON.stringify({
        path,
        sha: effectiveSha,
        message: `chore: remove ${path} via Nexus CodeSpaces`,
        branch: state.branch
      })
    });
    window.ideCloseTab(path);
    termPrint(`[Git] Arquivo removido: ${path}`, '#f85149');
    await loadRepositoryTree(state.branch);
  } catch (err) {
    termPrint(`[Erro ao excluir] ${err.message}`, '#f85149');
  }
};

async function pasteClipboardFile(targetDir = '') {
  if (!state.fileClipboard?.path) return;
  const srcPath = state.fileClipboard.path;
  const mode = state.fileClipboard.mode;
  const baseName = srcPath.split('/').pop();
  const cleanDir = targetDir.replace(/^\/+|\/+$/g, '');
  let destPath = cleanDir ? `${cleanDir}/${baseName}` : baseName;

  if (destPath === srcPath && mode === 'copy') {
    const dot = baseName.lastIndexOf('.');
    const copyName = dot > 0 ? `${baseName.slice(0, dot)}-copy${baseName.slice(dot)}` : `${baseName}-copy`;
    destPath = cleanDir ? `${cleanDir}/${copyName}` : copyName;
  }
  if (destPath === srcPath && mode === 'cut') return;

  try {
    const f = await apiRequest(`/projetos/${projetoId}/ide/file?path=${encodeURIComponent(srcPath)}&branch=${encodeURIComponent(state.branch)}`);
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({
        path: destPath,
        content: f.content,
        message: `${mode === 'cut' ? 'refactor: move' : 'feat: duplica'} ${srcPath} para ${destPath}`,
        branch: state.branch
      })
    });
    if (mode === 'cut') {
      await apiRequest(`/projetos/${projetoId}/ide/file`, {
        method: 'DELETE',
        body: JSON.stringify({
          path: srcPath,
          sha: f.sha,
          message: `chore: remove origem ${srcPath}`,
          branch: state.branch
        })
      });
      window.ideCloseTab(srcPath);
      state.fileClipboard = null;
    }
    termPrint(`[Explorer] Arquivo ${mode === 'cut' ? 'movido' : 'colado'}: ${destPath}`, '#3fb950');
    await loadRepositoryTree(state.branch);
    await window.ideOpenFile(destPath);
  } catch (err) {
    termPrint(`[Erro ao colar] ${err.message}`, '#f85149');
  }
}

function copyTextToClipboard(text, label) {
  navigator.clipboard?.writeText(text);
  outputLog(`${label} copiado: ${text}`);
}

function showContextMenu(x, y, items) {
  const menu = $('#ncs-context-menu');
  if (!menu) return;
  menu.innerHTML = items.map((it, idx) => {
    if (it.sep) return '<div class="ncs-ctx-sep"></div>';
    return `
      <button type="button" class="ncs-ctx-item ${it.danger ? 'danger' : ''}" data-ctx-idx="${idx}" ${it.disabled ? 'disabled' : ''}>
        <span class="ncs-ctx-left">
          <span class="ncs-ctx-icon">${it.icon || ''}</span>
          <span>${esc(it.label)}</span>
        </span>
        ${it.kbd ? `<span class="ncs-ctx-kbd">${esc(it.kbd)}</span>` : ''}
      </button>
    `;
  }).join('');

  menu.style.display = 'flex';
  menu.style.left = '0px';
  menu.style.top = '0px';
  const rect = menu.getBoundingClientRect();
  const left = Math.min(x, window.innerWidth - rect.width - 8);
  const top = Math.min(y, window.innerHeight - rect.height - 8);
  menu.style.left = `${Math.max(4, left)}px`;
  menu.style.top = `${Math.max(4, top)}px`;

  menu.querySelectorAll('[data-ctx-idx]').forEach((btn) => {
    btn.onclick = (ev) => {
      ev.stopPropagation();
      menu.style.display = 'none';
      const item = items[Number(btn.dataset.ctxIdx)];
      if (item?.action) item.action();
    };
  });
}

function hideContextMenu() {
  const menu = $('#ncs-context-menu');
  if (menu) menu.style.display = 'none';
}

function openFileContextMenu(x, y, filePath, sha) {
  state.selectedTreePath = filePath;
  state.selectedTreeType = 'file';
  renderTree();
  const folderOfFile = filePath.includes('/') ? filePath.split('/').slice(0, -1).join('/') : '';
  const repoName = state.fullName.split('/').pop() || 'repo';

  showContextMenu(x, y, [
    { icon: '&#128196;', label: 'Abrir', kbd: 'Enter', action: () => window.ideOpenFile(filePath) },
    { icon: '&#9703;', label: 'Abrir ao Lado', kbd: 'Ctrl+Enter', action: () => window.ideOpenSplit(filePath) },
    { icon: '&#127760;', label: 'Open with Live Server', kbd: 'Alt+L Alt+O', action: async () => { await window.ideOpenFile(filePath); window.ideTogglePreview(true); } },
    { icon: '&#9654;', label: 'Show Side Preview', kbd: 'Ctrl+Shift+V', action: async () => { await window.ideOpenFile(filePath); window.ideTogglePreview(true); } },
    { icon: '&#8599;', label: 'Open in Browser (GitHub)', kbd: 'Ctrl+Shift+B', action: () => state.htmlUrl && window.open(`${state.htmlUrl}/blob/${state.branch}/${filePath}`, '_blank', 'noopener') },
    { sep: true },
    { icon: '>_', label: 'Open in Integrated Terminal', action: () => { state.cwd = folderOfFile; updatePromptDisplay(); $('#ncs-bottom-panel').style.display = 'flex'; $('#ncs-term-input').focus(); } },
    { icon: '&#8644;', label: 'Selecionar para Comparar (Diff)', action: () => window.ideOpenDiff(filePath) },
    { icon: '&#128337;', label: 'Abrir Linha do Tempo (Git)', action: () => { const b = $('#ncs-timeline-body'); if (b) b.style.display = 'block'; } },
    { sep: true },
    { icon: '&#9986;', label: 'Recortar', kbd: 'Ctrl+X', action: () => { state.fileClipboard = { mode: 'cut', path: filePath }; renderTree(); } },
    { icon: '&#128203;', label: 'Copiar', kbd: 'Ctrl+C', action: () => { state.fileClipboard = { mode: 'copy', path: filePath }; outputLog(`Arquivo copiado: ${filePath}`); } },
    { icon: '&#128203;', label: 'Colar', kbd: 'Ctrl+V', disabled: !state.fileClipboard, action: () => pasteClipboardFile(folderOfFile) },
    { sep: true },
    { icon: '&#128279;', label: 'Copiar o Caminho', kbd: 'Shift+Alt+C', action: () => copyTextToClipboard(`/workspaces/${repoName}/${filePath}`, 'Caminho completo') },
    { icon: '&#128279;', label: 'Copiar Caminho Relativo', kbd: 'Ctrl+K Ctrl+Shift+C', action: () => copyTextToClipboard(filePath, 'Caminho relativo') },
    { sep: true },
    { icon: '&#9998;', label: 'Renomear...', kbd: 'F2', action: () => window.ideRenameFile(filePath, sha) },
    { icon: '&#128465;', label: 'Excluir', kbd: 'Del', danger: true, action: () => window.ideDeleteFile(filePath, sha) }
  ]);
}

function openFolderContextMenu(x, y, folderPath) {
  state.selectedTreePath = folderPath;
  state.selectedTreeType = 'folder';
  renderTree();
  const repoName = state.fullName.split('/').pop() || 'repo';

  showContextMenu(x, y, [
    { icon: '&#128196;', label: 'Novo Arquivo...', action: () => window.ideCreateNewFile(`${folderPath}/`) },
    { icon: '&#128193;', label: 'Nova Pasta...', action: () => window.ideCreateNewFolder(`${folderPath}/`) },
    { sep: true },
    { icon: '>_', label: 'Open in Integrated Terminal', action: () => { state.cwd = folderPath; updatePromptDisplay(); $('#ncs-bottom-panel').style.display = 'flex'; $('#ncs-term-input').focus(); } },
    { icon: '&#128203;', label: 'Colar', kbd: 'Ctrl+V', disabled: !state.fileClipboard, action: () => pasteClipboardFile(folderPath) },
    { sep: true },
    { icon: '&#128279;', label: 'Copiar o Caminho', kbd: 'Shift+Alt+C', action: () => copyTextToClipboard(`/workspaces/${repoName}/${folderPath}`, 'Caminho completo') },
    { icon: '&#128279;', label: 'Copiar Caminho Relativo', kbd: 'Ctrl+K Ctrl+Shift+C', action: () => copyTextToClipboard(folderPath, 'Caminho relativo') },
    { sep: true },
    { icon: '&#8863;', label: 'Recolher Pastas no Explorador', action: () => { state.expandedFolders.clear(); renderTree(); } }
  ]);
}

function openTabContextMenu(x, y, tabPath) {
  const repoName = state.fullName.split('/').pop() || 'repo';
  showContextMenu(x, y, [
    { icon: '&times;', label: 'Fechar', kbd: 'Ctrl+W', action: () => window.ideCloseTab(tabPath) },
    { label: 'Fechar Outros', action: () => window.ideCloseOtherTabs(tabPath) },
    { label: 'Fechar à Direita', action: () => window.ideCloseTabsToRight(tabPath) },
    { label: 'Fechar Salvos', action: () => window.ideCloseSavedTabs() },
    { label: 'Fechar Todos', action: () => window.ideCloseAllTabs() },
    { sep: true },
    { icon: '&#128279;', label: 'Copiar o Caminho', kbd: 'Shift+Alt+C', action: () => copyTextToClipboard(`/workspaces/${repoName}/${tabPath}`, 'Caminho completo') },
    { icon: '&#128279;', label: 'Copiar Caminho Relativo', kbd: 'Ctrl+K Ctrl+Shift+C', action: () => copyTextToClipboard(tabPath, 'Caminho relativo') },
    { sep: true },
    { icon: '&#9703;', label: 'Abrir ao Lado', kbd: 'Ctrl+Enter', action: () => window.ideOpenSplit(tabPath) },
    { icon: '&#8644;', label: 'Comparar com Versão do Git (Diff)', action: () => window.ideOpenDiff(tabPath) }
  ]);
}

/* ==================== COMMITS, DEPLOYS & PORTS ==================== */
function renderCommits() {
  const html = state.commits.map((c) => `
    <div class="ncs-commit-card">
      <div style="font-weight:600; color:var(--gh-fg-default);">${esc(c.message)}</div>
      <div class="ncs-muted-xs" style="margin-top:3px; display:flex; justify-content:space-between;">
        <span><code>${esc(c.sha)}</code> · ${esc(c.author)}</span>
        ${c.html_url ? `<a href="${esc(c.html_url)}" target="_blank" rel="noopener" style="color:var(--gh-accent);">GitHub &#8599;</a>` : ''}
      </div>
    </div>
  `).join('') || '<div class="ncs-muted-xs">Sem commits recentes.</div>';

  if ($('#ncs-commits-list')) $('#ncs-commits-list').innerHTML = html;
  if ($('#ncs-timeline-body')) $('#ncs-timeline-body').innerHTML = `<div style="padding:6px 8px; display:flex; flex-direction:column; gap:5px;">${html}</div>`;
}

async function loadDeploysAndPorts() {
  try {
    const depData = await apiRequest(`/projetos/${projetoId}/deploys`);
    state.deployments = depData.deployments || [];
    state.actionsRuns = depData.actions_runs || [];
  } catch {
    state.deployments = [];
    state.actionsRuns = [];
  }

  const depList = $('#ncs-deploys-list');
  if (depList) {
    const items = [
      ...state.deployments.map((d) => `
        <div class="ncs-commit-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <b style="color:#7ee787;">${esc(d.state || 'READY')}</b>
            <span class="ncs-muted-xs">${esc(d.target || 'production')}</span>
          </div>
          <div class="ncs-muted-xs" style="margin:3px 0;">${esc(d.commit_msg)}</div>
          ${d.url ? `<a href="${esc(d.url)}" target="_blank" rel="noopener" style="color:var(--gh-accent); font-size:11.5px;">${esc(d.url)} &#8599;</a>` : ''}
        </div>
      `),
      ...state.actionsRuns.map((r) => `
        <div class="ncs-commit-card">
          <div style="display:flex; justify-content:space-between;">
            <b>CI: ${esc(r.name)}</b>
            <span class="ncs-muted-xs">${esc(r.conclusion || r.status)}</span>
          </div>
          <div class="ncs-muted-xs">Branch: ${esc(r.branch)} · <a href="${esc(r.html_url)}" target="_blank" rel="noopener" style="color:var(--gh-accent);">Logs &#8599;</a></div>
        </div>
      `)
    ];
    depList.innerHTML = items.join('') || '<div class="ncs-muted-xs">Nenhum deploy recente registrado.</div>';
  }

  const ports = [
    { port: '3000', label: 'Live Server Preview (Local)', url: '#preview', vis: 'Privado (IDE)' }
  ];
  if (state.projeto?.url_homologacao) {
    ports.push({ port: '443 (Staging)', label: 'Homologação Nexus Cloud', url: state.projeto.url_homologacao, vis: 'Público' });
  }
  if (state.projeto?.url_producao) {
    ports.push({ port: '443 (Prod)', label: 'Produção Vercel', url: state.projeto.url_producao, vis: 'Público' });
  }
  $('#ncs-ports-count').textContent = ports.length;
  const tbody = $('#ncs-ports-tbody');
  if (tbody) {
    tbody.innerHTML = ports.map((p) => `
      <tr>
        <td><b>${esc(p.port)}</b></td>
        <td>${esc(p.label)}</td>
        <td>${p.url === '#preview'
          ? `<a href="#" onclick="event.preventDefault(); window.ideTogglePreview(true);">http://localhost:3000 (Preview Integrado)</a>`
          : `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)} &#8599;</a>`}</td>
        <td>${esc(p.vis)}</td>
        <td>
          ${p.url === '#preview'
            ? `<button type="button" class="ncs-top-btn" onclick="window.ideTogglePreview(true)">Abrir</button>`
            : `<a href="${esc(p.url)}" target="_blank" rel="noopener" class="ncs-top-btn">Abrir &#8599;</a>`}
        </td>
      </tr>
    `).join('');
  }

  const envLinks = $('#ncs-env-links');
  if (envLinks) {
    envLinks.innerHTML = ports.filter((p) => p.url !== '#preview').map((p) => `
      <div class="ncs-commit-card">
        <div style="font-weight:700;">${esc(p.label)}</div>
        <a href="${esc(p.url)}" target="_blank" rel="noopener" style="color:var(--gh-accent); font-size:11.5px; word-break:break-all;">${esc(p.url)} &#8599;</a>
      </div>
    `).join('') || '<div class="ncs-muted-xs">Configure URLs de homologação ou produção no projeto.</div>';
  }
}

async function loadRepositoryTree(branch = null) {
  const qs = branch ? `?branch=${encodeURIComponent(branch)}` : '';
  const data = await apiRequest(`/projetos/${projetoId}/ide/tree${qs}`);
  state.projeto = data.projeto;
  state.fullName = data.full_name;
  state.htmlUrl = data.html_url;
  state.branch = data.branch;
  state.branches = data.branches || [data.branch];
  state.tree = data.tree || [];
  state.commits = data.commits || [];

  const repoShort = data.full_name.split('/').pop() || data.projeto.titulo;
  document.title = `${repoShort} · Nexus CodeSpaces`;
  $('#ncs-tree-repo-title').textContent = repoShort;
  $('#ncs-cmd-title').textContent = `${repoShort} [${data.branch}] — Nexus CodeSpaces`;
  $('#ncs-branch-name').textContent = data.branch;
  $('#ncs-link-github').href = data.html_url;
  updatePromptDisplay();
  $('#ncs-commit-msg').placeholder = `Mensagem (Ctrl+Enter para Commit & Push em "${data.branch}")`;

  renderTree();
  renderCommits();
  loadDeploysAndPorts();

  if (!state.openTabs.length) {
    const readme = state.tree.find((n) => n.type === 'blob' && n.path.toLowerCase() === 'readme.md') || state.tree.find((n) => n.type === 'blob');
    if (readme) await window.ideOpenFile(readme.path);
  }
}

async function commitDirtyFiles(customMsg = null) {
  const dirtyTabs = state.openTabs.filter((t) => t.dirty && !t.isBinary);
  if (!dirtyTabs.length) {
    termPrint('[Git] Working tree clean — nenhuma alteração pendente para commit.', '#8b949e');
    return;
  }
  const msg = (customMsg || $('#ncs-commit-msg')?.value || '').trim() || `feat: atualiza ${dirtyTabs.map((d) => d.name).join(', ')}`;
  $('#ncs-sync-status').innerHTML = '<span style="color:#58a6ff;">&#8635; Enviando commit para GitHub...</span>';

  try {
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
      termPrint(`[Git Push] ${tab.path} -> commit ${res.commit_sha} (${state.branch})`, '#3fb950');
      outputLog(`Commit ${res.commit_sha} publicado em ${tab.path}`);
    }

    if ($('#ncs-commit-msg')) $('#ncs-commit-msg').value = '';
    state.diffMode = false;
    renderTabs();
    syncEditorView();
    await loadRepositoryTree(state.branch);
  } catch (err) {
    $('#ncs-sync-status').innerHTML = '<span style="color:#f85149;">&#10007; Erro no Push</span>';
    termPrint(`[Git Erro] ${err.message}`, '#f85149');
  }
}

async function triggerDeploy(target = 'production') {
  termPrint(`[Nexus Cloud] Disparando deploy (${target}) da branch '${state.branch}'...`, '#58a6ff');
  outputLog(`Iniciando deploy Vercel (${target})...`);
  try {
    const res = await apiRequest(`/projetos/${projetoId}/deploy`, {
      method: 'POST',
      body: JSON.stringify({ target, branch: state.branch })
    });
    termPrint(`[Nexus Cloud] Deploy iniciado! Status: ${res.deploy.status} | URL: ${res.deploy.url}`, '#3fb950');
    outputLog(`Deploy criado: ${res.deploy.url}`);
    await loadDeploysAndPorts();
    if (res.deploy.url) window.open(res.deploy.url, '_blank', 'noopener');
  } catch (err) {
    termPrint(`[Nexus Cloud Erro] ${err.message}`, '#f85149');
  }
}

/* ==================== MULTI-FILE SMART LIVE PREVIEW ==================== */
async function refreshLivePreview() {
  const frame = $('#ncs-preview-frame');
  if (!frame) return;

  const activeTab = state.openTabs.find((t) => t.path === state.activePath);
  if (activeTab && activeTab.path.toLowerCase().endsWith('.md')) {
    $('#ncs-preview-label').textContent = activeTab.path;
    const mdHtml = esc(activeTab.content)
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;padding:2px 5px;border-radius:4px;">$1</code>')
      .replace(/\n/g, '<br>');
    frame.srcdoc = `<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:28px 36px;color:#1f2328;line-height:1.6;max-width:860px;margin:auto;">${mdHtml}</body></html>`;
    return;
  }

  let htmlTab = activeTab && activeTab.path.toLowerCase().endsWith('.html') ? activeTab : null;
  if (!htmlTab) {
    const htmlNode = state.tree.find((n) => n.type === 'blob' && /(^|\/)index\.html$/i.test(n.path));
    if (htmlNode) {
      htmlTab = state.openTabs.find((t) => t.path === htmlNode.path);
      if (!htmlTab) {
        try {
          const f = await apiRequest(`/projetos/${projetoId}/ide/file?path=${encodeURIComponent(htmlNode.path)}&branch=${encodeURIComponent(state.branch)}`);
          htmlTab = { path: f.path, content: f.content };
        } catch {}
      }
    }
  }

  if (!htmlTab) {
    $('#ncs-preview-label').textContent = 'localhost:3000';
    frame.srcdoc = `<!DOCTYPE html><html><body style="font-family:system-ui;padding:32px;background:#0d1117;color:#e6edf3;"><h3>Nenhum arquivo HTML encontrado</h3><p style="color:#8b949e;">Abra um arquivo <code>.html</code> ou <code>.md</code> para visualizar o Live Server Preview.</p></body></html>`;
    return;
  }

  $('#ncs-preview-label').textContent = `localhost:3000/${htmlTab.path}`;
  let rendered = htmlTab.content;

  const cssTabs = state.openTabs.filter((t) => t.path.toLowerCase().endsWith('.css'));
  const jsTabs = state.openTabs.filter((t) => t.path.toLowerCase().endsWith('.js'));
  if (cssTabs.length) {
    const styleBlock = `<style>${cssTabs.map((c) => c.content).join('\n')}</style>`;
    rendered = rendered.includes('</head>') ? rendered.replace('</head>', `${styleBlock}</head>`) : styleBlock + rendered;
  }
  if (jsTabs.length) {
    const scriptBlock = `<script>${jsTabs.map((j) => j.content).join('\n')}<\/script>`;
    rendered = rendered.includes('</body>') ? rendered.replace('</body>', `${scriptBlock}</body>`) : rendered + scriptBlock;
  }

  frame.srcdoc = rendered;
}

window.ideTogglePreview = (forceOpen = null) => {
  const pane = $('#ncs-preview-pane');
  const open = forceOpen !== null ? forceOpen : pane.style.display !== 'flex';
  pane.style.display = open ? 'flex' : 'none';
  const glBtn = $('#ncs-golive-btn');
  if (glBtn) glBtn.innerHTML = open ? '&#9209; Port: 3000' : '&#128225; Go Live';
  if (open) refreshLivePreview();
  if (monacoEditor) monacoEditor.layout();
};

/* ==================== COMMAND PALETTE & TOP MENU COMMANDS ==================== */
const COMMANDS = [
  { id: 'newFile', label: 'Arquivo: Novo Arquivo no Repositório', shortcut: 'Ctrl+N', run: () => window.ideCreateNewFile() },
  { id: 'newFolder', label: 'Arquivo: Nova Pasta', shortcut: '', run: () => window.ideCreateNewFolder() },
  { id: 'commitPush', label: 'Git: Commit & Push para GitHub', shortcut: 'Ctrl+S', run: () => commitDirtyFiles() },
  { id: 'closeTab', label: 'Arquivo: Fechar Editor Ativo', shortcut: 'Ctrl+W', run: () => state.activePath && window.ideCloseTab(state.activePath) },
  { id: 'closeAllTabs', label: 'Arquivo: Fechar Todos os Editores', shortcut: '', run: () => window.ideCloseAllTabs() },
  { id: 'undo', label: 'Editar: Desfazer', shortcut: 'Ctrl+Z', run: () => monacoEditor?.trigger('menu', 'undo', null) },
  { id: 'redo', label: 'Editar: Refazer', shortcut: 'Ctrl+Y', run: () => monacoEditor?.trigger('menu', 'redo', null) },
  { id: 'find', label: 'Editar: Localizar no Arquivo', shortcut: 'Ctrl+F', run: () => monacoEditor?.getAction('actions.find')?.run() },
  { id: 'replace', label: 'Editar: Substituir no Arquivo', shortcut: 'Ctrl+H', run: () => monacoEditor?.getAction('editor.action.startFindReplaceAction')?.run() },
  { id: 'toggleComment', label: 'Editar: Alternar Comentário de Linha', shortcut: 'Ctrl+;', run: () => monacoEditor?.getAction('editor.action.commentLine')?.run() },
  { id: 'format', label: 'Editar: Formatar Documento', shortcut: 'Shift+Alt+F', run: () => monacoEditor?.getAction('editor.action.formatDocument')?.run() },
  { id: 'selectAll', label: 'Seleção: Selecionar Tudo', shortcut: 'Ctrl+A', run: () => monacoEditor?.setSelection(monacoEditor.getModel()?.getFullModelRange()) },
  { id: 'copyLineDown', label: 'Seleção: Copiar Linha Abaixo', shortcut: 'Shift+Alt+Down', run: () => monacoEditor?.getAction('editor.action.copyLinesDownAction')?.run() },
  { id: 'moveLineUp', label: 'Seleção: Mover Linha para Cima', shortcut: 'Alt+Up', run: () => monacoEditor?.getAction('editor.action.moveLinesUpAction')?.run() },
  { id: 'moveLineDown', label: 'Seleção: Mover Linha para Baixo', shortcut: 'Alt+Down', run: () => monacoEditor?.getAction('editor.action.moveLinesDownAction')?.run() },
  { id: 'addCursorNext', label: 'Seleção: Adicionar Próxima Ocorrência', shortcut: 'Ctrl+D', run: () => monacoEditor?.getAction('editor.action.addSelectionToNextFindMatch')?.run() },
  { id: 'commandPalette', label: 'Exibir: Paleta de Comandos...', shortcut: 'Ctrl+Shift+P', run: () => openQuickOpen('>') },
  { id: 'quickOpen', label: 'Acessar: Ir para Arquivo...', shortcut: 'Ctrl+P', run: () => openQuickOpen('') },
  { id: 'goToSymbol', label: 'Acessar: Ir para Símbolo no Editor...', shortcut: 'Ctrl+Shift+O', run: () => monacoEditor?.getAction('editor.action.quickOutline')?.run() },
  { id: 'goToLine', label: 'Acessar: Ir para Linha/Coluna...', shortcut: 'Ctrl+G', run: () => monacoEditor?.getAction('editor.action.gotoLine')?.run() },
  { id: 'navBack', label: 'Acessar: Voltar Editor', shortcut: 'Alt+Left', run: () => $('#ncs-nav-back')?.click() },
  { id: 'navFwd', label: 'Acessar: Avançar Editor', shortcut: 'Alt+Right', run: () => $('#ncs-nav-fwd')?.click() },
  { id: 'showExplorer', label: 'Exibir: Explorador', shortcut: 'Ctrl+Shift+E', run: () => activateSidebarTab('explorer') },
  { id: 'searchInFiles', label: 'Exibir: Pesquisar nos Arquivos', shortcut: 'Ctrl+Shift+F', run: () => { activateSidebarTab('search'); $('#ncs-search-input')?.focus(); } },
  { id: 'showGit', label: 'Exibir: Controle do Código-Fonte (Git)', shortcut: 'Ctrl+Shift+G', run: () => activateSidebarTab('git') },
  { id: 'showDeploys', label: 'Exibir: Nexus Cloud & Deploys', shortcut: '', run: () => activateSidebarTab('deploys') },
  { id: 'toggleSidebar', label: 'Exibir: Alternar Barra Lateral Primária', shortcut: 'Ctrl+B', run: () => togglePrimarySidebar() },
  { id: 'toggleTerminal', label: 'Exibir: Alternar Painel Inferior / Terminal', shortcut: 'Ctrl+`', run: () => toggleBottomPanel() },
  { id: 'splitEditorRight', label: 'Exibir: Dividir Editor à Direita (Abrir ao Lado)', shortcut: 'Ctrl+\\', run: () => state.activePath && window.ideOpenSplit(state.activePath) },
  { id: 'togglePreview', label: 'Exibir: Show Side Preview', shortcut: 'Ctrl+Shift+V', run: () => window.ideTogglePreview() },
  { id: 'openLiveServer', label: 'Live Server: Open with Live Server', shortcut: 'Alt+L Alt+O', run: () => window.ideTogglePreview(true) },
  { id: 'toggleMinimap', label: 'Exibir: Alternar Minimapa', shortcut: '', run: () => { state.prefs.minimap = !state.prefs.minimap; monacoEditor?.updateOptions({ minimap: { enabled: state.prefs.minimap } }); } },
  { id: 'toggleWordWrap', label: 'Exibir: Alternar Quebra de Linha (Word Wrap)', shortcut: 'Alt+Z', run: () => { state.prefs.wordWrap = state.prefs.wordWrap === 'on' ? 'off' : 'on'; monacoEditor?.updateOptions({ wordWrap: state.prefs.wordWrap }); } },
  { id: 'toggleDiff', label: 'Git: Comparar Alterações (Diff View)', shortcut: '', run: () => { state.diffMode = !state.diffMode; syncEditorView(); renderTabs(); } },
  { id: 'branch', label: 'Git: Trocar ou Criar Nova Branch', shortcut: '', run: () => switchOrCreateBranch() },
  { id: 'deployProd', label: 'Nexus Cloud: Deploy Produção (Vercel)', shortcut: '', run: () => triggerDeploy('production') },
  { id: 'deployPrev', label: 'Nexus Cloud: Deploy Homologação (Preview)', shortcut: '', run: () => triggerDeploy('preview') },
  { id: 'focusTerminal', label: 'Terminal: Focar Terminal Integrado', shortcut: 'Ctrl+`', run: () => { $('#ncs-bottom-panel').style.display = 'flex'; $('#ncs-term-input')?.focus(); } },
  { id: 'runGitStatus', label: 'Terminal: Executar git status', shortcut: '', run: () => { $('#ncs-bottom-panel').style.display = 'flex'; executeTerminalCommand('git status'); } },
  { id: 'clearTerminal', label: 'Terminal: Limpar Terminal', shortcut: '', run: () => { $('#ncs-terminal-out').innerHTML = ''; } },
  { id: 'openGitHub', label: 'GitHub: Abrir Repositório no Navegador', shortcut: '', run: () => state.htmlUrl && window.open(state.htmlUrl, '_blank', 'noopener') },
  { id: 'backPortal', label: 'Nexus ERP: Voltar ao Portal Principal', shortcut: '', run: () => { window.location.href = './index.html'; } }
];

let qoSelectedIdx = 0;
let qoCurrentItems = [];

function openQuickOpen(prefix = '') {
  const modal = $('#ncs-quickopen');
  const inp = $('#ncs-quickopen-input');
  modal.style.display = 'flex';
  inp.value = prefix;
  inp.focus();
  renderQuickOpenList(prefix);
}

function renderQuickOpenList(rawQuery) {
  const list = $('#ncs-quickopen-list');
  const isCmd = rawQuery.startsWith('>');
  const q = (isCmd ? rawQuery.slice(1) : rawQuery).trim().toLowerCase();

  if (isCmd) {
    qoCurrentItems = COMMANDS.filter((c) => c.label.toLowerCase().includes(q)).map((c) => ({
      type: 'cmd',
      cmd: c
    }));
  } else {
    qoCurrentItems = state.tree
      .filter((n) => n.type === 'blob' && !n.path.endsWith('/.gitkeep') && n.path.toLowerCase().includes(q))
      .slice(0, 25)
      .map((f) => ({ type: 'file', path: f.path }));
  }

  qoSelectedIdx = 0;
  list.innerHTML = qoCurrentItems.map((item, i) => {
    if (item.type === 'cmd') {
      return `
        <div class="ncs-qo-item ${i === 0 ? 'selected' : ''}" data-qo-idx="${i}">
          <span>&#9656; ${esc(item.cmd.label)}</span>
          <span class="ncs-muted-xs">${esc(item.cmd.shortcut)}</span>
        </div>
      `;
    }
    return `
      <div class="ncs-qo-item ${i === 0 ? 'selected' : ''}" data-qo-idx="${i}">
        <span style="display:flex; align-items:center; gap:8px;">${getFileBadge(item.path)} ${esc(item.path.split('/').pop())}</span>
        <span class="ncs-muted-xs">${esc(item.path)}</span>
      </div>
    `;
  }).join('') || '<div class="ncs-muted-xs" style="padding:12px;">Nenhum resultado encontrado.</div>';

  list.querySelectorAll('[data-qo-idx]').forEach((el) => {
    el.onclick = () => executeQuickOpenItem(Number(el.dataset.qoIdx));
  });
}

function executeQuickOpenItem(idx) {
  const item = qoCurrentItems[idx];
  $('#ncs-quickopen').style.display = 'none';
  if (!item) return;
  if (item.type === 'cmd') item.cmd.run();
  else window.ideOpenFile(item.path);
}

/* ==================== SEARCH ACROSS REPO ==================== */
async function runRepoSearch() {
  const q = ($('#ncs-search-input')?.value || '').trim();
  const resBox = $('#ncs-search-results');
  const meta = $('#ncs-search-meta');
  if (!q) {
    resBox.innerHTML = '';
    meta.textContent = '';
    return;
  }

  const needle = state.searchCaseSensitive ? q : q.toLowerCase();
  const blobs = state.tree.filter((n) => n.type === 'blob' && !n.path.endsWith('/.gitkeep'));

  for (const b of blobs.slice(0, 25)) {
    if (!state.openTabs.some((t) => t.path === b.path) && b.size < 120000) {
      try {
        const f = await apiRequest(`/projetos/${projetoId}/ide/file?path=${encodeURIComponent(b.path)}&branch=${encodeURIComponent(state.branch)}`);
        if (!f.is_binary) {
          state.openTabs.push({
            path: f.path, name: f.name, content: f.content, originalContent: f.content,
            sha: f.sha, dirty: false, isBinary: false
          });
        }
      } catch {}
    }
  }
  renderTabs();

  let totalMatches = 0;
  const groups = [];

  for (const tab of state.openTabs) {
    if (tab.isBinary) continue;
    const lines = tab.content.split('\n');
    const hits = [];
    lines.forEach((lineText, idx) => {
      const hay = state.searchCaseSensitive ? lineText : lineText.toLowerCase();
      if (hay.includes(needle)) {
        hits.push({ line: idx + 1, text: lineText.trim() });
        totalMatches++;
      }
    });
    if (hits.length) groups.push({ path: tab.path, hits });
  }

  meta.textContent = `${totalMatches} resultado(s) em ${groups.length} arquivo(s)`;
  resBox.innerHTML = groups.map((g) => `
    <div style="margin-bottom:8px;">
      <div class="ncs-tree-row" style="padding-left:4px; font-weight:700;" onclick="window.ideOpenFile('${esc(g.path)}')">
        ${getFileBadge(g.path)}
        <span class="ncs-tree-name">${esc(g.path)}</span>
        <span class="ncs-acc-count">${g.hits.length}</span>
      </div>
      ${g.hits.slice(0, 15).map((h) => `
        <div class="ncs-tree-row" style="padding-left:20px; font-size:12px; color:var(--gh-fg-muted);" onclick="window.ideOpenFile('${esc(g.path)}', ${h.line})">
          <span style="color:var(--gh-accent); min-width:26px;">:${h.line}</span>
          <span class="ncs-tree-name">${esc(h.text)}</span>
        </div>
      `).join('')}
    </div>
  `).join('') || '<div class="ncs-muted-xs">Nenhuma correspondência encontrada.</div>';
}

/* ==================== BRANCH SWITCHER & PANEL CONTROLS ==================== */
async function switchOrCreateBranch() {
  const next = await openInputDialog({
    title: 'Trocar ou Criar Branch Git',
    desc: `Branches existentes: ${state.branches.join(', ')}`,
    defaultValue: state.branch,
    placeholder: 'Digite o nome da branch...',
    confirmText: 'Alternar / Criar Branch'
  });
  if (!next || !next.trim() || next.trim() === state.branch) return;
  const bName = next.trim();
  try {
    if (!state.branches.includes(bName)) {
      await apiRequest(`/projetos/${projetoId}/ide/branch`, {
        method: 'POST',
        body: JSON.stringify({ new_branch: bName, from_branch: state.branch })
      });
      termPrint(`[Git] Nova branch '${bName}' criada a partir de '${state.branch}'.`, '#3fb950');
    }
    state.openTabs = [];
    state.activePath = null;
    await loadRepositoryTree(bName);
  } catch (err) {
    termPrint(`[Git Branch Erro] ${err.message}`, '#f85149');
  }
}

function activateSidebarTab(tabId) {
  const sb = $('#ncs-sidebar');
  sb.style.display = 'flex';
  $('#ncs-layout-sidebar')?.classList.add('active');
  document.querySelectorAll('[data-side-tab]').forEach((b) => b.classList.toggle('active', b.dataset.sideTab === tabId));
  document.querySelectorAll('.ncs-side-pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${tabId}`));
  if (monacoEditor) monacoEditor.layout();
}

function togglePrimarySidebar() {
  const sb = $('#ncs-sidebar');
  const open = sb.style.display === 'none';
  sb.style.display = open ? 'flex' : 'none';
  $('#ncs-layout-sidebar')?.classList.toggle('active', open);
  if (monacoEditor) monacoEditor.layout();
}

function toggleBottomPanel() {
  const p = $('#ncs-bottom-panel');
  const open = p.style.display === 'none';
  p.style.display = open ? 'flex' : 'none';
  $('#ncs-layout-panel')?.classList.toggle('active', open);
  if (monacoEditor) monacoEditor.layout();
}

/* ==================== RESIZABLE SPLITTERS ==================== */
function setupResizers() {
  const sbResizer = $('#ncs-sidebar-resizer');
  const sb = $('#ncs-sidebar');
  sbResizer?.addEventListener('mousedown', (e) => {
    e.preventDefault();
    sbResizer.classList.add('dragging');
    const onMove = (ev) => {
      const w = Math.min(520, Math.max(180, ev.clientX - 48));
      sb.style.width = `${w}px`;
      if (monacoEditor) monacoEditor.layout();
    };
    const onUp = () => {
      sbResizer.classList.remove('dragging');
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });

  const pResizer = $('#ncs-panel-resizer');
  const panel = $('#ncs-bottom-panel');
  pResizer?.addEventListener('mousedown', (e) => {
    e.preventDefault();
    pResizer.classList.add('dragging');
    const onMove = (ev) => {
      const h = Math.min(window.innerHeight * 0.65, Math.max(95, window.innerHeight - ev.clientY - 24));
      panel.style.height = `${h}px`;
      if (monacoEditor) monacoEditor.layout();
    };
    const onUp = () => {
      pResizer.classList.remove('dragging');
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });
}

/* ==================== VIRTUAL BASH & GIT TERMINAL ==================== */
async function executeTerminalCommand(rawCmd) {
  const cmd = rawCmd.trim();
  if (!cmd) return;
  state.termHistory.push(cmd);
  state.termHistIdx = state.termHistory.length;

  const prefix = state.cwd ? `/${state.cwd}` : '';
  termPrint(`nexus@codespaces:~/${state.fullName.split('/').pop() || 'repo'}${prefix}$ ${cmd}`, '#58a6ff');

  if (cmd === 'help') {
    termPrint(
      'Nexus CodeSpaces Shell (bash 5.2)\n' +
      '  ls / ls -la             Lista arquivos do diretório atual\n' +
      '  pwd / cd <dir>          Navega entre pastas do repositório\n' +
      '  cat <arquivo>           Exibe o conteúdo de um arquivo\n' +
      '  touch <arquivo>         Cria um novo arquivo no GitHub\n' +
      '  mkdir <pasta>           Cria um novo diretório no GitHub\n' +
      '  rm <arquivo>            Remove um arquivo do repositório\n' +
      '  git status              Mostra alterações pendentes na working tree\n' +
      '  git branch              Lista branches do repositório\n' +
      '  git checkout -b <nome>  Cria e muda para uma nova branch\n' +
      '  git commit -m "msg"     Faz commit & push das alterações\n' +
      '  git log                 Exibe os últimos commits\n' +
      '  npm run dev / start     Inicia servidor e abre Live Server Preview\n' +
      '  nexus deploy            Dispara deploy em produção na Vercel\n' +
      '  clear                   Limpa o terminal'
    );
  } else if (cmd === 'clear') {
    $('#ncs-terminal-out').innerHTML = '';
  } else if (cmd === 'pwd') {
    termPrint(`/workspaces/${state.fullName.split('/').pop() || 'repo'}${prefix}`);
  } else if (cmd === 'whoami') {
    termPrint(state.user?.email || 'nexus-dev');
  } else if (cmd === 'date') {
    termPrint(new Date().toString());
  } else if (cmd === 'cd' || cmd === 'cd ~' || cmd === 'cd /') {
    state.cwd = '';
    updatePromptDisplay();
  } else if (cmd.startsWith('cd ')) {
    const target = cmd.slice(3).trim().replace(/\/+$/, '');
    if (target === '..') {
      state.cwd = state.cwd.split('/').slice(0, -1).join('/');
      updatePromptDisplay();
    } else {
      const nextDir = state.cwd ? `${state.cwd}/${target}` : target;
      const exists = state.tree.some((n) => n.path.startsWith(nextDir + '/'));
      if (exists) {
        state.cwd = nextDir;
        updatePromptDisplay();
      } else {
        termPrint(`bash: cd: ${target}: Arquivo ou diretório inexistente`, '#f85149');
      }
    }
  } else if (cmd === 'ls' || cmd === 'ls -la' || cmd === 'ls -l') {
    const blobs = state.tree.filter((n) => n.type === 'blob').map((n) => n.path);
    const scoped = state.cwd ? blobs.filter((p) => p.startsWith(state.cwd + '/')).map((p) => p.slice(state.cwd.length + 1)) : blobs;
    termPrint(scoped.join('   ') || '(diretório vazio)');
  } else if (cmd.startsWith('cat ')) {
    const f = cmd.slice(4).trim();
    const full = state.cwd ? `${state.cwd}/${f}` : f;
    await window.ideOpenFile(full);
    const tab = state.openTabs.find((t) => t.path === full);
    if (tab) termPrint(tab.content);
  } else if (cmd.startsWith('touch ')) {
    const f = cmd.slice(6).trim();
    const full = state.cwd ? `${state.cwd}/${f}` : f;
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({ path: full, content: '', branch: state.branch })
    });
    await loadRepositoryTree(state.branch);
    termPrint(`Arquivo '${full}' criado.`, '#3fb950');
  } else if (cmd.startsWith('mkdir ')) {
    const d = cmd.slice(6).trim().replace(/\/+$/, '');
    const full = state.cwd ? `${state.cwd}/${d}/.gitkeep` : `${d}/.gitkeep`;
    await apiRequest(`/projetos/${projetoId}/ide/file`, {
      method: 'POST',
      body: JSON.stringify({ path: full, content: '', branch: state.branch })
    });
    await loadRepositoryTree(state.branch);
    termPrint(`Diretório '${d}' criado.`, '#3fb950');
  } else if (cmd.startsWith('rm ')) {
    const f = cmd.slice(3).trim();
    const full = state.cwd ? `${state.cwd}/${f}` : f;
    const node = state.tree.find((n) => n.path === full);
    if (!node) termPrint(`rm: não foi possível remover '${f}': Arquivo inexistente`, '#f85149');
    else await window.ideDeleteFile(full, node.sha);
  } else if (cmd === 'git status') {
    const dirty = state.openTabs.filter((t) => t.dirty).map((t) => `\tmodified:   ${t.path}`);
    termPrint(`On branch ${state.branch}\n${dirty.length ? 'Changes not staged for commit:\n' + dirty.join('\n') : 'nothing to commit, working tree clean'}`);
  } else if (cmd === 'git branch') {
    termPrint(state.branches.map((b) => (b === state.branch ? `* ${b}` : `  ${b}`)).join('\n'));
  } else if (cmd === 'git log') {
    termPrint(state.commits.slice(0, 8).map((c) => `commit ${c.sha} (${c.author})\n    ${c.message}`).join('\n\n') || 'Sem commits.');
  } else if (cmd.startsWith('git checkout -b ')) {
    const nb = cmd.replace('git checkout -b ', '').trim();
    await apiRequest(`/projetos/${projetoId}/ide/branch`, { method: 'POST', body: JSON.stringify({ new_branch: nb, from_branch: state.branch }) });
    await loadRepositoryTree(nb);
    termPrint(`Switched to a new branch '${nb}'`, '#3fb950');
  } else if (cmd.startsWith('git checkout ')) {
    const tb = cmd.replace('git checkout ', '').trim();
    await loadRepositoryTree(tb);
    termPrint(`Switched to branch '${tb}'`, '#3fb950');
  } else if (cmd.startsWith('git commit')) {
    const m = cmd.match(/-m\s+["'](.+?)["']/);
    await commitDirtyFiles(m ? m[1] : null);
  } else if (cmd === 'git push') {
    await commitDirtyFiles();
  } else if (cmd === 'npm run dev' || cmd === 'npm start') {
    termPrint('> Live Server ativo em http://localhost:3000', '#3fb950');
    window.ideTogglePreview(true);
  } else if (cmd === 'nexus deploy') {
    await triggerDeploy('production');
  } else if (cmd === 'nexus preview') {
    await triggerDeploy('preview');
  } else {
    termPrint(`bash: ${cmd}: comando não encontrado (digite 'help')`, '#f85149');
  }
}

/* ==================== EVENT BINDINGS & BOOT ==================== */
function bindEvents() {
  // Top VS Code Menu Bar (Arquivo, Editar, Seleção, Exibir, Acessar, Executar, Terminal)
  let openMenuName = null;
  const closeAllTopMenus = () => {
    openMenuName = null;
    document.querySelectorAll('.ncs-menubar-btn').forEach((b) => b.classList.remove('open'));
    document.querySelectorAll('.ncs-dropdown-menu').forEach((m) => { m.style.display = 'none'; });
  };
  const showTopMenu = (name) => {
    closeAllTopMenus();
    openMenuName = name;
    document.querySelector(`.ncs-menubar-btn[data-menu="${name}"]`)?.classList.add('open');
    const menuEl = $(`#menu-${name}`);
    if (menuEl) menuEl.style.display = 'flex';
  };

  document.querySelectorAll('.ncs-menubar-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      hideContextMenu();
      const mName = btn.dataset.menu;
      if (openMenuName === mName) closeAllTopMenus();
      else showTopMenu(mName);
    });
    btn.addEventListener('mouseenter', () => {
      if (openMenuName && openMenuName !== btn.dataset.menu) {
        showTopMenu(btn.dataset.menu);
      }
    });
  });

  document.querySelectorAll('.ncs-dropdown-menu [data-cmd]').forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      closeAllTopMenus();
      const cmdObj = COMMANDS.find((c) => c.id === btn.dataset.cmd);
      if (cmdObj) cmdObj.run();
    };
  });

  document.addEventListener('click', () => {
    closeAllTopMenus();
    hideContextMenu();
  });

  // Global VS Code Context Menu Handler (Intercepta botão direito no Explorador, Abas e Chrome da IDE)
  document.addEventListener('contextmenu', (e) => {
    closeAllTopMenus();
    // Mantém o menu de contexto nativo do VS Code dentro do Monaco Editor
    if (e.target.closest('#ncs-monaco-container') || e.target.closest('#ncs-monaco-split-container') || e.target.closest('#ncs-diff-container') || e.target.closest('input') || e.target.closest('textarea')) {
      hideContextMenu();
      return;
    }

    e.preventDefault();
    const treeRow = e.target.closest('[data-ctx-type="file"]');
    if (treeRow) {
      openFileContextMenu(e.clientX, e.clientY, treeRow.dataset.ctxPath, treeRow.dataset.ctxSha || null);
      return;
    }

    const folderRow = e.target.closest('[data-ctx-type="folder"]');
    if (folderRow) {
      openFolderContextMenu(e.clientX, e.clientY, folderRow.dataset.ctxPath);
      return;
    }

    const tabEl = e.target.closest('[data-ctx-type="tab"]');
    if (tabEl) {
      openTabContextMenu(e.clientX, e.clientY, tabEl.dataset.ctxPath);
      return;
    }

    if (e.target.closest('#ncs-file-tree')) {
      showContextMenu(e.clientX, e.clientY, [
        { icon: '&#128196;', label: 'Novo Arquivo...', action: () => window.ideCreateNewFile() },
        { icon: '&#128193;', label: 'Nova Pasta...', action: () => window.ideCreateNewFolder() },
        { icon: '&#128203;', label: 'Colar', kbd: 'Ctrl+V', disabled: !state.fileClipboard, action: () => pasteClipboardFile('') },
        { sep: true },
        { icon: '&#8863;', label: 'Recolher Pastas', action: () => { state.expandedFolders.clear(); renderTree(); } },
        { icon: '&#8635;', label: 'Atualizar Explorador', action: () => loadRepositoryTree(state.branch) }
      ]);
      return;
    }

    showContextMenu(e.clientX, e.clientY, [
      { icon: '&#9656;', label: 'Paleta de Comandos...', kbd: 'Ctrl+Shift+P', action: () => openQuickOpen('>') },
      { icon: '&#128269;', label: 'Ir para Arquivo...', kbd: 'Ctrl+P', action: () => openQuickOpen('') },
      { sep: true },
      { icon: '&#10003;', label: 'Commit & Push para GitHub', kbd: 'Ctrl+S', action: () => commitDirtyFiles() },
      { icon: '&#9889;', label: 'Deploy Produção (Vercel)', action: () => triggerDeploy('production') }
    ]);
  });

  // Explorer Keyboard Shortcuts (F2 Rename, Del Delete, Ctrl+C/X/V File Clipboard)
  $('#ncs-file-tree')?.addEventListener('keydown', (e) => {
    if (!state.selectedTreePath || state.selectedTreeType !== 'file') return;
    if (e.key === 'F2') {
      e.preventDefault();
      window.ideRenameFile(state.selectedTreePath);
    } else if (e.key === 'Delete') {
      e.preventDefault();
      window.ideDeleteFile(state.selectedTreePath);
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
      e.preventDefault();
      state.fileClipboard = { mode: 'copy', path: state.selectedTreePath };
      outputLog(`Arquivo copiado: ${state.selectedTreePath}`);
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'x') {
      e.preventDefault();
      state.fileClipboard = { mode: 'cut', path: state.selectedTreePath };
      renderTree();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
      e.preventDefault();
      const dir = state.selectedTreePath.includes('/') ? state.selectedTreePath.split('/').slice(0, -1).join('/') : '';
      pasteClipboardFile(dir);
    }
  });

  // Navegação histórico de arquivos
  $('#ncs-nav-back')?.addEventListener('click', () => {
    if (state.navIndex > 0) {
      state.navIndex--;
      updateNavButtons();
      window.ideSelectTab(state.navHistory[state.navIndex], null, false);
    }
  });
  $('#ncs-nav-fwd')?.addEventListener('click', () => {
    if (state.navIndex < state.navHistory.length - 1) {
      state.navIndex++;
      updateNavButtons();
      window.ideSelectTab(state.navHistory[state.navIndex], null, false);
    }
  });

  // Activity bar tabs
  document.querySelectorAll('[data-side-tab]').forEach((btn) => {
    btn.onclick = () => {
      const sb = $('#ncs-sidebar');
      const isSame = btn.classList.contains('active') && sb.style.display !== 'none';
      if (isSame) {
        togglePrimarySidebar();
        return;
      }
      activateSidebarTab(btn.dataset.sideTab);
    };
  });

  // Accordions no Explorer
  document.querySelectorAll('[data-acc-target]').forEach((head) => {
    head.onclick = () => {
      const target = document.getElementById(head.dataset.accTarget);
      if (!target) return;
      const hidden = target.style.display === 'none';
      target.style.display = hidden ? 'block' : 'none';
      const chev = head.querySelector('.ncs-chevron');
      if (chev) chev.innerHTML = hidden ? '&#9662;' : '&#9656;';
    };
  });

  // Bottom panel tabs
  document.querySelectorAll('[data-panel-tab]').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('[data-panel-tab]').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.ncs-panel-view').forEach((v) => { v.style.display = 'none'; });
      btn.classList.add('active');
      const view = $(`#panel-view-${btn.dataset.panelTab}`);
      if (view) view.style.display = 'flex';
    };
  });

  // Toolbar & Action Buttons
  $('#ncs-new-file-btn')?.addEventListener('click', () => window.ideCreateNewFile());
  $('#ncs-new-folder-btn')?.addEventListener('click', () => window.ideCreateNewFolder());
  $('#ncs-collapse-all-btn')?.addEventListener('click', () => { state.expandedFolders.clear(); renderTree(); });
  $('#ncs-refresh-tree-btn')?.addEventListener('click', () => loadRepositoryTree(state.branch));

  $('#ncs-btn-commit')?.addEventListener('click', () => commitDirtyFiles());
  $('#ncs-git-commit-btn')?.addEventListener('click', () => commitDirtyFiles());
  $('#ncs-sync-btn')?.addEventListener('click', () => commitDirtyFiles());
  $('#ncs-commit-msg')?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      commitDirtyFiles();
    }
  });

  $('#ncs-btn-deploy')?.addEventListener('click', () => triggerDeploy('production'));
  $('#ncs-side-deploy-prod')?.addEventListener('click', () => triggerDeploy('production'));
  $('#ncs-side-deploy-prev')?.addEventListener('click', () => triggerDeploy('preview'));

  $('#ncs-golive-btn')?.addEventListener('click', () => window.ideTogglePreview());
  $('#ncs-run-preview-btn')?.addEventListener('click', () => window.ideTogglePreview(true));
  $('#ncs-tab-preview-btn')?.addEventListener('click', () => window.ideTogglePreview());
  $('#ncs-reload-preview')?.addEventListener('click', () => refreshLivePreview());
  $('#ncs-close-preview')?.addEventListener('click', () => window.ideTogglePreview(false));

  $('#ncs-btn-split')?.addEventListener('click', () => state.activePath && window.ideOpenSplit(state.activePath));
  $('#ncs-tab-split-btn')?.addEventListener('click', () => state.activePath && window.ideOpenSplit(state.activePath));
  $('#ncs-close-split-btn')?.addEventListener('click', () => { state.splitOpen = false; state.splitTabs = []; renderTabs(); });

  $('#ncs-tab-diff-btn')?.addEventListener('click', () => {
    state.diffMode = !state.diffMode;
    renderTabs();
    syncEditorView();
  });

  $('#ncs-layout-sidebar')?.addEventListener('click', togglePrimarySidebar);
  $('#ncs-layout-panel')?.addEventListener('click', toggleBottomPanel);
  $('#ncs-hide-terminal')?.addEventListener('click', toggleBottomPanel);
  $('#ncs-clear-terminal')?.addEventListener('click', () => { $('#ncs-terminal-out').innerHTML = ''; });

  $('#ncs-branch-btn')?.addEventListener('click', switchOrCreateBranch);
  $('#ncs-git-branch-btn')?.addEventListener('click', switchOrCreateBranch);
  $('#ncs-remote-btn')?.addEventListener('click', () => openQuickOpen('>'));

  // Welcome shortcuts
  $('#ncs-wel-newfile')?.addEventListener('click', () => window.ideCreateNewFile());
  $('#ncs-wel-quickopen')?.addEventListener('click', () => openQuickOpen(''));
  $('#ncs-wel-git')?.addEventListener('click', () => activateSidebarTab('git'));
  $('#ncs-wel-deploy')?.addEventListener('click', () => activateSidebarTab('deploys'));

  // Quick Open & Command Palette
  $('#ncs-quick-open-trigger')?.addEventListener('click', () => openQuickOpen(''));
  $('#ncs-cmd-palette-trigger')?.addEventListener('click', () => openQuickOpen('>'));
  $('#ncs-quickopen')?.addEventListener('click', (e) => { if (e.target.id === 'ncs-quickopen') $('#ncs-quickopen').style.display = 'none'; });
  $('#ncs-quickopen-input')?.addEventListener('input', (e) => renderQuickOpenList(e.target.value));
  $('#ncs-quickopen-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      qoSelectedIdx = Math.min(qoCurrentItems.length - 1, qoSelectedIdx + 1);
      $('#ncs-quickopen-list').querySelectorAll('.ncs-qo-item').forEach((el, i) => el.classList.toggle('selected', i === qoSelectedIdx));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      qoSelectedIdx = Math.max(0, qoSelectedIdx - 1);
      $('#ncs-quickopen-list').querySelectorAll('.ncs-qo-item').forEach((el, i) => el.classList.toggle('selected', i === qoSelectedIdx));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeQuickOpenItem(qoSelectedIdx);
    } else if (e.key === 'Escape') {
      $('#ncs-quickopen').style.display = 'none';
    }
  });

  // Search Pane
  let searchDebounce = null;
  $('#ncs-search-input')?.addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(runRepoSearch, 280);
  });
  $('#ncs-search-case')?.addEventListener('click', (e) => {
    state.searchCaseSensitive = !state.searchCaseSensitive;
    e.currentTarget.classList.toggle('active', state.searchCaseSensitive);
    runRepoSearch();
  });

  // Settings Pane
  $('#ncs-set-theme')?.addEventListener('change', (e) => {
    state.prefs.theme = e.target.value;
    if (monacoApi) monacoApi.editor.setTheme(state.prefs.theme);
  });
  $('#ncs-set-fontsize')?.addEventListener('change', (e) => {
    state.prefs.fontSize = Number(e.target.value) || 14;
    monacoEditor?.updateOptions({ fontSize: state.prefs.fontSize });
    monacoSplitEditor?.updateOptions({ fontSize: state.prefs.fontSize });
  });
  $('#ncs-set-tabsize')?.addEventListener('change', (e) => {
    state.prefs.tabSize = Number(e.target.value) || 2;
    $('#ncs-tab-info').textContent = `Espaços: ${state.prefs.tabSize}`;
    monacoEditor?.getModel()?.updateOptions({ tabSize: state.prefs.tabSize });
  });
  $('#ncs-set-minimap')?.addEventListener('change', (e) => {
    state.prefs.minimap = e.target.checked;
    monacoEditor?.updateOptions({ minimap: { enabled: state.prefs.minimap } });
  });
  $('#ncs-set-wordwrap')?.addEventListener('change', (e) => {
    state.prefs.wordWrap = e.target.checked ? 'on' : 'off';
    monacoEditor?.updateOptions({ wordWrap: state.prefs.wordWrap });
    monacoSplitEditor?.updateOptions({ wordWrap: state.prefs.wordWrap });
  });

  // Fallback Textarea bindings
  const ta = $('#ncs-textarea');
  const hl = $('#ncs-code-highlight');
  const gutter = $('#ncs-gutter');
  ta?.addEventListener('input', () => {
    const tab = state.openTabs.find((t) => t.path === state.activePath);
    if (!tab) return;
    tab.content = ta.value;
    tab.dirty = tab.content !== tab.originalContent;
    hl.innerHTML = fallbackHighlight(tab.content, tab.path);
    const linesCount = Math.max(1, tab.content.split('\n').length);
    gutter.innerHTML = Array.from({ length: linesCount }, (_, i) => i + 1).join('<br>');
    renderTabs();
  });
  ta?.addEventListener('scroll', () => {
    hl.scrollTop = ta.scrollTop;
    hl.scrollLeft = ta.scrollLeft;
    gutter.scrollTop = ta.scrollTop;
  });

  // Terminal input
  $('#ncs-term-input')?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      const cmd = e.target.value;
      e.target.value = '';
      await executeTerminalCommand(cmd);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (state.termHistIdx > 0) {
        state.termHistIdx--;
        e.target.value = state.termHistory[state.termHistIdx] || '';
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (state.termHistIdx < state.termHistory.length - 1) {
        state.termHistIdx++;
        e.target.value = state.termHistory[state.termHistIdx] || '';
      } else {
        state.termHistIdx = state.termHistory.length;
        e.target.value = '';
      }
    }
  });

  // Global keyboard shortcuts (VS Code Web)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllTopMenus();
      hideContextMenu();
      $('#ncs-quickopen').style.display = 'none';
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      commitDirtyFiles();
    } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'p') {
      e.preventDefault();
      openQuickOpen('>');
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p') {
      e.preventDefault();
      openQuickOpen('');
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      togglePrimarySidebar();
    } else if ((e.ctrlKey || e.metaKey) && e.key === '`') {
      e.preventDefault();
      toggleBottomPanel();
    } else if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
      e.preventDefault();
      if (state.activePath) window.ideOpenSplit(state.activePath);
    } else if (e.key === 'F1') {
      e.preventDefault();
      openQuickOpen('>');
    }
  });
}

(async function bootNexusCodeSpaces() {
  bindEvents();
  setupResizers();

  try {
    const me = await apiRequest('/auth/me');
    if (me?.perfil === 'cliente') {
      window.location.replace('./portal.html');
      return;
    }
    state.user = me;
    $('#ncs-account-btn').title = `${me.nome} (${me.email})`;
  } catch {
    window.location.href = '../login.html';
    return;
  }

  if (!projetoId) {
    termPrint('Erro: projeto_id não informado na URL.', '#f85149');
    return;
  }

  termPrint('Inicializando container Nexus CodeSpaces (VS Code Web Core)...', '#58a6ff');
  await initMonacoEditor();

  try {
    await loadRepositoryTree();
    termPrint(`✓ Repositório ${state.fullName} montado com sucesso na branch '${state.branch}'.`, '#3fb950');
    outputLog(`Workspace ${state.fullName} pronto.`);
  } catch (err) {
    termPrint(`[Erro ao conectar GitHub] ${err.message}`, '#f85149');
  }
})();
