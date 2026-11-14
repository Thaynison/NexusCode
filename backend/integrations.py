import unicodedata
import base64
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_TLD_PRICING: Dict[str, Dict[str, Any]] = {
    ".com.br": {"label": "Nacional Brasil (.com.br)", "custo": 40.00, "venda": 79.90, "destaque": True, "ativo": True},
    ".com": {"label": "Global Comercial (.com)", "custo": 58.00, "venda": 109.90, "destaque": True, "ativo": True},
    ".net": {"label": "Infraestrutura & Rede (.net)", "custo": 64.00, "venda": 119.90, "destaque": False, "ativo": True},
    ".org": {"label": "Organizações (.org)", "custo": 62.00, "venda": 114.90, "destaque": False, "ativo": True},
    ".tech": {"label": "Tecnologia & Startups (.tech)", "custo": 45.00, "venda": 99.90, "destaque": True, "ativo": True},
    ".online": {"label": "Presença Digital (.online)", "custo": 25.00, "venda": 69.90, "destaque": False, "ativo": True},
    ".app": {"label": "Aplicativos & SaaS (.app)", "custo": 78.00, "venda": 139.90, "destaque": False, "ativo": True},
    ".io": {"label": "Tech & Sistemas (.io)", "custo": 195.00, "venda": 299.90, "destaque": False, "ativo": True},
}

RDAP_SERVERS: Dict[str, str] = {
    ".br": "https://rdap.registro.br/domain/{domain}",
    ".com.br": "https://rdap.registro.br/domain/{domain}",
    ".net.br": "https://rdap.registro.br/domain/{domain}",
    ".org.br": "https://rdap.registro.br/domain/{domain}",
    ".com": "https://rdap.verisign.com/com/v1/domain/{domain}",
    ".net": "https://rdap.verisign.com/net/v1/domain/{domain}",
    ".org": "https://rdap.publicinterestregistry.org/rdap/domain/{domain}",
    ".tech": "https://rdap.nic.tech/domain/{domain}",
    ".online": "https://rdap.nic.online/domain/{domain}",
    ".app": "https://rdap.nic.google/domain/{domain}",
    ".dev": "https://rdap.nic.google/domain/{domain}",
    ".io": "https://rdap.nic.io/domain/{domain}",
}


def get_tld_pricing(raw_json: Optional[str]) -> Dict[str, Dict[str, Any]]:
    pricing = {k: dict(v) for k, v in DEFAULT_TLD_PRICING.items()}
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                for ext, info in parsed.items():
                    if isinstance(info, dict):
                        base = pricing.get(ext, {"label": ext, "custo": 50.0, "venda": 99.9, "destaque": False, "ativo": True})
                        base.update(info)
                        pricing[ext] = base
        except Exception:
            pass
    return pricing


def normalizar_dominio_busca(query: str, default_ext: str = ".com.br") -> Tuple[str, str, str]:
    """Retorna (dominio_completo, sld_sem_extensao, extensao)."""
    q = (query or "").strip().lower()
    q = re.sub(r"^https?://", "", q)
    q = re.sub(r"^www\.", "", q)
    q = q.split("/")[0].split("?")[0].split(":")[0].strip().rstrip(".")
    q = re.sub(r"[^a-z0-9.-]", "", q)
    if not q:
        raise ValueError("Informe um nome de domínio válido para pesquisar.")

    known_exts = sorted(DEFAULT_TLD_PRICING.keys(), key=len, reverse=True)
    for ext in known_exts:
        if q.endswith(ext) and len(q) > len(ext):
            sld = q[: -len(ext)].strip(".")
            sld = re.sub(r"[^a-z0-9-]", "", sld).strip("-")
            if len(sld) < 2:
                raise ValueError("O nome do domínio deve ter ao menos 2 caracteres.")
            return f"{sld}{ext}", sld, ext

    if "." in q:
        parts = q.split(".", 1)
        sld = re.sub(r"[^a-z0-9-]", "", parts[0]).strip("-")
        ext = "." + parts[1].strip(".")
        if len(sld) < 2 or len(ext) < 3:
            raise ValueError("Formato de domínio inválido.")
        return f"{sld}{ext}", sld, ext

    sld = re.sub(r"[^a-z0-9-]", "", q).strip("-")
    if len(sld) < 2:
        raise ValueError("O nome do domínio deve ter ao menos 2 caracteres.")
    ext = default_ext if default_ext.startswith(".") else f".{default_ext}"
    return f"{sld}{ext}", sld, ext


