import calendar
import json
import urllib.request
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

_HOLIDAYS_CACHE: Dict[int, set] = {}
_MIN_WAGE_CACHE: Optional[float] = None

CBO_CATALOG = [
    {"codigo": "2124-05", "titulo": "Analista de Desenvolvimento de Sistemas", "familia": "Tecnologia da Informação"},
    {"codigo": "2124-10", "titulo": "Analista de Redes e de Comunicação de Dados", "familia": "Tecnologia da Informação"},
    {"codigo": "2124-15", "titulo": "Analista de Sistemas de Automação", "familia": "Tecnologia da Informação"},
    {"codigo": "2124-20", "titulo": "Analista de Suporte Computacional", "familia": "Tecnologia da Informação"},
    {"codigo": "3171-10", "titulo": "Programador de Sistemas de Informação", "familia": "Tecnologia da Informação"},
    {"codigo": "3171-05", "titulo": "Desenvolvedor Web e Mobile (Front-end / Full Stack)", "familia": "Tecnologia da Informação"},
    {"codigo": "2123-05", "titulo": "Administrador de Banco de Dados (DBA)", "familia": "Tecnologia da Informação"},
    {"codigo": "2123-15", "titulo": "Administrador de Sistemas Operacionais / DevOps", "familia": "Tecnologia da Informação"},
    {"codigo": "2122-05", "titulo": "Engenheiro de Aplicativos em Computação", "familia": "Engenharia & Software"},
    {"codigo": "2122-15", "titulo": "Engenheiro de Sistemas Operacionais em Computação", "familia": "Engenharia & Software"},
    {"codigo": "1425-05", "titulo": "Gerente de Rede / Infraestrutura TI", "familia": "Gestão & Liderança"},
    {"codigo": "1425-10", "titulo": "Gerente de Desenvolvimento de Sistemas (Tech Lead)", "familia": "Gestão & Liderança"},
    {"codigo": "1425-15", "titulo": "Gerente de Produção de Tecnologia da Informação", "familia": "Gestão & Liderança"},
    {"codigo": "1425-20", "titulo": "Gerente de Projetos de Tecnologia da Informação", "familia": "Gestão & Liderança"},
    {"codigo": "1425-25", "titulo": "Gerente de Segurança da Informação", "familia": "Gestão & Liderança"},
    {"codigo": "1231-05", "titulo": "Diretor Administrativo", "familia": "Diretoria Executiva"},
    {"codigo": "1231-15", "titulo": "Diretor Financeiro (CFO)", "familia": "Diretoria Executiva"},
    {"codigo": "1236-05", "titulo": "Diretor de Serviços de Informática (CTO)", "familia": "Diretoria Executiva"},
    {"codigo": "2624-10", "titulo": "Designer Gráfico e de Interfaces (UI/UX)", "familia": "Design & Produto"},
    {"codigo": "2624-25", "titulo": "Designer de Produto Digital", "familia": "Design & Produto"},
    {"codigo": "2521-05", "titulo": "Administrador / Analista Administrativo", "familia": "Administração & RH"},
    {"codigo": "4110-10", "titulo": "Assistente Administrativo", "familia": "Administração & RH"},
    {"codigo": "2524-05", "titulo": "Analista de Recursos Humanos (RH)", "familia": "Administração & RH"},
    {"codigo": "4131-10", "titulo": "Auxiliar de Contabilidade / Departamento Pessoal", "familia": "Financeiro & Fiscal"},
    {"codigo": "2522-10", "titulo": "Contador / Analista Contábil e Fiscal", "familia": "Financeiro & Fiscal"},
    {"codigo": "2525-15", "titulo": "Analista Financeiro", "familia": "Financeiro & Fiscal"},
    {"codigo": "1423-05", "titulo": "Gerente Comercial", "familia": "Comercial & Vendas"},
    {"codigo": "3541-25", "titulo": "Assistente de Vendas / SDR", "familia": "Comercial & Vendas"},
    {"codigo": "3541-35", "titulo": "Técnico de Vendas / Executivo de Contas", "familia": "Comercial & Vendas"},
    {"codigo": "2531-15", "titulo": "Publicitário / Analista de Marketing Digital", "familia": "Marketing & Comunicação"},
    {"codigo": "4223-10", "titulo": "Operador de Atendimento / Sucesso do Cliente (CS)", "familia": "Atendimento & Suporte"},
]


