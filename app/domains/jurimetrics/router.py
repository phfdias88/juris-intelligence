"""
Router do dominio de Jurimetria Preditiva.

Endpoints para predicao granular a nivel de pedido individual
e score consolidado do processo.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.jurimetrics.schemas import (
    PredicaoPedidoRequest,
    PredicaoPedidoResponse,
    ScoreConsolidadoResponse,
)
from app.domains.jurimetrics.services import JurimetricsService
from app.domains.shared.models import Processo
from app.domains.shared.repository import ProcessoRepository

router = APIRouter(prefix="/jurimetrics", tags=["Jurimetria Preditiva"])


# ── Dependencias ─────────────────────────────────

def _get_repository(db: Session = Depends(get_db)) -> ProcessoRepository:
    return ProcessoRepository(db)


def _get_service(repo: ProcessoRepository = Depends(_get_repository)) -> JurimetricsService:
    return JurimetricsService(repo)


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
    "/predict",
    response_model=PredicaoPedidoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar predicao para um pedido especifico",
)
def predizer_pedido(
    dados: PredicaoPedidoRequest,
    repo: ProcessoRepository = Depends(_get_repository),
    service: JurimetricsService = Depends(_get_service),
):
    """Prediz a probabilidade de deferimento de um pedido especifico.

    Exemplo: qual a chance de o Juiz X deferir "Danos Morais" de R$ 50k
    em um processo na vara trabalhista do TJSP?

    O resultado inclui probabilidade, valor estimado de condenacao
    e uma fundamentacao textual explicando os fatores considerados.
    """
    processo = repo.buscar_por_id(dados.processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processo com id={dados.processo_id} nao encontrado.",
        )
    return service.predizer_pedido(dados, processo)


@router.get(
    "/processos/{processo_id}/score",
    response_model=ScoreConsolidadoResponse,
    summary="Score consolidado de um processo",
)
def score_consolidado(
    processo: Processo = Depends(_get_processo_or_404),
    service: JurimetricsService = Depends(_get_service),
):
    """Retorna o score consolidado do processo.

    Calcula a media ponderada das probabilidades de todos os pedidos
    ja analisados, usando o valor de cada pedido como peso.
    Util para ter uma visao geral do risco do processo inteiro.
    """
    return service.score_consolidado(processo)
