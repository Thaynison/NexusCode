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


// ==================== SMART TABBED MODAL ENGINE (ZERO SCROLLBAR & NO LOOP) ====================
function isSectionHidden(card) {
  if (!card) return true;
  if (card.dataset.modalHidden === 'true' || card.hasAttribute('hidden')) return true;
  if (card.style && card.style.display === 'none' && !card.hasAttribute('data-tab-panel')) return true;
  let cur = card.parentElement;
  while (cur && cur !== document.body) {
    if (cur.dataset?.modalHidden === 'true' || cur.hasAttribute?.('hidden')) return true;
    if (cur.style && cur.style.display === 'none') return true;
    cur = cur.parentElement;
  }
  return false;
}

function cleanStepTitle(rawText, index) {
  let txt = String(rawText || '').replace(/^\d+\s*/, '').trim();
  txt = txt.replace(/\s*\([^)]*\)/g, '').trim();
  if (txt.length > 28) {
    const shortPart = txt.split(/[&—-]/)[0].trim();
    if (shortPart.length >= 4) txt = shortPart;
  }
  return txt || `Etapa ${index + 1}`;
}

export function enhanceModalLayout(dialogEl) {
  if (!dialogEl) return;

  // Fechar ao clicar fora
  if (!dialogEl.dataset.backdropBound) {
    dialogEl.dataset.backdropBound = '1';
    dialogEl.addEventListener('click', (e) => {
      if (e.target === dialogEl && dialogEl.id !== 'nc-system-dialog') {
        dialogEl.close();
      }
    });
  }

  const modalRoot = dialogEl.querySelector('.modal');
  const bodyEl = dialogEl.querySelector('.modal-body');
  if (!modalRoot || !bodyEl) return;

  // Cleanup prev nav
  const oldNavs = modalRoot.querySelectorAll('.modal-tabs');
  oldNavs.forEach(n => n.remove());
  modalRoot.querySelectorAll('.modal-step-nav-btn').forEach(n => n.remove());
  modalRoot.classList.remove('modal-tabbed');

  const allCards = [...bodyEl.querySelectorAll('.modal-section-card')];
  const visibleCards = allCards.filter(c => !isSectionHidden(c));

  if (visibleCards.length < 2) {
    allCards.forEach((c) => {
      if (c.hasAttribute('data-tab-panel')) {
        c.style.removeProperty('display');
        c.removeAttribute('data-tab-panel');
      }
    });
    return;
  }

  modalRoot.classList.add('modal-tabbed');

  const nav = document.createElement('nav');
  nav.className = 'modal-tabs';
  nav.setAttribute('role', 'tablist');

  let activeIdx = 0;
  const footerEl = modalRoot.querySelector('.modal-footer');
  let prevBtn = null;
  let nextBtn = null;

  if (footerEl) {
    const targetWrap = footerEl.querySelector('.modal-footer-right') || footerEl;
    prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = 'btn secondary modal-step-nav-btn';
    prevBtn.textContent = '← Anterior';

    nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'btn secondary modal-step-nav-btn';
    nextBtn.textContent = 'Próximo →';

    const submitBtn = targetWrap.querySelector('button[type="submit"]');
    if (submitBtn) {
      targetWrap.insertBefore(prevBtn, submitBtn);
      targetWrap.insertBefore(nextBtn, submitBtn);
    } else {
      targetWrap.prepend(nextBtn);
      targetWrap.prepend(prevBtn);
    }
  }

  const activateTab = (idx) => {
    activeIdx = Math.max(0, Math.min(visibleCards.length - 1, idx));
    visibleCards.forEach((card, i) => {
      if (i === activeIdx) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
      card.setAttribute('data-tab-panel', String(i));
    });
    
    nav.querySelectorAll('.modal-tab-btn').forEach((btn, i) => {
      const isAct = i === activeIdx;
      if (isAct) {
         btn.classList.add('active');
         btn.setAttribute('aria-selected', 'true');
      } else {
         btn.classList.remove('active');
         btn.setAttribute('aria-selected', 'false');
      }
    });
    
    if (prevBtn) prevBtn.style.display = activeIdx > 0 ? 'inline-flex' : 'none';
    if (nextBtn) nextBtn.style.display = activeIdx < visibleCards.length - 1 ? 'inline-flex' : 'none';
    
    // Evitar o pulo ao topo, apenas reseta se houver scroll interno no modal-body
    if(bodyEl.scrollTop > 0) bodyEl.scrollTop = 0;
  };

  visibleCards.forEach((card, i) => {
    const titleEl = card.querySelector('.modal-section-title');
    const stepEl = titleEl?.querySelector('.modal-section-step');
    const stepNum = stepEl ? stepEl.textContent.trim() : String(i + 1);
    const labelText = cleanStepTitle(titleEl ? titleEl.textContent : '', i);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'modal-tab-btn';
    btn.setAttribute('role', 'tab');
    btn.innerHTML = `<span class="modal-tab-step">${esc(stepNum)}</span><span>${esc(labelText)}</span>`;
    
    // Bind click without causing event bubbling issues
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      activateTab(i);
    });
    nav.appendChild(btn);
  });

  if (prevBtn) prevBtn.addEventListener('click', () => activateTab(activeIdx - 1));
  if (nextBtn) nextBtn.addEventListener('click', () => activateTab(activeIdx + 1));

  bodyEl.parentElement.insertBefore(nav, bodyEl);
  
  // Set initial tab explicitly
  activateTab(0);

  // Validação HTML5
  const formEl = modalRoot.matches('form') ? modalRoot : modalRoot.querySelector('form');
  if (formEl && !formEl.dataset.tabInvalidBound) {
    formEl.dataset.tabInvalidBound = '1';
    formEl.addEventListener('invalid', (ev) => {
      const target = ev.target;
      const panel = target?.closest?.('[data-tab-panel]');
      if (panel) {
        const panelIdx = Number(panel.getAttribute('data-tab-panel'));
        if (!Number.isNaN(panelIdx)) {
          activateTab(panelIdx);
          const tabsNav = modalRoot.querySelector('.modal-tabs');
          if (tabsNav) {
             const tabBtns = [...tabsNav.querySelectorAll('.modal-tab-btn')];
             if (tabBtns[panelIdx]) tabBtns[panelIdx].classList.add('has-error');
          }
          setTimeout(() => target.focus?.(), 50);
        }
      }
    }, true);
  }
}

