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

## Passo a Passo para Publicar na Vercel + Neon

1. **Conectar o banco Neon ao projeto na Vercel:**
   - No painel da Vercel (aba *Storage* / *Neon*), clique em **Conecte-se ao Projeto** para vincular o banco `nexus_code_crm` ao seu projeto Vercel.
   - A Vercel criará automaticamente a variável `DATABASE_URL` no ambiente de produção.

2. **Configurar a chave JWT na Vercel:**
   - Em *Settings → Environment Variables*, adicione:
     - `SECRET_KEY`: uma sequência longa e aleatória (ex.: 64 caracteres).

3. **Fazer o Deploy:**
   - Envie os arquivos deste ZIP para o repositório GitHub conectado à Vercel (ou execute `npx vercel --prod`).
   - As tabelas e o usuário administrador inicial (`admin@nexuscode.com` / `Nexus@2026`) serão criados automaticamente no primeiro acesso.

## Execução Local (Mesmo Host)

```bash
pip install -r requirements.txt
uvicorn api.index:app --reload
```
Acesse `http://127.0.0.1:8000` (frontend e API `/api/*` rodando na mesma porta).
