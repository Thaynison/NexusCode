# Nexus Code — Plataforma Institucional & Gestão Empresarial (Vercel + Neon)

Arquitetura unificada em **mesmo host** para deploy em produção na **Vercel** com banco de dados **Neon (PostgreSQL Serverless)**.

## Estrutura do Projeto

- `index.html` — Site institucional, portfólio, loja e formulário comercial integrado.
- `login.html` — Autenticação corporativa (administradores, equipe e clientes).
- `app/index.html` — Painel administrativo e atendimento comercial.
- `app/portal.html` — Portal do cliente (acompanhamento de solicitações, projetos e faturas).
- `api/index.py` — Função Serverless Python (FastAPI) roteada em `/api/*`.
- `backend/` — Modelos SQLAlchemy, schemas Pydantic, autenticação JWT/Bcrypt e regras de negócio.
- `vercel.json` — Roteamento unificado `/api/(.*)` -> `/api/index.py`.
- `requirements.txt` — Dependências Python para build automático na Vercel.
- `.env.example` — Modelo das variáveis de ambiente necessárias.

## Passo a Passo para Publicar na Vercel + Neon

1. **Conectar o banco Neon ao projeto na Vercel:**
   - No painel da Vercel (aba *Storage* / *Neon*), conecte o banco `nexus_code_crm` ao projeto para criar automaticamente `DATABASE_URL`.

2. **Configurar as Variáveis de Ambiente na Vercel (Obrigatório):**
   - Acesse **Vercel → Seu Projeto → Settings → Environment Variables**.
   - Adicione (ou cole no formato `.env`) as 4 chaves abaixo marcando **Production**, **Preview** e **Development**:
     - `SECRET_KEY` (Chave de assinatura dos tokens JWT de login)
     - `MP_WEBHOOK_SECRET` (Assinatura secreta HMAC do Webhook do Mercado Pago)
     - `WEBHOOK_SECRET` (Token secreto para baixa automática via `/api/webhook/pagamento`)
     - `CRON_SECRET` (Token secreto de autenticação da rotina diária `/api/cron/verificar-vencimentos`)
   - **Importante:** Após salvar as variáveis, vá em **Deployments → ⋮ → Redeploy** para aplicar as variáveis ao build em produção.

3. **Verificar Saúde e Variáveis Ativas:**
   - Acesse `https://seu-dominio.vercel.app/api/health` para confirmar que `secret_key_configurada`, `mp_webhook_secret_configurado`, `webhook_secret_configurado` e `cron_secret_configurado` retornam `true`.

## Execução Local (Mesmo Host)

```bash
pip install -r requirements.txt
uvicorn api.index:app --reload
```
Acesse `http://127.0.0.1:8000` (frontend e API `/api/*` rodando na mesma porta).