export function initGlobalModalEnhancer() {
  if (typeof document === 'undefined') return;
  const setupDialogs = () => {
    document.querySelectorAll('dialog.dialog:not(#nc-system-dialog)').forEach((dlg) => {
      // Monitor directly the #dynamic-record-fields or modal body instead of the dialog
      // to avoid infinite loops when we inject the nav outside the body
      const observeTarget = dlg.querySelector('#dynamic-record-fields') || dlg.querySelector('.modal-body') || dlg;
      if (observeTarget.dataset.observerAttached) return;
      observeTarget.dataset.observerAttached = '1';
      
      let timer = null;
      const obs = new MutationObserver((mutations) => {
        // Ignorar se a mutação foi a própria injeção do display:none nas tabs
        const isSafe = mutations.some(m => m.type === 'childList' && Array.from(m.addedNodes).some(n => n.classList && n.classList.contains('modal-section-card')));
        if(isSafe || (mutations.length > 0 && !mutations[0].target.classList.contains('modal-body'))) {
           clearTimeout(timer);
           timer = setTimeout(() => enhanceModalLayout(dlg), 50);
        }
      });
      obs.observe(observeTarget, { childList: true });
      enhanceModalLayout(dlg);
    });
  };
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupDialogs);
  } else {
    setupDialogs();
  }
}

initGlobalModalEnhancer();
