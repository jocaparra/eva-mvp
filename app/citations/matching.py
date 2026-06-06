"""Casamento número → fonte com normalização e status explícito."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

from app.state import Citation


class CitationStatus(str, Enum):
    """Status de auditoria de um campo numérico."""

    CITED = "cited"  # número encontrado em fonte data_room
    UNCITED = "uncited"  # número concreto sem fonte data_room
    DIVERGENT = "divergent"  # fontes data_room existem mas números não batem
    ESTIMATE = "estimate"  # marcado como estimativa (est.)
    EXTERNAL = "external"  # confirmado apenas em fonte externa
    MISSING = "missing"  # campo vazio


# Campos financeiros sujeitos a auditoria factual
AUDITABLE_FIELDS = (
    "revenue_2022",
    "revenue_2023",
    "revenue_2024",
    "ebitda",
    "net_margin",
    "growth_yoy",
    "valuation",
    "ev_ebitda",
    "pe_ratio",
    "ev_revenue",
)

_SUFFIX_MULTIPLIERS = {
    "k": 1_000,
    "mil": 1_000,
    "mi": 1_000_000,
    "mm": 1_000_000,
    "m": 1_000_000,
    "milhao": 1_000_000,
    "milhão": 1_000_000,
    "milhoes": 1_000_000,
    "milhões": 1_000_000,
    "bi": 1_000_000_000,
    "bilhao": 1_000_000_000,
    "bilhão": 1_000_000_000,
    "b": 1_000_000_000,
}


@dataclass(frozen=True)
class SourceCandidate:
    """Fonte data_room avaliada no casamento (útil para diagnosticar DIVERGENT)."""

    source_file: str
    page: Optional[int]
    chunk_id: Optional[str]
    best_delta_pct: Optional[float]
    quote: str


@dataclass(frozen=True)
class FieldAudit:
    """Resultado de auditoria de um campo numérico."""

    field: str
    value: str
    status: CitationStatus
    citation: Optional[Citation]  # None explícito quando sem fonte data_room
    match_delta_pct: Optional[float] = None  # diferença % do melhor match (0 = exato)
    source_candidates: Tuple[SourceCandidate, ...] = field(default_factory=tuple)


def _is_estimate(value: str) -> bool:
    lowered = value.lower().strip()
    return lowered.endswith("est.") or " est." in lowered or lowered.endswith("est")


def _parse_token(token: str) -> Optional[float]:
    """Converte token numérico PT-BR/EN para float absoluto."""
    token = token.strip().lower()
    if not token:
        return None

    multiplier = 1.0
    for suffix, mult in sorted(_SUFFIX_MULTIPLIERS.items(), key=lambda x: -len(x[0])):
        if token.endswith(suffix):
            multiplier = float(mult)
            token = token[: -len(suffix)].strip()
            break

    if token.endswith("%"):
        try:
            return float(token[:-1].replace(",", "."))
        except ValueError:
            return None

    # PT-BR: 12.500.000 (milhar com ponto) ou 12,5 (decimal com vírgula)
    cleaned = token.replace("r$", "").replace(" ", "")
    if cleaned.count(",") == 1 and cleaned.count(".") >= 1:
        # ex.: 1.234.567,89
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1 and cleaned.count(",") == 0:
        # ex.: 12.500.000
        cleaned = cleaned.replace(".", "")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def extract_numbers(text: str) -> List[float]:
    """
    Extrai magnitudes numéricas comparáveis de texto financeiro.
    Ex.: "R$ 12,5 mi" → 12_500_000; "12.500.000" → 12_500_000; "25%" → 25.0
    """
    if not text:
        return []

    numbers: List[float] = []
    patterns = [
        r"r\$\s*[\d.,]+(?:\s*(?:mi|mil|mm|m|bi|b|milhões|milhão|bilhão))?",
        r"[\d.,]+\s*(?:%|mi|mil|mm|m|bi|b|milhões|milhão|bilhão)",
        r"[\d.,]+",
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            token = match.group(0).strip()
            if token in seen:
                continue
            seen.add(token)
            parsed = _parse_token(token)
            if parsed is not None:
                numbers.append(parsed)
    return numbers


def _relative_delta(a: float, b: float) -> float:
    """Diferença relativa em percentual (0–100)."""
    if a == 0 and b == 0:
        return 0.0
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom * 100.0


def best_match_delta(field_value: str, quote: str) -> Optional[float]:
    """Menor diferença % entre números do campo e da citação; None se incomparável."""
    field_nums = extract_numbers(field_value)
    quote_nums = extract_numbers(quote)
    if not field_nums or not quote_nums:
        return None
    return min(_relative_delta(fn, qn) for fn in field_nums for qn in quote_nums)


def values_match(field_value: str, quote: str, tolerance: float = 0.08) -> bool:
    """True se algum número do campo bate com algum número da citação (±tolerância)."""
    delta = best_match_delta(field_value, quote)
    if delta is None:
        return False
    return delta / 100.0 <= tolerance


def _source_candidates(value: str, dataroom: List[Citation]) -> Tuple[SourceCandidate, ...]:
    """Lista chunks data_room com delta do melhor match (para revisão humana)."""
    candidates: list[SourceCandidate] = []
    for citation in dataroom:
        quote = citation.get("quote") or ""
        candidates.append(
            SourceCandidate(
                source_file=citation.get("source_file") or "",
                page=citation.get("page"),
                chunk_id=citation.get("chunk_id"),
                best_delta_pct=best_match_delta(value, quote),
                quote=quote[:400],
            )
        )
    return tuple(candidates)


def audit_financial_field(
    field: str,
    value: str,
    citations: List[Citation],
) -> FieldAudit:
    """Audita um campo numérico e retorna status + citação (ou None explícito)."""
    value = str(value or "").strip()
    if not value:
        return FieldAudit(field, value, CitationStatus.MISSING, None)
    if _is_estimate(value):
        return FieldAudit(field, value, CitationStatus.ESTIMATE, None)

    dataroom = [c for c in citations if c.get("source") == "data_room"]
    external = [c for c in citations if c.get("source") == "external"]

    candidates = _source_candidates(value, dataroom)

    for citation in dataroom:
        quote = citation.get("quote") or ""
        if values_match(value, quote):
            return FieldAudit(
                field,
                value,
                CitationStatus.CITED,
                citation,
                match_delta_pct=best_match_delta(value, quote),
                source_candidates=candidates,
            )

    field_has_numbers = bool(extract_numbers(value))
    source_has_numbers = any(extract_numbers(c.get("quote") or "") for c in dataroom)
    if field_has_numbers and dataroom and source_has_numbers:
        best_delta = min(
            (c.best_delta_pct for c in candidates if c.best_delta_pct is not None),
            default=None,
        )
        return FieldAudit(
            field,
            value,
            CitationStatus.DIVERGENT,
            None,
            match_delta_pct=best_delta,
            source_candidates=candidates,
        )

    for citation in external:
        quote = citation.get("quote") or ""
        if values_match(value, quote):
            return FieldAudit(
                field,
                value,
                CitationStatus.EXTERNAL,
                citation,
                match_delta_pct=best_match_delta(value, quote),
            )

    if field_has_numbers:
        return FieldAudit(field, value, CitationStatus.UNCITED, None, source_candidates=candidates)

    return FieldAudit(field, value, CitationStatus.ESTIMATE, None)


def audit_financial_structured(
    financial: dict,
    citations: List[Citation],
) -> dict[str, FieldAudit]:
    """Audita todos os campos numéricos-chave."""
    audits: dict[str, FieldAudit] = {}
    for field in AUDITABLE_FIELDS:
        audits[field] = audit_financial_field(field, str(financial.get(field, "")), citations)
    return audits


def _candidate_to_dict(candidate: SourceCandidate) -> dict[str, Any]:
    return {
        "source_file": candidate.source_file,
        "page": candidate.page,
        "chunk_id": candidate.chunk_id,
        "best_delta_pct": candidate.best_delta_pct,
        "quote": candidate.quote,
    }


def audits_to_serializable(audits: dict[str, FieldAudit]) -> dict:
    """Converte audits para dict JSON-serializável."""
    return {
        field: {
            "field": audit.field,
            "value": audit.value,
            "status": audit.status.value,
            "citation": audit.citation,
            "match_delta_pct": audit.match_delta_pct,
            "source_candidates": [_candidate_to_dict(c) for c in audit.source_candidates],
        }
        for field, audit in audits.items()
    }