def buscar_cbos(termo: str = "") -> List[Dict[str, str]]:
    q = (termo or "").strip().lower()
    if not q:
        return CBO_CATALOG[:25]
    return [
        item for item in CBO_CATALOG
        if q in item["codigo"].lower()
        or q in item["titulo"].lower()
        or q in item["familia"].lower()
    ][:30]


def _round2(val: float) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def obter_feriados_nacionais(ano: int) -> set:
    """Consulta a API pública BrasilAPI para feriados nacionais do ano, com fallback seguro."""
    if ano in _HOLIDAYS_CACHE:
        return _HOLIDAYS_CACHE[ano]

    feriados = set()
    try:
        url = f"https://brasilapi.com.br/api/feriados/v1/{ano}"
        req = urllib.request.Request(url, headers={"User-Agent": "NexusCodeERP/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data:
                    if item.get("date"):
                        feriados.add(item["date"])
    except Exception:
        feriados = {
            f"{ano}-01-01",
            f"{ano}-04-21",
            f"{ano}-05-01",
            f"{ano}-09-07",
            f"{ano}-10-12",
            f"{ano}-11-02",
            f"{ano}-11-15",
            f"{ano}-11-20",
            f"{ano}-12-25",
        }

    _HOLIDAYS_CACHE[ano] = feriados
    return feriados


def obter_salario_minimo_vigente() -> float:
    """Consulta a série oficial 1619 do Banco Central do Brasil (BCB SGS) para salário mínimo."""
    global _MIN_WAGE_CACHE
    if _MIN_WAGE_CACHE is not None:
        return _MIN_WAGE_CACHE

    salario_minimo = 1621.00
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1619/dados/ultimos/1?formato=json"
        req = urllib.request.Request(url, headers={"User-Agent": "NexusCodeERP/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data and isinstance(data, list) and data[0].get("valor"):
                    val = float(data[0]["valor"])
                    if val >= 1400.0:
                        salario_minimo = val
    except Exception:
        pass

    _MIN_WAGE_CACHE = salario_minimo
    return salario_minimo


def parse_hhmm_to_minutes(hhmm: Optional[str]) -> Optional[int]:
    if not hhmm:
        return None
    parts = str(hhmm).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def format_minutes_hhmm(minutes: int) -> str:
    sign = "-" if minutes < 0 else ""
    abs_m = abs(int(minutes))
    return f"{sign}{abs_m // 60:02d}h{abs_m % 60:02d}m"


def calcular_jornada_diaria(
    data_ponto: date,
    entrada: Optional[str],
    saida_almoco: Optional[str],
    retorno_almoco: Optional[str],
    saida: Optional[str],
    carga_diaria_horas: float = 8.0,
    tipo_dia: str = "normal",
) -> Dict[str, Any]:
    """Calcula minutos trabalhados, horas extras 50%/100% e atrasos de uma batida de ponto."""
    feriados = obter_feriados_nacionais(data_ponto.year)
    is_sunday = data_ponto.weekday() == 6
    is_saturday = data_ponto.weekday() == 5
    is_holiday = data_ponto.isoformat() in feriados
    eh_100 = is_sunday or is_holiday or tipo_dia == "feriado_domingo"

    if tipo_dia in ("atestado", "falta_justificada", "folga"):
        meta_min = int(round(carga_diaria_horas * 60)) if not (is_sunday or is_saturday or is_holiday) else 0
        return {
            "minutos_trabalhados": meta_min if tipo_dia in ("atestado", "falta_justificada") else 0,
            "minutos_extras_50": 0,
            "minutos_extras_100": 0,
            "minutos_atraso": 0,
            "eh_feriado_ou_domingo": eh_100,
        }

    m_ent = parse_hhmm_to_minutes(entrada)
    m_sai_alm = parse_hhmm_to_minutes(saida_almoco)
    m_ret_alm = parse_hhmm_to_minutes(retorno_almoco)
    m_sai = parse_hhmm_to_minutes(saida)

    trabalhados = 0
    if m_ent is not None and m_sai is not None and m_sai > m_ent:
        total_bruto = m_sai - m_ent
        intervalo = 0
        if m_sai_alm is not None and m_ret_alm is not None and m_ret_alm > m_sai_alm:
            intervalo = m_ret_alm - m_sai_alm
        trabalhados = max(0, total_bruto - intervalo)
    elif m_ent is not None and m_sai_alm is not None and m_sai_alm > m_ent:
        trabalhados = m_sai_alm - m_ent

    if eh_100:
        esperado_min = 0
    elif is_saturday:
        esperado_min = 240 if carga_diaria_horas >= 8 else 0
    else:
        esperado_min = int(round(carga_diaria_horas * 60))

    tolerancia = 10
    diff = trabalhados - esperado_min

    extras_50 = 0
    extras_100 = 0
    atraso = 0

    if diff > tolerancia:
        if eh_100:
            extras_100 = diff
        else:
            extras_50 = diff
    elif diff < -tolerancia and m_sai is not None and esperado_min > 0:
        atraso = abs(diff)

    return {
        "minutos_trabalhados": trabalhados,
        "minutos_extras_50": extras_50,
        "minutos_extras_100": extras_100,
        "minutos_atraso": atraso,
        "eh_feriado_ou_domingo": eh_100,
    }


def calcular_inss_2026(salario_bruto: float, salario_minimo: float = 1621.00) -> float:
    """Cálculo progressivo oficial do INSS (faixas 7.5%, 9%, 12%, 14% até o teto previdenciário)."""
    if salario_bruto <= 0:
        return 0.0

    f1 = salario_minimo
    f2 = 2902.84
    f3 = 4354.27
    teto = 8475.55

    base = min(salario_bruto, teto)
    inss = 0.0

    if base > 0:
        inss += min(base, f1) * 0.075
    if base > f1:
        inss += (min(base, f2) - f1) * 0.09
    if base > f2:
        inss += (min(base, f3) - f2) * 0.12
    if base > f3:
        inss += (base - f3) * 0.14

    return _round2(inss)


def calcular_irrf_2026(salario_bruto: float, inss: float, dependentes: int = 0) -> float:
    """
    Cálculo oficial do IRRF 2026:
    - Dedução legal (INSS + R$ 189,59/dependente) ou desconto simplificado (R$ 607,20).
    - Isenção até R$ 5.000,00 e redutor gradual até R$ 7.350,00 (Lei 15.270).
    """
    if salario_bruto <= 5000.00:
        return 0.0

    deducao_legal = inss + (dependentes * 189.59)
    deducao_simplificada = 607.20
    deducao_aplicada = max(deducao_legal, deducao_simplificada)

    base_calculo = max(0.0, salario_bruto - deducao_aplicada)

    if base_calculo <= 2428.80:
        imposto = 0.0
    elif base_calculo <= 2826.65:
        imposto = base_calculo * 0.075 - 182.16
    elif base_calculo <= 3751.05:
        imposto = base_calculo * 0.15 - 394.16
    elif base_calculo <= 4664.68:
        imposto = base_calculo * 0.225 - 675.49
    else:
        imposto = base_calculo * 0.275 - 908.73

    imposto = max(0.0, imposto)

    if 5000.00 < salario_bruto <= 7350.00 and imposto > 0:
        redutor = max(0.0, 978.62 - (0.133145 * salario_bruto))
        imposto = max(0.0, imposto - redutor)

    return _round2(imposto)


def calcular_holerite_automatico(
    usuario: Any,
    registros_ponto: List[Any],
    competencia: str,
) -> Dict[str, Any]:
    parts = competencia.strip().split("/")
    mes = int(parts[0])
    ano = int(parts[1])
    _, ultimo_dia_mes = calendar.monthrange(ano, mes)
    inicio_mes = date(ano, mes, 1)
    fim_mes = date(ano, mes, ultimo_dia_mes)

    salario_contratual = float(usuario.salario_base or 0.0)
    carga_diaria = float(getattr(usuario, "carga_horaria_diaria", None) or 8.0)
    tipo_contrato = getattr(usuario, "tipo_contrato", None) or "clt_fixo"
    dependentes = int(getattr(usuario, "dependentes_irrf", None) or 0)
    usa_vt = bool(getattr(usuario, "vale_transporte", False))
    valor_vt_mensal = float(getattr(usuario, "valor_vt_mensal", None) or 0.0)

    salario_minimo = obter_salario_minimo_vigente()
    feriados = obter_feriados_nacionais(ano)

    dias_uteis_mes = 0
    domingos_feriados_mes = 0
    for d in range(1, ultimo_dia_mes + 1):
        dt = date(ano, mes, d)
        if dt.weekday() == 6 or dt.isoformat() in feriados:
            domingos_feriados_mes += 1
        else:
            dias_uteis_mes += 1

    dias_proporcionais = 30
    dt_adm = getattr(usuario, "data_contratacao", None)
    dt_fim = getattr(usuario, "data_fim_contrato", None)
    efetivo_inicio = max(inicio_mes, dt_adm) if (dt_adm and dt_adm > inicio_mes) else inicio_mes
    efetivo_fim = min(fim_mes, dt_fim) if (dt_fim and dt_fim < fim_mes) else fim_mes

    if efetivo_inicio <= efetivo_fim:
        if efetivo_inicio > inicio_mes or efetivo_fim < fim_mes:
            dias_corridos = (efetivo_fim - efetivo_inicio).days + 1
            dias_proporcionais = min(30, max(1, dias_corridos))
    else:
        dias_proporcionais = 0

    registros_validos = [
        r for r in registros_ponto
        if getattr(r, "status_ajuste", "aprovado") != "rejeitado"
    ]
    total_min_trab = sum(int(r.minutos_trabalhados or 0) for r in registros_validos)
    total_min_he50 = sum(int(r.minutos_extras_50 or 0) for r in registros_validos)
    total_min_he100 = sum(int(r.minutos_extras_100 or 0) for r in registros_validos)
    total_min_atraso = sum(int(r.minutos_atraso or 0) for r in registros_validos)

    divisor_mensal = round(carga_diaria * 27.5, 2) if carga_diaria > 0 else 220.0
    if abs(carga_diaria - 8.0) < 0.01:
        divisor_mensal = 220.0
    elif abs(carga_diaria - 6.0) < 0.01:
        divisor_mensal = 180.0

    valor_hora = salario_contratual / divisor_mensal if divisor_mensal > 0 else 0.0

    if tipo_contrato == "horista":
        taxa_hora = salario_contratual if salario_contratual < 500 else valor_hora
        valor_hora = taxa_hora
        salario_base_calc = _round2((total_min_trab / 60.0) * taxa_hora)
    else:
        salario_base_calc = _round2((salario_contratual / 30.0) * dias_proporcionais)

    valor_he50 = _round2((total_min_he50 / 60.0) * valor_hora * 1.5)
    valor_he100 = _round2((total_min_he100 / 60.0) * valor_hora * 2.0)
    valor_dsr = _round2(
        ((valor_he50 + valor_he100) / max(1, dias_uteis_mes)) * domingos_feriados_mes
    ) if (valor_he50 + valor_he100) > 0 else 0.0

    total_proventos_extras = _round2(valor_he50 + valor_he100 + valor_dsr)
    salario_bruto = _round2(salario_base_calc + total_proventos_extras)

    desconto_atrasos = _round2((total_min_atraso / 60.0) * valor_hora) if tipo_contrato != "horista" else 0.0

    if tipo_contrato in ("pj_mensal", "estagio"):
        inss = 0.0
        irrf = 0.0
        fgts = 0.0
    else:
        base_tributavel = max(0.0, salario_bruto - desconto_atrasos)
        inss = calcular_inss_2026(base_tributavel, salario_minimo)
        irrf = calcular_irrf_2026(base_tributavel, inss, dependentes)
        fgts = _round2(base_tributavel * 0.08)

    desconto_vt = 0.0
    if usa_vt and tipo_contrato not in ("pj_mensal",):
        desconto_vt = _round2(min(salario_base_calc * 0.06, valor_vt_mensal if valor_vt_mensal > 0 else salario_base_calc * 0.06))

    total_descontos = _round2(desconto_atrasos + inss + irrf + desconto_vt)
    valor_liquido = _round2(max(0.0, salario_bruto - total_descontos))

    prov_parts = []
    if valor_he50 > 0:
        prov_parts.append(f"HE 50% ({format_minutes_hhmm(total_min_he50)}): R$ {valor_he50:.2f}")
    if valor_he100 > 0:
        prov_parts.append(f"HE 100% ({format_minutes_hhmm(total_min_he100)}): R$ {valor_he100:.2f}")
    if valor_dsr > 0:
        prov_parts.append(f"DSR s/ Extras: R$ {valor_dsr:.2f}")

    desc_parts = []
    if inss > 0:
        desc_parts.append(f"INSS: R$ {inss:.2f}")
    if irrf > 0:
        desc_parts.append(f"IRRF: R$ {irrf:.2f}")
    if desconto_atrasos > 0:
        desc_parts.append(f"Atrasos/Faltas ({format_minutes_hhmm(total_min_atraso)}): R$ {desconto_atrasos:.2f}")
    if desconto_vt > 0:
        desc_parts.append(f"Vale-Transporte (6%): R$ {desconto_vt:.2f}")

    return {
        "usuario_id": usuario.id,
        "usuario_nome": usuario.nome,
        "cargo": usuario.cargo or "",
        "cbo_codigo": getattr(usuario, "cbo_codigo", None) or "",
        "cbo_descricao": getattr(usuario, "cbo_descricao", None) or "",
        "tipo_contrato": tipo_contrato,
        "competencia": competencia,
        "salario_contratual": salario_contratual,
        "dias_proporcionais": dias_proporcionais,
        "salario_base": salario_base_calc,
        "dias_registrados_ponto": len(registros_validos),
        "horas_trabalhadas_fmt": format_minutes_hhmm(total_min_trab),
        "horas_extras_50_fmt": format_minutes_hhmm(total_min_he50),
        "horas_extras_100_fmt": format_minutes_hhmm(total_min_he100),
        "horas_atraso_fmt": format_minutes_hhmm(total_min_atraso),
        "valor_he50": valor_he50,
        "valor_he100": valor_he100,
        "valor_dsr": valor_dsr,
        "proventos": total_proventos_extras,
        "descricao_proventos": " | ".join(prov_parts) if prov_parts else "Sem adicionais variáveis no período",
        "inss": inss,
        "irrf": irrf,
        "desconto_atrasos": desconto_atrasos,
        "desconto_vt": desconto_vt,
        "descontos": total_descontos,
        "descricao_descontos": " | ".join(desc_parts) if desc_parts else "Isento de descontos",
        "valor_liquido": valor_liquido,
        "fgts_valor": fgts,
        "salario_minimo_ref": salario_minimo,
    }
