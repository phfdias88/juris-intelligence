"""
Router do dominio de Inteligencia Legal.

Endpoints para gestao de testemunhas e analise de contradicoes via NLP.
O processamento pesado e assincrono (Celery) — a API retorna imediatamente
com o task_id para consulta posterior.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.legal_intelligence.services import LegalIntelligenceService
from app.domains.shared.models import Processo
from app.domains.shared.repository import ProcessoRepository
from app.domains.shared.schemas import (
    DepoimentoCreate,
    DepoimentoResponse,
    TaskDispatchResponse,
)

router = APIRouter(prefix="/legal", tags=["Inteligencia Legal"])


# ── Dependencias ─────────────────────────────────

def _get_repository(db: Session = Depends(get_db)) -> ProcessoRepository:
    return ProcessoRepository(db)


def _get_service(repo: ProcessoRepository = Depends(_get_repository)) -> LegalIntelligenceService:
    return LegalIntelligenceService(repo)


def _get_processo_or_404(
    processo_id: int,
    repo: ProcessoRepository = Depends(_get_repository),
) -> Processo:
    processo = repo.buscar_por_id(processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processo com id={processo_id} nao encontrado.",
        )
    return processo


# ── Endpoints ────────────────────────────────────

@router.post(
    "/processos/{processo_id}/depoimentos",
    response_model=DepoimentoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Registrar depoimento e disparar analise de contradicoes",
)
def registrar_depoimento(
    processo_id: int,
    dados: DepoimentoCreate,
    _: Processo = Depends(_get_processo_or_404),
    service: LegalIntelligenceService = Depends(_get_service),
):
    """Registra um depoimento de testemunha e dispara analise assincrona.

    Retorna HTTP 202 (Accepted) porque o processamento de NLP ocorre
    em background via Celery. Use o campo 'celery_task_id' ou o endpoint
    GET /depoimentos/{id} para consultar o resultado.
    """
    return service.registrar_depoimento(
        processo_id=processo_id,
        testemunha_nome=dados.testemunha_nome,
        texto_depoimento=dados.texto_depoimento,
    )


@router.get(
    "/processos/{processo_id}/depoimentos",
    response_model=list[DepoimentoResponse],
    summary="Listar depoimentos de um processo",
)
def listar_depoimentos(
    processo_id: int,
    _: Processo = Depends(_get_processo_or_404),
    service: LegalIntelligenceService = Depends(_get_service),
):
    """Retorna todos os depoimentos de um processo com status da analise."""
    return service.listar_depoimentos(processo_id)


@router.get(
    "/depoimentos/{depoimento_id}",
    response_model=DepoimentoResponse,
    summary="Consultar status/resultado da analise de um depoimento",
)
def buscar_depoimento(
    depoimento_id: int,
    service: LegalIntelligenceService = Depends(_get_service),
):
    """Consulta o depoimento e o status da analise de contradicoes.

    Status possiveis:
    - PENDENTE: aguardando na fila do Celery
    - PROCESSANDO: worker esta analisando
    - CONCLUIDO: analise_contradicao_ia e score_confiabilidade preenchidos
    - ERRO: falha no processamento (verificar logs do worker)
    """
    depoimento = service.buscar_depoimento(depoimento_id)
    if not depoimento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Depoimento com id={depoimento_id} nao encontrado.",
        )
    return depoimento
