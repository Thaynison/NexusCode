const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESC_MAP[c]);

const UI_ICONS = {
  danger: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>',
  warning: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
  primary: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
  error: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
  success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
  info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
  close: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
};

function ensureToastContainer() {
  let container = document.getElementById('nc-toast-stack');
  if (!container) {
    container = document.createElement('div');
    container.id = 'nc-toast-stack';
    container.className = 'nc-toast-stack';
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }
  return container;
}

export function showToast(message, type = 'success', duration = 3800) {
  const container = ensureToastContainer();
  const toast = document.createElement('div');
  toast.className = `nc-toast nc-toast-${type}`;
  const icon = type === 'error' ? UI_ICONS.error : type === 'info' ? UI_ICONS.info : UI_ICONS.success;

  toast.innerHTML = `
    <span class="nc-toast-icon">${icon}</span>
    <span class="nc-toast-msg">${esc(message)}</span>
    <button type="button" class="nc-toast-close" aria-label="Fechar notificação">${UI_ICONS.close}</button>
  `;

  const removeToast = () => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 220);
  };

  toast.querySelector('.nc-toast-close').onclick = removeToast;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

function ensureSystemDialog() {
  let dlg = document.getElementById('nc-system-dialog');
  if (!dlg) {
    dlg = document.createElement('dialog');
    dlg.id = 'nc-system-dialog';
    dlg.className = 'dialog nc-sys-dialog';
    document.body.appendChild(dlg);
  }
  return dlg;
}

export function showConfirmModal({
  title = 'Confirmar Ação',
  message = 'Deseja prosseguir com esta operação?',
  detail = '',
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  variant = 'danger',
  onConfirm = null
} = {}) {
  return new Promise((resolve) => {
    const dlg = ensureSystemDialog();
    const iconSvg = UI_ICONS[variant] || UI_ICONS.warning;
    const btnClass = variant === 'danger' ? 'btn danger' : 'btn';

    dlg.innerHTML = `
      <div class="modal nc-confirm-modal">
        <div class="nc-confirm-top">
          <div class="nc-confirm-badge ${esc(variant)}">${iconSvg}</div>
          <button type="button" class="btn secondary icon-only" data-sys-cancel aria-label="Fechar">${UI_ICONS.close}</button>
        </div>
        <h3 class="nc-confirm-title">${esc(title)}</h3>
        <p class="nc-confirm-msg">${esc(message)}</p>
        ${detail ? `<div class="nc-confirm-detail">${esc(detail)}</div>` : ''}
        <div id="nc-confirm-error" class="nc-inline-error" style="display:none;"></div>
        <div class="nc-confirm-actions">
          <button type="button" class="btn secondary" data-sys-cancel>${esc(cancelText)}</button>
          <button type="button" class="${btnClass}" data-sys-ok>${esc(confirmText)}</button>
        </div>
      </div>
    `;

    const cancelBtns = dlg.querySelectorAll('[data-sys-cancel]');
    const okBtn = dlg.querySelector('[data-sys-ok]');
    const errBox = dlg.querySelector('#nc-confirm-error');

    const cleanupAndResolve = (val) => {
      if (dlg.open) dlg.close();
      resolve(val);
    };

    cancelBtns.forEach((b) => {
      b.onclick = () => cleanupAndResolve(false);
    });

    dlg.oncancel = (e) => {
      e.preventDefault();
      cleanupAndResolve(false);
    };

    dlg.onclick = (e) => {
      if (e.target === dlg && !okBtn.disabled) {
        cleanupAndResolve(false);
      }
    };

    okBtn.onclick = async () => {
      if (!onConfirm) {
        cleanupAndResolve(true);
        return;
      }
      const prevLabel = okBtn.textContent;
      okBtn.disabled = true;
      cancelBtns.forEach((b) => (b.disabled = true));
      okBtn.textContent = 'Processando...';
      errBox.style.display = 'none';

      try {
        await onConfirm();
        cleanupAndResolve(true);
      } catch (err) {
        errBox.textContent = err?.message || 'Não foi possível concluir a operação.';
        errBox.style.display = 'block';
        okBtn.disabled = false;
        cancelBtns.forEach((b) => (b.disabled = false));
        okBtn.textContent = prevLabel;
      }
    };

    dlg.showModal();
    okBtn.focus();
  });
}

export function showNoticeModal({
  title = 'Aviso do Sistema',
  message = '',
  detail = '',
  buttonText = 'Entendi',
  variant = 'error'
} = {}) {
  return new Promise((resolve) => {
    const dlg = ensureSystemDialog();
    const iconSvg = UI_ICONS[variant] || UI_ICONS.info;

    dlg.innerHTML = `
      <div class="modal nc-confirm-modal">
        <div class="nc-confirm-top">
          <div class="nc-confirm-badge ${esc(variant)}">${iconSvg}</div>
          <button type="button" class="btn secondary icon-only" data-sys-close aria-label="Fechar">${UI_ICONS.close}</button>
        </div>
        <h3 class="nc-confirm-title">${esc(title)}</h3>
        <p class="nc-confirm-msg">${esc(message)}</p>
        ${detail ? `<div class="nc-confirm-detail">${esc(detail)}</div>` : ''}
        <div class="nc-confirm-actions">
          <button type="button" class="btn" data-sys-close>${esc(buttonText)}</button>
        </div>
      </div>
    `;

    const closeBtns = dlg.querySelectorAll('[data-sys-close]');
    const finish = () => {
      if (dlg.open) dlg.close();
      resolve();
    };

    closeBtns.forEach((b) => (b.onclick = finish));
    dlg.oncancel = (e) => {
      e.preventDefault();
      finish();
    };
    dlg.onclick = (e) => {
      if (e.target === dlg) finish();
    };

    dlg.showModal();
    closeBtns[closeBtns.length - 1]?.focus();
  });
}
