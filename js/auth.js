import { apiRequest, setSession, getToken } from '../assets/js/config.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const authForm = $('#auth-form');
const authStatus = $('#auth-status');

// Pré-aquece a Serverless Function na Vercel (gru1) enquanto o usuário digita
fetch('/api/health').catch(() => {});

if (getToken()) {
  apiRequest('/auth/me')
    .then((u) => {
      window.location.href = u.perfil === 'cliente' ? 'app/portal.html' : 'app/index.html';
    })
    .catch(() => localStorage.removeItem('nexus_token'));
}

if (authForm) {
  function switchAuthMode(mode) {
    authForm.mode.value = mode;
    $$('[data-auth-tab]').forEach((btn) => {
      if (btn.classList.contains('nc-tab')) {
        btn.classList.toggle('active', btn.dataset.authTab === mode);
      }
    });

    const titles = {
      login: ['Acesso à Plataforma', 'Insira suas credenciais para continuar', 'Acessar Plataforma'],
      register: ['Cadastro de Cliente', 'Crie sua conta para acompanhar projetos e solicitações', 'Concluir Cadastro'],
      forgot: ['Recuperação de Senha', 'Informe seu e-mail cadastrado para receber as instruções de acesso', 'Enviar Instruções'],
      reset: ['Definir Nova Senha', 'Informe sua nova senha de acesso abaixo', 'Salvar Nova Senha']
    };

    $('#auth-title').textContent = titles[mode][0];
    $('#auth-subtitle').textContent = titles[mode][1];
    $('#auth-submit-btn span').textContent = titles[mode][2];

    if (mode === 'register') {
      $('#auth-extra').innerHTML = `<div class="nc-field">
          <label for="auth-name">Nome completo</label>
          <div class="nc-input-wrap">
            <svg class="nc-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            <input id="auth-name" name="displayName" type="text" placeholder="Seu nome completo" required>
          </div>
        </div>
        <label style="display:flex; align-items:flex-start; gap:8px; font-size:12px; color:#475569; margin-top:10px; cursor:pointer; line-height:1.45;">
          <input type="checkbox" name="lgpdConsent" required style="margin-top:2px; accent-color:#0096B4;">
          <span>Li e concordo com o tratamento dos meus dados pessoais conforme a <b>LGPD (Lei nº 13.709/2018)</b>.</span>
        </label>`;
    } else {
      $('#auth-extra').innerHTML = '';
    }

    const emailField = $('#auth-username')?.closest('.nc-field');
    if (emailField) {
      emailField.style.display = mode === 'reset' ? 'none' : 'flex';
      authForm.username.required = mode !== 'reset';
    }

    $('#password-wrap').style.display = mode === 'forgot' ? 'none' : 'flex';
    authForm.password.required = mode !== 'forgot';
    authStatus.className = 'nc-auth-status';
    authStatus.textContent = '';
  }

  $$('[data-auth-tab]').forEach((b) => (b.onclick = () => switchAuthMode(b.dataset.authTab)));

  const urlParams = new URLSearchParams(window.location.search);
  const resetToken = urlParams.get('reset_token');
  if (resetToken) {
    switchAuthMode('reset');
  }

  $('#toggle-password')?.addEventListener('click', () => {
    const pwd = $('#auth-password');
    const isHidden = pwd.type === 'password';
    pwd.type = isHidden ? 'text' : 'password';
    const eye = $('#eye-icon');
    if (eye) {
      eye.innerHTML = isHidden
        ? '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path><line x1="2" y1="2" x2="22" y2="22"></line>'
        : '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle>';
    }
  });

  authForm.onsubmit = async (e) => {
    e.preventDefault();
    const mode = authForm.mode.value;
    const btn = $('#auth-submit-btn');
    const labelSpan = btn.querySelector('span');
    const prevText = labelSpan.textContent;

    btn.disabled = true;
    labelSpan.textContent = 'Autenticando...';
    authStatus.className = 'nc-auth-status';
    authStatus.textContent = '';

    try {
      const raw = Object.fromEntries(new FormData(authForm));

      if (mode === 'forgot') {
        const res = await apiRequest('/auth/forgot-password', {
          method: 'POST',
          body: JSON.stringify({ email: raw.username })
        });
        authStatus.className = 'nc-auth-status success';
        authStatus.textContent = res.message;
        return;
      }

      if (mode === 'reset') {
        const res = await apiRequest('/auth/reset-password', {
          method: 'POST',
          body: JSON.stringify({ token: resetToken, nova_senha: raw.password })
        });
        authStatus.className = 'nc-auth-status success';
        authStatus.textContent = res.message;
        setTimeout(() => { window.location.href = 'login.html'; }, 1600);
        return;
      }

      const endpoint = mode === 'register' ? '/auth/register' : '/auth/login';
      const payload = mode === 'register'
        ? { nome: raw.displayName, email: raw.username, senha: raw.password }
        : { email: raw.username, senha: raw.password };

      const data = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setSession(data.access_token, data.usuario);
      window.location.href = data.usuario.perfil === 'cliente' ? 'app/portal.html' : 'app/index.html';
    } catch (err) {
      authStatus.className = 'nc-auth-status error';
      authStatus.textContent = err.message;
    } finally {
      btn.disabled = false;
      labelSpan.textContent = prevText;
    }
  };
}