def _http_json_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 12,
) -> Tuple[int, Dict[str, Any]]:
    req_headers = {"Accept": "application/json", "User-Agent": "NexusCodeEnterprise/2.4"}
    if headers:
        req_headers.update(headers)
    data_bytes = None
    if payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return status, json.loads(raw) if raw else {}
            except Exception:
                return status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw else {"error": str(e)}
        except Exception:
            return e.code, {"error": raw or str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def consultar_rdap_unico(domain: str) -> Dict[str, Any]:
    """Consulta disponibilidade real via protocolo oficial RDAP (Registro.br / Verisign / ICANN)."""
    ext = "." + domain.split(".", 1)[1] if "." in domain else ".com"
    template = RDAP_SERVERS.get(ext, "https://rdap.org/domain/{domain}")
    url = template.format(domain=urllib.parse.quote(domain))
    status, data = _http_json_request(url, method="GET", timeout=8)

    if status == 404:
        return {"dominio": domain, "disponivel": True, "status_rdap": "livre", "detalhe": "Disponível para registro imediato"}
    if status == 200:
        expira = None
        for ev in data.get("events", []) if isinstance(data.get("events"), list) else []:
            if ev.get("eventAction") == "expiration":
                expira = str(ev.get("eventDate", ""))[:10]
                break
        return {
            "dominio": domain,
            "disponivel": False,
            "status_rdap": "registrado",
            "detalhe": f"Já registrado{f' (expira em {expira})' if expira else ''}",
        }
    return {
        "dominio": domain,
        "disponivel": False,
        "status_rdap": "indeterminado",
        "detalhe": "Não foi possível consultar o servidor RDAP neste instante",
    }


def pesquisar_dominios_com_sugestoes(query: str, pricing_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    primary_domain, sld, primary_ext = normalizar_dominio_busca(query)
    active_exts = [ext for ext, cfg in pricing_map.items() if cfg.get("ativo", True)]
    if primary_ext not in active_exts:
        active_exts.insert(0, primary_ext)

    ordered_exts = [primary_ext] + [e for e in active_exts if e != primary_ext][:5]
    resultados: List[Dict[str, Any]] = []

    for ext in ordered_exts:
        dom = f"{sld}{ext}"
        price_info = pricing_map.get(ext, {"label": ext, "custo": 50.0, "venda": 99.9, "destaque": False})
        rdap = consultar_rdap_unico(dom)
        resultados.append({
            "dominio": dom,
            "sld": sld,
            "extensao": ext,
            "label": price_info.get("label", ext),
            "disponivel": rdap["disponivel"],
            "status_rdap": rdap["status_rdap"],
            "detalhe": rdap["detalhe"],
            "preco_anual": float(price_info.get("venda", 99.90)),
            "destaque": bool(price_info.get("destaque", False)),
            "principal": dom == primary_domain,
        })

    principal = resultados[0] if resultados else None
    return {
        "termo": query,
        "principal": principal,
        "resultados": resultados,
    }


# ==================== MERCADO PAGO ENGINE ====================

def _mp_headers(access_token: str, idempotency_key: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        h["X-Idempotency-Key"] = idempotency_key
    return h


def mp_criar_pagamento_pix(
    access_token: str,
    valor: float,
    descricao: str,
    external_reference: str,
    pagador_email: str,
    pagador_nome: str = "Cliente",
    notification_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Cria uma cobrança PIX instantânea via API oficial do Mercado Pago (/v1/payments)."""
    if not access_token or not access_token.strip():
        raise ValueError("Access Token do Mercado Pago não configurado em Empresa & Permissões > Integrações.")

    parts = (pagador_nome or "Cliente Nexus").strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "Cliente"

    body: Dict[str, Any] = {
        "transaction_amount": round(float(valor), 2),
        "description": descricao[:250],
        "payment_method_id": "pix",
        "external_reference": external_reference,
        "payer": {
            "email": pagador_email or "financeiro@nexuscodebrasil.com.br",
            "first_name": first_name[:60],
            "last_name": last_name[:60],
        },
    }
    if notification_url and notification_url.startswith("https://"):
        body["notification_url"] = notification_url

    idem = f"nc-pix-{external_reference}-{uuid.uuid4().hex[:10]}"
    status, data = _http_json_request(
        "https://api.mercadopago.com/v1/payments",
        method="POST",
        headers=_mp_headers(access_token, idem),
        payload=body,
        timeout=15,
    )
    if status not in (200, 201):
        msg = data.get("message") or data.get("error") or "Falha ao gerar cobrança PIX no Mercado Pago."
        raise RuntimeError(f"Mercado Pago ({status}): {msg}")

    tx = data.get("point_of_interaction", {}).get("transaction_data", {})
    return {
        "payment_id": str(data.get("id")),
        "status": data.get("status", "pending"),
        "status_detail": data.get("status_detail", ""),
        "qr_code": tx.get("qr_code", ""),
        "qr_code_base64": tx.get("qr_code_base64", ""),
        "ticket_url": tx.get("ticket_url", ""),
    }


def mp_criar_checkout_pro(
    access_token: str,
    titulo: str,
    valor: float,
    external_reference: str,
    pagador_email: str,
    back_url_base: str,
    notification_url: Optional[str] = None,
    ambiente: Optional[str] = None,
) -> Dict[str, Any]:
    """Cria preferência Checkout Pro (Cartão de Crédito, Débito, PIX e Boleto)."""
    if not access_token or not access_token.strip():
        raise ValueError("Access Token do Mercado Pago não configurado em Empresa & Permissões > Integrações.")

    is_legacy_test = access_token.strip().startswith("TEST-")
    is_sandbox = is_legacy_test or (ambiente or "").strip().lower() == "sandbox"
    payer_mail = (pagador_email or "").strip()

    clean_base = back_url_base.rstrip("/")
    body: Dict[str, Any] = {
        "items": [
            {
                "title": titulo[:250],
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": round(float(valor), 2),
            }
        ],
        "external_reference": external_reference,
        "back_urls": {
            "success": f"{clean_base}?mp_status=approved&ref={urllib.parse.quote(external_reference)}",
            "pending": f"{clean_base}?mp_status=pending&ref={urllib.parse.quote(external_reference)}",
            "failure": f"{clean_base}?mp_status=failure&ref={urllib.parse.quote(external_reference)}",
        },
        "auto_return": "approved",
    }
    if payer_mail and not is_sandbox:
        body["payer"] = {"email": payer_mail}
    if notification_url and notification_url.startswith("https://"):
        body["notification_url"] = notification_url

    status, data = _http_json_request(
        "https://api.mercadopago.com/checkout/preferences",
        method="POST",
        headers=_mp_headers(access_token),
        payload=body,
        timeout=15,
    )
    if status not in (200, 201):
        msg = data.get("message") or data.get("error") or "Falha ao criar Checkout Pro no Mercado Pago."
        raise RuntimeError(f"Mercado Pago Checkout ({status}): {msg}")

    live_url = data.get("init_point") or ""
    sbx_url = data.get("sandbox_init_point") or live_url
    # Credenciais APP_USR (Produção ou Teste) utilizam sempre init_point; sandbox_init_point aplica-se apenas a tokens legados TEST-
    chosen_url = sbx_url if is_legacy_test else (live_url or sbx_url)

    return {
        "preference_id": str(data.get("id")),
        "init_point": chosen_url,
        "sandbox_init_point": sbx_url,
    }



def mp_criar_order_pix(
    access_token: str,
    valor: float,
    descricao: str,
    external_reference: str,
    pagador_email: str,
    pagador_nome: str = "Cliente",
) -> Dict[str, Any]:
    """
    Cria uma Order online com pagamento PIX via nova API de Orders do Mercado Pago (POST /v1/orders).
    """
    if not access_token or not access_token.strip():
        raise ValueError("Access Token do Mercado Pago não configurado em Empresa & Permissões > Integrações.")

    clean_ref = re.sub(r"[^a-zA-Z0-9_-]", "-", str(external_reference or "ORD")).strip("-")[:64] or "ORD"
    clean_desc = re.sub(r"[\r\n\t]+", " ", str(descricao or "Pagamento Nexus Code")).strip()[:150]
    clean_name = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ\s]", "", str(pagador_nome or "Cliente Nexus")).strip()
    parts = (clean_name or "Cliente Nexus").split(" ", 1)
    first_name = parts[0][:50] or "Cliente"
    last_name = (parts[1] if len(parts) > 1 else "Nexus")[:50] or "Nexus"
    amount_str = f"{round(float(valor), 2):.2f}"

    body: Dict[str, Any] = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": amount_str,
        "external_reference": clean_ref,
        "description": clean_desc,
        "payer": {
            "email": (pagador_email or "financeiro@nexuscodebrasil.com.br").strip(),
            "first_name": first_name,
            "last_name": last_name,
        },
        "transactions": {
            "payments": [
                {
                    "amount": amount_str,
                    "payment_method": {
                        "id": "pix",
                        "type": "bank_transfer",
                    },
                }
            ]
        },
    }

    idem = f"nc-ord-{clean_ref}-{uuid.uuid4().hex[:10]}"
    status, data = _http_json_request(
        "https://api.mercadopago.com/v1/orders",
        method="POST",
        headers=_mp_headers(access_token, idem),
        payload=body,
        timeout=15,
    )
    if status not in (200, 201):
        err_list = data.get("errors") if isinstance(data.get("errors"), list) else []
        if err_list and isinstance(err_list[0], dict):
            e0 = err_list[0]
            extra = ", ".join(str(x) for x in (e0.get("details") or [])) if isinstance(e0.get("details"), list) else str(e0.get("details") or e0.get("property") or "")
            msg0 = e0.get("message") or "Erro de validação"
            detail = f"{msg0} ({extra})" if extra else msg0
        else:
            detail = data.get("message") or data.get("error") or "Falha ao criar Order PIX."
        raise RuntimeError(f"Mercado Pago Orders ({status}): {detail}")

    order_id = str(data.get("id") or "")
    payments_arr = (data.get("transactions") or {}).get("payments") or []
    pay0 = payments_arr[0] if payments_arr and isinstance(payments_arr[0], dict) else {}
    payment_id = str(pay0.get("id") or "")
    pm_obj = pay0.get("payment_method") if isinstance(pay0.get("payment_method"), dict) else {}
    poi_tx = ((pay0.get("point_of_interaction") or {}).get("transaction_data") or {})

    qr_code = pm_obj.get("qr_code") or poi_tx.get("qr_code") or ""
    qr_code_base64 = pm_obj.get("qr_code_base64") or poi_tx.get("qr_code_base64") or ""
    ticket_url = pm_obj.get("ticket_url") or pay0.get("ticket_url") or poi_tx.get("ticket_url") or ""

    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "status": data.get("status", "action_required"),
        "status_detail": data.get("status_detail", ""),
        "qr_code": qr_code,
        "qr_code_base64": qr_code_base64,
        "ticket_url": ticket_url,
    }


def mp_consultar_order(access_token: str, order_id: str) -> Dict[str, Any]:
    """Consulta uma Order na nova API do Mercado Pago (GET /v1/orders/{id})."""
    if not access_token or not order_id:
        return {"status": "unknown"}
    status, data = _http_json_request(
        f"https://api.mercadopago.com/v1/orders/{urllib.parse.quote(str(order_id))}",
        method="GET",
        headers=_mp_headers(access_token),
        timeout=12,
    )
    if status != 200:
        return {"status": "error", "http_status": status, "detail": data.get("message", "")}

    raw_status = str(data.get("status") or "").lower()
    payments_arr = (data.get("transactions") or {}).get("payments") or []
    pay0 = payments_arr[0] if payments_arr and isinstance(payments_arr[0], dict) else {}
    pay_status = str(pay0.get("status") or "").lower()

    pm_obj = pay0.get("payment_method") if isinstance(pay0.get("payment_method"), dict) else {}
    poi_tx = ((pay0.get("point_of_interaction") or {}).get("transaction_data") or {})
    tx_det = pay0.get("transaction_details") if isinstance(pay0.get("transaction_details"), dict) else {}

    is_paid = raw_status in ("processed", "approved") or pay_status in ("processed", "approved")
    return {
        "order_id": str(data.get("id") or order_id),
        "payment_id": str(pay0.get("id") or ""),
        "status": "approved" if is_paid else raw_status,
        "status_detail": data.get("status_detail") or pay0.get("status_detail") or "",
        "external_reference": data.get("external_reference", ""),
        "transaction_amount": data.get("total_amount", 0),
        "payment_method_id": pm_obj.get("id") or "",
        "payment_type_id": pm_obj.get("type") or "",
        "installments": pm_obj.get("installments") or 1,
        "end_to_end_id": poi_tx.get("e2e_id") or tx_det.get("transaction_id") or "",
        "ticket_url": pm_obj.get("ticket_url") or pay0.get("ticket_url") or poi_tx.get("ticket_url") or "",
        "date_approved": pay0.get("date_approved") or data.get("last_updated_date") or "",
    }


def mp_criar_cobranca_pix_unificada(
    access_token: str,
    api_tipo: Optional[str],
    valor: float,
    descricao: str,
    external_reference: str,
    pagador_email: str,
    pagador_nome: str = "Cliente",
    notification_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gera cobrança PIX usando a nova API de Orders (/v1/orders) como padrão,
    com suporte completo à API de Payments (/v1/payments).
    """
    modo = (api_tipo or "orders").strip().lower()
    if modo == "orders":
        try:
            res = mp_criar_order_pix(
                access_token=access_token,
                valor=valor,
                descricao=descricao,
                external_reference=external_reference,
                pagador_email=pagador_email,
                pagador_nome=pagador_nome,
            )
            if res.get("qr_code") or res.get("order_id"):
                return res
        except RuntimeError as e:
            # Faz fallback seguro para /v1/payments caso /v1/orders não esteja habilitado ou restrito no Sandbox
            print(f"[MP Orders Fallback -> Payments] {e}")

    pay_res = mp_criar_pagamento_pix(
        access_token=access_token,
        valor=valor,
        descricao=descricao,
        external_reference=external_reference,
        pagador_email=pagador_email,
        pagador_nome=pagador_nome,
        notification_url=notification_url,
    )
    return {"order_id": None, **pay_res}


def mp_consultar_pagamento(access_token: str, payment_id: str) -> Dict[str, Any]:
    if not access_token or not payment_id:
        return {"status": "unknown"}
    status, data = _http_json_request(
        f"https://api.mercadopago.com/v1/payments/{urllib.parse.quote(str(payment_id))}",
        method="GET",
        headers=_mp_headers(access_token),
        timeout=12,
    )
    if status != 200:
        return {"status": "error", "http_status": status, "detail": data.get("message", "")}
    poi_tx = ((data.get("point_of_interaction") or {}).get("transaction_data") or {})
    tx_det = data.get("transaction_details") if isinstance(data.get("transaction_details"), dict) else {}
    return {
        "payment_id": str(data.get("id")),
        "status": data.get("status", "pending"),
        "status_detail": data.get("status_detail", ""),
        "external_reference": data.get("external_reference", ""),
        "transaction_amount": data.get("transaction_amount", 0),
        "payment_method_id": data.get("payment_method_id") or "",
        "payment_type_id": data.get("payment_type_id") or "",
        "installments": data.get("installments") or 1,
        "end_to_end_id": poi_tx.get("e2e_id") or tx_det.get("transaction_id") or "",
        "ticket_url": poi_tx.get("ticket_url") or tx_det.get("external_resource_url") or "",
        "date_approved": data.get("date_approved"),
    }


def mp_validar_assinatura_webhook(
    x_signature: Optional[str],
    x_request_id: Optional[str],
    data_id: Optional[str],
    secret: Optional[str],
) -> bool:
    """Valida assinatura HMAC-SHA256 do header x-signature do Mercado Pago (exige secret configurado)."""
    if not secret or not secret.strip():
        return False
    if not x_signature:
        return False
    ts_val = None
    v1_val = None
    for part in x_signature.split(","):
        kv = part.strip().split("=", 1)
        if len(kv) == 2:
            if kv[0] == "ts":
                ts_val = kv[1].strip()
            elif kv[0] == "v1":
                v1_val = kv[1].strip()
    if not ts_val or not v1_val:
        return False

    raw_id = str(data_id or "")
    candidates = {raw_id, raw_id.lower()}
    secret_bytes = secret.strip().encode("utf-8")
    for cid in candidates:
        manifest = f"id:{cid};request-id:{x_request_id or ''};ts:{ts_val};"
        digest = hmac.new(secret_bytes, manifest.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(digest, v1_val):
            return True
    return False


def mp_enviar_pix_colaborador(
    access_token: str,
    valor: float,
    pix_tipo: str,
    pix_chave: str,
    favorecido_nome: str,
    favorecido_cpf: Optional[str],
    descricao: str,
    external_reference: str,
) -> Dict[str, Any]:
    """
    Dispara transferência PIX de saída via Mercado Pago Payouts / Disbursements API.
    Requer permissão de Payouts / Transferências habilitada na conta PJ do Mercado Pago.
    """
    if not access_token or not access_token.strip():
        raise ValueError("Access Token do Mercado Pago não configurado.")
    if not pix_chave or not pix_chave.strip():
        raise ValueError("O colaborador não possui Chave PIX cadastrada no perfil.")

    key_type_map = {
        "cpf": "CPF",
        "cnpj": "CNPJ",
        "email": "EMAIL",
        "telefone": "PHONE",
        "aleatoria": "EVP",
    }
    mp_key_type = key_type_map.get((pix_tipo or "cpf").lower(), "CPF")
    clean_key = pix_chave.strip()
    if mp_key_type in ("CPF", "CNPJ", "PHONE"):
        digits = re.sub(r"\D", "", clean_key)
        if mp_key_type == "PHONE" and not digits.startswith("55") and len(digits) in (10, 11):
            digits = "+55" + digits
        elif mp_key_type == "PHONE" and not clean_key.startswith("+"):
            digits = "+" + digits
        clean_key = digits

    payload: Dict[str, Any] = {
        "external_reference": external_reference,
        "amount": round(float(valor), 2),
        "description": descricao[:140],
        "receiver": {
            "name": favorecido_nome[:100],
            "pix_key": {
                "type": mp_key_type,
                "value": clean_key,
            },
        },
    }
    if favorecido_cpf:
        cpf_digits = re.sub(r"\D", "", favorecido_cpf)
        if cpf_digits:
            payload["receiver"]["identification"] = {"type": "CPF", "number": cpf_digits}

    idem = f"nc-payout-{external_reference}"
    status, data = _http_json_request(
        "https://api.mercadopago.com/v1/disbursements",
        method="POST",
        headers=_mp_headers(access_token, idem),
        payload=payload,
        timeout=15,
    )
    if status in (200, 201):
        return {
            "payout_id": str(data.get("id") or data.get("transaction_id") or idem),
            "status": data.get("status", "approved"),
            "raw": data,
        }

    err_msg = data.get("message") or data.get("error") or f"HTTP {status}"
    raise RuntimeError(
        f"Mercado Pago Payouts ({status}): {err_msg}. Verifique se a API de Transferências/Disbursements está habilitada na sua conta PJ Mercado Pago."
    )


# ==================== REGISTRADOR DE DOMÍNIOS & VERCEL SSL ENGINE ====================

def registrar_dominio_no_provedor(
    provedor: str,
    api_user: Optional[str],
    api_key: Optional[str],
    client_ip: Optional[str],
    dominio: str,
    anos: int,
    titular_nome: str,
    titular_email: str,
    titular_telefone: Optional[str],
) -> Dict[str, Any]:
    """
    Executa o registro automático do domínio no registrador configurado
    (Namecheap API, ResellerClub API ou Sandbox/Homologação).
    """
    prov = (provedor or "sandbox").strip().lower()
    if prov in ("sandbox", "simulado", ""):
        return {
            "sucesso": True,
            "provedor": "sandbox",
            "order_id": f"SBX-DOM-{uuid.uuid4().hex[:8].upper()}",
            "mensagem": f"Domínio {dominio} registrado em modo homologação e apontado para Vercel DNS.",
        }

    if not api_user or not api_key:
        raise ValueError(f"Credenciais da API do registrador ({prov}) não configuradas.")

    parts = (titular_nome or "Cliente Nexus").strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "Empresa"
    phone_fmt = "+55.27999999999"
    if titular_telefone:
        d = re.sub(r"\D", "", titular_telefone)
        if len(d) >= 10:
            phone_fmt = f"+55.{d[-11:]}"

    if prov == "namecheap":
        sld, tld = dominio.split(".", 1)
        params = {
            "ApiUser": api_user.strip(),
            "ApiKey": api_key.strip(),
            "UserName": api_user.strip(),
            "ClientIp": (client_ip or "127.0.0.1").strip(),
            "Command": "namecheap.domains.create",
            "DomainName": dominio,
            "Years": str(max(1, int(anos))),
            "RegistrantFirstName": first_name,
            "RegistrantLastName": last_name,
            "RegistrantAddress1": "Av Principal 100",
            "RegistrantCity": "Aracruz",
            "RegistrantStateProvince": "ES",
            "RegistrantPostalCode": "29190000",
            "RegistrantCountry": "BR",
            "RegistrantPhone": phone_fmt,
            "RegistrantEmailAddress": titular_email,
            "TechFirstName": first_name,
            "TechLastName": last_name,
            "TechAddress1": "Av Principal 100",
            "TechCity": "Aracruz",
            "TechStateProvince": "ES",
            "TechPostalCode": "29190000",
            "TechCountry": "BR",
            "TechPhone": phone_fmt,
            "TechEmailAddress": titular_email,
            "AdminFirstName": first_name,
            "AdminLastName": last_name,
            "AdminAddress1": "Av Principal 100",
            "AdminCity": "Aracruz",
            "AdminStateProvince": "ES",
            "AdminPostalCode": "29190000",
            "AdminCountry": "BR",
            "AdminPhone": phone_fmt,
            "AdminEmailAddress": titular_email,
            "AuxBillingFirstName": first_name,
            "AuxBillingLastName": last_name,
            "AuxBillingAddress1": "Av Principal 100",
            "AuxBillingCity": "Aracruz",
            "AuxBillingStateProvince": "ES",
            "AuxBillingPostalCode": "29190000",
            "AuxBillingCountry": "BR",
            "AuxBillingPhone": phone_fmt,
            "AuxBillingEmailAddress": titular_email,
        }
        url = "https://api.namecheap.com/xml.response?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_body = resp.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_body)
        if root.attrib.get("Status") != "OK":
            err_el = root.find(".//{http://api.namecheap.com/xml.response}Error")
            err_msg = err_el.text if err_el is not None else "Erro ao registrar domínio na Namecheap."
            raise RuntimeError(err_msg)

        # Configura DNS automático apontando para Vercel (@ A 76.76.21.21 e www CNAME cname.vercel-dns.com)
        dns_params = {
            "ApiUser": api_user.strip(),
            "ApiKey": api_key.strip(),
            "UserName": api_user.strip(),
            "ClientIp": (client_ip or "127.0.0.1").strip(),
            "Command": "namecheap.domains.dns.setHosts",
            "SLD": sld,
            "TLD": tld,
            "HostName1": "@",
            "RecordType1": "A",
            "Address1": "76.76.21.21",
            "TTL1": "300",
            "HostName2": "www",
            "RecordType2": "CNAME",
            "Address2": "cname.vercel-dns.com.",
            "TTL2": "300",
        }
        try:
            urllib.request.urlopen("https://api.namecheap.com/xml.response?" + urllib.parse.urlencode(dns_params), timeout=12)
        except Exception:
            pass

        return {
            "sucesso": True,
            "provedor": "namecheap",
            "order_id": f"NC-{sld.upper()}-{uuid.uuid4().hex[:6].upper()}",
            "mensagem": f"Domínio {dominio} registrado na Namecheap com DNS apontado para Vercel.",
        }

    if prov == "resellerclub":
        params = {
            "auth-userid": api_user.strip(),
            "api-key": api_key.strip(),
            "domain-name": dominio,
            "years": str(max(1, int(anos))),
            "ns": ["ns1.vercel-dns.com", "ns2.vercel-dns.com"],
            "customer-id": client_ip or "0",
            "reg-contact-id": client_ip or "0",
            "admin-contact-id": client_ip or "0",
            "tech-contact-id": client_ip or "0",
            "billing-contact-id": client_ip or "0",
            "invoice-option": "NoInvoice",
        }
        url = "https://httpapi.com/api/domains/register.json?" + urllib.parse.urlencode(params, doseq=True)
        status, data = _http_json_request(url, method="POST", timeout=20)
        if status not in (200, 201) or data.get("status") == "ERROR":
            raise RuntimeError(data.get("message") or "Erro ao registrar domínio no ResellerClub.")
        return {
            "sucesso": True,
            "provedor": "resellerclub",
            "order_id": str(data.get("entityid") or f"RC-{uuid.uuid4().hex[:8].upper()}"),
            "mensagem": f"Domínio {dominio} registrado via ResellerClub.",
        }

    raise ValueError(f"Provedor de registro '{prov}' não suportado.")


def provisionar_dominio_vercel(
    vercel_token: Optional[str],
    project_id: Optional[str],
    team_id: Optional[str],
    dominio: str,
) -> Dict[str, Any]:
    """Adiciona o domínio ao projeto Vercel para emissão automática de certificado SSL/HTTPS."""
    if not vercel_token or not project_id:
        return {"provisionado": False, "dns_status": "aguardando_propagacao", "detalhe": "Credenciais Vercel não configuradas."}

    qs = f"?teamId={urllib.parse.quote(team_id.strip())}" if team_id and team_id.strip() else ""
    url = f"https://api.vercel.com/v10/projects/{urllib.parse.quote(project_id.strip())}/domains{qs}"
    headers = {"Authorization": f"Bearer {vercel_token.strip()}"}
    status, data = _http_json_request(url, method="POST", headers=headers, payload={"name": dominio}, timeout=12)

    if status in (200, 201, 409):
        verified = bool(data.get("verified", False))
        return {
            "provisionado": True,
            "dns_status": "ativo_ssl" if verified else "aguardando_propagacao",
            "detalhe": "Certificado SSL ativo na Vercel" if verified else "Domínio adicionado na Vercel; aguardando propagação DNS",
        }
    return {
        "provisionado": False,
        "dns_status": "aguardando_propagacao",
        "detalhe": data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else str(data),
    }


def verificar_status_dns_vercel(
    vercel_token: Optional[str],
    project_id: Optional[str],
    team_id: Optional[str],
    dominio: str,
) -> Dict[str, Any]:
    """Verifica na API da Vercel se o CNAME/A já propagou e o SSL está ativo."""
    if not vercel_token or not project_id:
        return {"dns_status": "aguardando_propagacao", "misconfigured": True, "detalhe": "Configure VERCEL_TOKEN e VERCEL_PROJECT_ID para verificação automática."}

    qs = f"?teamId={urllib.parse.quote(team_id.strip())}" if team_id and team_id.strip() else ""
    url = f"https://api.vercel.com/v9/projects/{urllib.parse.quote(project_id.strip())}/domains/{urllib.parse.quote(dominio)}/config{qs}"
    headers = {"Authorization": f"Bearer {vercel_token.strip()}"}
    status, data = _http_json_request(url, method="GET", headers=headers, timeout=10)
    if status == 200:
        misconfigured = bool(data.get("misconfigured", True))
        return {
            "dns_status": "ativo_ssl" if not misconfigured else "aguardando_propagacao",
            "misconfigured": misconfigured,
            "detalhe": "DNS propagado e Certificado SSL/HTTPS ativo!" if not misconfigured else "Aguardando propagação do registro CNAME (cname.vercel-dns.com).",
        }
    return {"dns_status": "aguardando_propagacao", "misconfigured": True, "detalhe": "Não foi possível consultar o status DNS na Vercel."}


# ==================== GITHUB ENTERPRISE & VERCEL DEVOPS ENGINE ====================

def _github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "NexusCodeEnterprise/2.5",
    }


def slugify_repo_name(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", texto or "projeto-nexus").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", norm.lower()).strip("-.")
    return slug[:80] or "projeto-nexus"


def extrair_repo_full_name(repo_url_ou_slug: Optional[str], default_owner: Optional[str] = None) -> Optional[str]:
    raw = (repo_url_ou_slug or "").strip().rstrip("/")
    if not raw:
        return None
    if raw.endswith(".git"):
        raw = raw[:-4]
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+)$", raw, re.IGNORECASE)
    if m:
        return m.group(1)
    if "/" in raw and not raw.startswith("http"):
        parts = [p for p in raw.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    if default_owner and re.match(r"^[a-zA-Z0-9._-]+$", raw):
        return f"{default_owner.strip()}/{raw}"
    return None


def _build_starter_repo_files(repo_name: str, descricao: str, template: str, org_name: str) -> List[Dict[str, str]]:
    desc_clean = (descricao or f"Projeto corporativo provisionado pelo Portal {org_name}.").strip()
    first_line_html = re.sub(r"[\r\n\t]+", " ", desc_clean.splitlines()[0] if desc_clean else "").strip()[:180]
    if not first_line_html or "DEMONSTRATIVO" in first_line_html.upper():
        first_line_html = f"Aplicação corporativa gerenciada via {org_name} & Nexus CodeSpaces."
    tpl = (template or "fullstack").strip().lower()

    readme = (
        f"# {repo_name}\n\n"
        f"{desc_clean}\n\n"
        f"## Arquitetura & DevOps\n"
        f"- **Provisionado via:** {org_name} Enterprise DevOps\n"
        f"- **Cloud IDE:** Nexus Code Studio (Codespaces Web)\n"
        f"- **Pipeline CI/CD:** GitHub Actions + Vercel\n"
    )
    gitignore = "node_modules/\n__pycache__/\n*.py[cod]\n.env\n.env.local\n.DS_Store\ndist/\nbuild/\n.vscode/\n"
    ci_yml = (
        "name: Nexus Code CI\n"
        "on:\n  push:\n    branches: [ main, develop ]\n  pull_request:\n    branches: [ main ]\n"
        "jobs:\n  validate:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: Verificar Estrutura\n        run: ls -la\n"
    )

    files = [
        {"path": "README.md", "content": readme},
        {"path": ".gitignore", "content": gitignore},
        {"path": ".github/workflows/nexus-ci.yml", "content": ci_yml},
    ]

    if tpl == "python":
        files.extend([
            {"path": "requirements.txt", "content": "fastapi>=0.115.0\nuvicorn[standard]>=0.30.0\npydantic>=2.8.0\n"},
            {
                "path": "app/main.py",
                "content": (
                    "from fastapi import FastAPI\n\n"
                    f'app = FastAPI(title="{repo_name}", version="1.0.0")\n\n'
                    "@app.get('/')\n"
                    "def health():\n"
                    f'    return {{"status": "online", "service": "{repo_name}"}}\n'
                ),
            },
        ])
    elif tpl in ("nodejs", "fullstack"):
        files.extend([
            {
                "path": "package.json",
                "content": json.dumps(
                    {
                        "name": repo_name,
                        "version": "1.0.0",
                        "private": True,
                        "scripts": {"start": "node src/index.js", "dev": "node --watch src/index.js"},
                    },
                    indent=2,
                ) + "\n",
            },
            {
                "path": "src/index.js",
                "content": (
                    "const http = require('http');\n"
                    "const PORT = process.env.PORT || 3000;\n\n"
                    "const server = http.createServer((req, res) => {\n"
                    "  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });\n"
                    f"  res.end(JSON.stringify({{ status: 'online', project: '{repo_name}', timestamp: new Date().toISOString() }}));\n"
                    "});\n\n"
                    "server.listen(PORT, () => console.log(`Servidor ativo na porta ${PORT}`));\n"
                ),
            },
        ])
        if tpl == "fullstack":
            files.append({
                "path": "public/index.html",
                "content": (
                    f"<!DOCTYPE html>\n<html lang=\"pt-BR\">\n<head>\n  <meta charset=\"UTF-8\">\n  <title>{repo_name}</title>\n</head>\n"
                    f"<body style=\"font-family:system-ui;background:#0A1D37;color:#fff;padding:40px;\">\n  <h1>{repo_name}</h1>\n  <p>{first_line_html}</p>\n</body>\n</html>\n"
                ),
            })
    else:
        files.extend([
            {
                "path": "index.html",
                "content": (
                    f"<!DOCTYPE html>\n<html lang=\"pt-BR\">\n<head>\n  <meta charset=\"UTF-8\">\n  <title>{repo_name}</title>\n"
                    "  <link rel=\"stylesheet\" href=\"assets/css/style.css\">\n</head>\n"
                    f"<body>\n  <main class=\"hero\"><h1>{repo_name}</h1><p>{first_line_html}</p></main>\n  <script src=\"assets/js/app.js\"></script>\n</body>\n</html>\n"
                ),
            },
            {"path": "assets/css/style.css", "content": "body { margin: 0; font-family: system-ui, sans-serif; background: #061224; color: #f8fafc; }\n.hero { max-width: 860px; margin: 80px auto; padding: 32px; }\n"},
            {"path": "assets/js/app.js", "content": f"console.log('{repo_name} inicializado via Nexus Code Studio');\n"},
        ])
    return files


def github_testar_conexao(token: str, org: Optional[str] = None) -> Dict[str, Any]:
    if not token or not token.strip():
        raise ValueError("Informe o Personal Access Token do GitHub.")
    clean_tok = token.strip()
    st, user_data = _http_json_request("https://api.github.com/user", method="GET", headers=_github_headers(clean_tok), timeout=12)
    if st != 200:
        raise RuntimeError(f"GitHub Auth ({st}): {user_data.get('message') or 'Token inválido ou expirado.'}")
    login = user_data.get("login", "")
    target_org = (org or login).strip()
    is_org = False
    if target_org and target_org.lower() != login.lower():
        st_o, org_data = _http_json_request(f"https://api.github.com/orgs/{urllib.parse.quote(target_org)}", method="GET", headers=_github_headers(clean_tok), timeout=10)
        if st_o == 200:
            is_org = True
        else:
            raise RuntimeError(f"Organização '{target_org}' não encontrada ou sem permissão no token (HTTP {st_o}).")

    tipo_token = "Fine-grained PAT" if clean_tok.startswith("github_pat_") else "Classic PAT"
    aviso_permissoes = (
        "Fine-grained PAT detetado: garanta que 'Administration: Read and write' e 'Contents: Read and write' estão ativos em Repository permissions."
        if clean_tok.startswith("github_pat_")
        else "Classic PAT detetado: garanta que o escopo 'repo' está selecionado."
    )
    return {
        "ok": True,
        "usuario_github": login,
        "organizacao": target_org,
        "tipo_conta": "Organização" if is_org else "Conta Pessoal",
        "tipo_token": tipo_token,
        "aviso_permissoes": aviso_permissoes,
    }


def github_criar_repositorio_empresa(
    token: str,
    org: Optional[str],
    repo_nome: str,
    descricao: str = "",
    visibilidade: str = "private",
    template: str = "fullstack",
    empresa_nome: str = "Nexus Code Brasil",
) -> Dict[str, Any]:
    if not token or not token.strip():
        raise ValueError("Token do GitHub não configurado em Empresa & Permissões > Integrações.")

    clean_tok = token.strip()
    clean_repo = slugify_repo_name(repo_nome)
    is_private = (visibilidade or "private").strip().lower() != "public"
    raw_desc = (descricao or f"Repositório gerenciado pelo Portal {empresa_nome}").splitlines()[0].strip()
    clean_desc = re.sub(r"[\x00-\x1f\x7f]+", " ", raw_desc)
    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()[:280]
    if not clean_desc:
        clean_desc = re.sub(r"[\x00-\x1f\x7f]+", " ", f"Repositório gerenciado pelo Portal {empresa_nome}").strip()[:280]
    payload = {
        "name": clean_repo,
        "description": clean_desc,
        "private": is_private,
        "auto_init": False,
        "has_issues": True,
        "has_projects": True,
    }

    headers = _github_headers(clean_tok)
    clean_org = (org or "").strip()

    # Identifica o utilizador autenticado para saber se clean_org é conta pessoal ou organização
    st_u, user_data = _http_json_request("https://api.github.com/user", method="GET", headers=headers, timeout=12)
    if st_u != 200:
        raise RuntimeError(f"GitHub Auth ({st_u}): {user_data.get('message') or 'Token do GitHub inválido ou expirado.'}")
    auth_login = (user_data.get("login") or "").strip()

    status, data = (0, {})
    is_personal_target = not clean_org or (auth_login and clean_org.lower() == auth_login.lower())

    if not is_personal_target:
        status, data = _http_json_request(
            f"https://api.github.com/orgs/{urllib.parse.quote(clean_org)}/repos",
            method="POST",
            headers=headers,
            payload=payload,
            timeout=15,
        )

    if is_personal_target or status == 404:
        status, data = _http_json_request(
            "https://api.github.com/user/repos",
            method="POST",
            headers=headers,
            payload=payload,
            timeout=15,
        )

    if status not in (200, 201):
        errs = data.get("errors") if isinstance(data.get("errors"), list) else []
        extra = errs[0].get("message") if errs and isinstance(errs[0], dict) else ""
        msg = data.get("message") or "Falha ao criar repositório no GitHub."
        if status == 403 and "personal access token" in msg.lower():
            raise RuntimeError(
                "GitHub (403): O Personal Access Token não possui permissão para criar repositórios. "
                "No Fine-grained Token (github_pat_), ative 'Administration: Read and write' e 'Contents: Read and write' em Repository permissions (ou utilize um Classic Token com o escopo 'repo')."
            )
        if status == 422 and "already exists" in f"{msg} {extra}".lower():
            owner_slug = clean_org or auth_login
            raise RuntimeError(
                f"GitHub (422): Já existe um repositório chamado '{owner_slug}/{clean_repo}' na sua conta GitHub."
            )
        raise RuntimeError(f"GitHub ({status}): {msg} {extra}".strip())

    full_name = data.get("full_name")
    default_branch = data.get("default_branch") or "main"

    starter_files = _build_starter_repo_files(clean_repo, descricao, template, empresa_nome)
    for idx, f_item in enumerate(starter_files):
        b64 = base64.b64encode(f_item["content"].encode("utf-8")).decode("ascii")
        put_st, put_data = _http_json_request(
            f"https://api.github.com/repos/{full_name}/contents/{urllib.parse.quote(f_item['path'])}",
            method="PUT",
            headers=headers,
            payload={
                "message": "chore: inicialização automática pelo Portal Nexus Enterprise" if idx == 0 else f"chore: adiciona {f_item['path']}",
                "content": b64,
                "branch": default_branch,
            },
            timeout=15,
        )
        if put_st not in (200, 201):
            put_msg = put_data.get("message") or "Erro ao enviar ficheiros iniciais."
            raise RuntimeError(
                f"Repositório '{full_name}' criado, mas falhou o envio dos ficheiros ({put_st}: {put_msg}). "
                "Ative 'Contents: Read and write' nas permissões do token."
            )

    return {
        "repo_id": data.get("id"),
        "name": data.get("name", clean_repo),
        "full_name": full_name,
        "html_url": data.get("html_url"),
        "clone_url": data.get("clone_url"),
        "default_branch": default_branch,
        "visibilidade": "private" if data.get("private", is_private) else "public",
    }


def github_listar_arvore_repositorio(token: str, full_name: str, branch: str = "main") -> Dict[str, Any]:
    headers = _github_headers(token)
    st_r, repo_data = _http_json_request(f"https://api.github.com/repos/{full_name}", method="GET", headers=headers, timeout=12)
    if st_r != 200:
        raise RuntimeError(f"Repositório '{full_name}' não acessível no GitHub ({st_r}): {repo_data.get('message', '')}")

    active_branch = branch or repo_data.get("default_branch") or "main"
    _, branches_data = _http_json_request(f"https://api.github.com/repos/{full_name}/branches?per_page=30", method="GET", headers=headers, timeout=12)
    branches = [b.get("name") for b in branches_data if isinstance(b, dict)] if isinstance(branches_data, list) else [active_branch]
    if active_branch not in branches and branches:
        active_branch = branches[0]

    _, commits_data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/commits?sha={urllib.parse.quote(active_branch)}&per_page=15",
        method="GET",
        headers=headers,
        timeout=12,
    )
    commits = []
    if isinstance(commits_data, list):
        for c in commits_data:
            cm = c.get("commit") or {}
            author = cm.get("author") or {}
            commits.append({
                "sha": str(c.get("sha") or "")[:7],
                "full_sha": c.get("sha"),
                "message": (cm.get("message") or "").splitlines()[0],
                "author": author.get("name") or (c.get("author") or {}).get("login") or "Dev",
                "date": author.get("date") or "",
                "html_url": c.get("html_url") or "",
            })

    st_t, tree_data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/git/trees/{urllib.parse.quote(active_branch)}?recursive=1",
        method="GET",
        headers=headers,
        timeout=15,
    )
    items = []
    if st_t == 200 and isinstance(tree_data.get("tree"), list):
        for node in tree_data["tree"]:
            items.append({
                "path": node.get("path"),
                "type": node.get("type"),
                "size": node.get("size", 0),
                "sha": node.get("sha"),
            })

    return {
        "full_name": full_name,
        "html_url": repo_data.get("html_url"),
        "private": bool(repo_data.get("private")),
        "default_branch": repo_data.get("default_branch") or "main",
        "branch": active_branch,
        "branches": branches,
        "commits": commits,
        "tree": items,
    }


def github_ler_arquivo(token: str, full_name: str, path: str, branch: str = "main") -> Dict[str, Any]:
    clean_path = path.lstrip("/")
    url = f"https://api.github.com/repos/{full_name}/contents/{urllib.parse.quote(clean_path)}?ref={urllib.parse.quote(branch)}"
    st, data = _http_json_request(url, method="GET", headers=_github_headers(token), timeout=12)
    if st != 200:
        raise RuntimeError(f"Não foi possível abrir '{clean_path}' ({st}): {data.get('message', '')}")

    raw_b64 = (data.get("content") or "").replace("\n", "")
    is_binary = False
    decoded = ""
    try:
        decoded = base64.b64decode(raw_b64).decode("utf-8")
    except Exception:
        is_binary = True
        decoded = f"[Arquivo binário ou imagem: {data.get('name')} ({data.get('size', 0)} bytes)]"

    return {
        "path": data.get("path", clean_path),
        "name": data.get("name", clean_path.split("/")[-1]),
        "sha": data.get("sha"),
        "size": data.get("size", 0),
        "is_binary": is_binary,
        "content": decoded,
        "html_url": data.get("html_url", ""),
    }


def github_salvar_arquivo(
    token: str,
    full_name: str,
    path: str,
    content: str,
    message: Optional[str] = None,
    branch: str = "main",
    sha: Optional[str] = None,
) -> Dict[str, Any]:
    clean_path = path.lstrip("/")
    headers = _github_headers(token)
    target_sha = sha

    if not target_sha:
        st_chk, chk_data = _http_json_request(
            f"https://api.github.com/repos/{full_name}/contents/{urllib.parse.quote(clean_path)}?ref={urllib.parse.quote(branch)}",
            method="GET",
            headers=headers,
            timeout=10,
        )
        if st_chk == 200 and isinstance(chk_data, dict):
            target_sha = chk_data.get("sha")

    payload: Dict[str, Any] = {
        "message": (message or f"feat: atualiza {clean_path} via Nexus Code Studio").strip(),
        "content": base64.b64encode((content or "").encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if target_sha:
        payload["sha"] = target_sha

    st, data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/contents/{urllib.parse.quote(clean_path)}",
        method="PUT",
        headers=headers,
        payload=payload,
        timeout=15,
    )
    if st not in (200, 201):
        raise RuntimeError(f"Erro ao salvar '{clean_path}' no GitHub ({st}): {data.get('message', '')}")

    content_obj = data.get("content") or {}
    commit_obj = data.get("commit") or {}
    return {
        "path": content_obj.get("path", clean_path),
        "sha": content_obj.get("sha"),
        "commit_sha": str(commit_obj.get("sha") or "")[:7],
        "commit_url": commit_obj.get("html_url", ""),
    }


def github_excluir_arquivo(token: str, full_name: str, path: str, sha: str, message: Optional[str] = None, branch: str = "main") -> Dict[str, Any]:
    clean_path = path.lstrip("/")
    st, data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/contents/{urllib.parse.quote(clean_path)}",
        method="DELETE",
        headers=_github_headers(token),
        payload={"message": message or f"chore: remove {clean_path}", "sha": sha, "branch": branch},
        timeout=15,
    )
    if st not in (200, 204):
        raise RuntimeError(f"Erro ao excluir '{clean_path}' ({st}): {data.get('message', '')}")
    return {"ok": True, "path": clean_path}


def github_criar_branch(token: str, full_name: str, new_branch: str, from_branch: str = "main") -> Dict[str, Any]:
    headers = _github_headers(token)
    clean_new = re.sub(r"[^a-zA-Z0-9._/-]", "-", new_branch.strip()).strip("/")
    st_ref, ref_data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/git/ref/heads/{urllib.parse.quote(from_branch)}",
        method="GET",
        headers=headers,
        timeout=10,
    )
    if st_ref != 200:
        raise RuntimeError(f"Branch base '{from_branch}' não encontrada ({st_ref}).")
    base_sha = (ref_data.get("object") or {}).get("sha")

    st_cr, cr_data = _http_json_request(
        f"https://api.github.com/repos/{full_name}/git/refs",
        method="POST",
        headers=headers,
        payload={"ref": f"refs/heads/{clean_new}", "sha": base_sha},
        timeout=12,
    )
    if st_cr not in (200, 201):
        raise RuntimeError(f"Falha ao criar branch '{clean_new}' ({st_cr}): {cr_data.get('message', '')}")
    return {"ok": True, "branch": clean_new, "sha": base_sha}


def vercel_disparar_deploy_projeto(
    vercel_token: str,
    team_id: Optional[str],
    project_slug: str,
    github_repo_full_name: str,
    github_token: Optional[str] = None,
    branch: str = "main",
    target: str = "production",
    existing_vercel_project_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not vercel_token or not vercel_token.strip():
        raise ValueError("Configure o Vercel API Token em Empresa & Permissões > Integrações para disparar deploys.")

    headers = {"Authorization": f"Bearer {vercel_token.strip()}"}
    qs = f"?teamId={urllib.parse.quote(team_id.strip())}" if team_id and team_id.strip() else ""
    clean_slug = slugify_repo_name(project_slug)[:50]
    v_proj_id = (existing_vercel_project_id or "").strip()

    if not v_proj_id:
        st_p, p_data = _http_json_request(
            f"https://api.vercel.com/v9/projects{qs}",
            method="POST",
            headers=headers,
            payload={
                "name": clean_slug,
                "gitRepository": {"type": "github", "repo": github_repo_full_name},
            },
            timeout=15,
        )
        if st_p in (200, 201):
            v_proj_id = p_data.get("id", clean_slug)
        elif st_p == 409:
            v_proj_id = clean_slug

    repo_id = None
    if github_token and github_repo_full_name:
        st_g, g_data = _http_json_request(
            f"https://api.github.com/repos/{github_repo_full_name}",
            method="GET",
            headers=_github_headers(github_token),
            timeout=10,
        )
        if st_g == 200:
            repo_id = g_data.get("id")

    deploy_payload: Dict[str, Any] = {
        "name": clean_slug,
        "project": v_proj_id or clean_slug,
    }
    if target == "production":
        deploy_payload["target"] = "production"
    if repo_id:
        deploy_payload["gitSource"] = {"type": "github", "repoId": repo_id, "ref": branch or "main"}

    st_d, d_data = _http_json_request(
        f"https://api.vercel.com/v13/deployments{qs}",
        method="POST",
        headers=headers,
        payload=deploy_payload,
        timeout=20,
    )
    if st_d not in (200, 201):
        err = d_data.get("error", {}).get("message") if isinstance(d_data.get("error"), dict) else (d_data.get("message") or str(d_data))
        raise RuntimeError(f"Vercel Deploy ({st_d}): {err}")

    raw_url = d_data.get("url") or ""
    live_url = f"https://{raw_url}" if raw_url and not raw_url.startswith("http") else raw_url
    return {
        "deployment_id": d_data.get("id"),
        "url": live_url,
        "status": d_data.get("readyState") or d_data.get("status") or "BUILDING",
        "inspector_url": d_data.get("inspectorUrl") or "",
        "vercel_project_id": d_data.get("projectId") or v_proj_id,
    }


def vercel_listar_deploys_projeto(
    vercel_token: Optional[str],
    team_id: Optional[str],
    vercel_project_id: Optional[str],
    github_token: Optional[str] = None,
    github_repo_full_name: Optional[str] = None,
) -> Dict[str, Any]:
    deployments = []
    actions_runs = []

    if vercel_token and vercel_project_id:
        headers = {"Authorization": f"Bearer {vercel_token.strip()}"}
        params = [f"projectId={urllib.parse.quote(vercel_project_id.strip())}", "limit=10"]
        if team_id and team_id.strip():
            params.append(f"teamId={urllib.parse.quote(team_id.strip())}")
        st, data = _http_json_request("https://api.vercel.com/v6/deployments?" + "&".join(params), method="GET", headers=headers, timeout=12)
        if st == 200 and isinstance(data.get("deployments"), list):
            for d in data["deployments"]:
                u = d.get("url") or ""
                deployments.append({
                    "id": d.get("uid") or d.get("id"),
                    "url": f"https://{u}" if u and not u.startswith("http") else u,
                    "state": d.get("state") or d.get("readyState") or "READY",
                    "target": d.get("target") or "preview",
                    "created": d.get("created"),
                    "inspector_url": d.get("inspectorUrl") or "",
                    "commit_msg": ((d.get("meta") or {}).get("githubCommitMessage") or "Deploy via Portal Nexus"),
                })

    if github_token and github_repo_full_name:
        st_a, a_data = _http_json_request(
            f"https://api.github.com/repos/{github_repo_full_name}/actions/runs?per_page=8",
            method="GET",
            headers=_github_headers(github_token),
            timeout=10,
        )
        if st_a == 200 and isinstance(a_data.get("workflow_runs"), list):
            for run in a_data["workflow_runs"]:
                actions_runs.append({
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "branch": run.get("head_branch"),
                    "html_url": run.get("html_url"),
                    "created_at": run.get("created_at"),
                })

    return {"deployments": deployments, "actions_runs": actions_runs}
