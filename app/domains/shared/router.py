"""
Router CRUD de Processos — a base de toda a plataforma.

Todos os dominios dependem da existencia de processos no banco.
Este router fornece o CRUD completo para gerenciamento.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.shared.models import Processo
from app.domains.shared.repository import ProcessoRepository
from app.domains.shared.schemas import (
    ProcessoCreate,
    ProcessoResponse,
    ProcessoUpdate,
)

router = APIRouter(prefix="/processos", tags=["Processos"])


# ── Dependencias ─────────────────────────────────

def _get_repository(db: Session = Depends(get_db)) -> ProcessoRepository:
    return ProcessoRepository(db)


def _get_processo_or_404(
    processo_id: int,
    repo: ProcessoRepository = Depends(_get_repository),
) -> Processo:
    """Busca processo por ID ou retorna 404."""
    processo = repo.buscar_por_id(processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processo com id={processo_id} nao encontrado.",
        )
    return processo


# ── Endpoints ────────────────────────────────────

@router.post("/", response_model=ProcessoResponse, status_code=status.HTTP_201_CREATED)
def criar_processo(
    dados: ProcessoCreate,
    repo: ProcessoRepository = Depends(_get_repository),
):
    """Cadastra um novo processo judicial no sistema."""
    existente = repo.buscar_por_cnj(dados.numero_cnj)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Processo com CNJ {dados.numero_cnj} ja cadastrado.",
        )
    processo = Processo(**dados.model_dump())
    return repo.criar(processo)


@router.get("/", response_model=list[ProcessoResponse])
def listar_processos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    repo: ProcessoRepository = Depends(_get_repository),
):
    """Lista processos com paginacao."""
    return repo.listar(skip=skip, limit=limit)


@router.get("/{processo_id}", response_model=ProcessoResponse)
def buscar_processo(processo: Processo = Depends(_get_processo_or_404)):
    """Retorna os dados de um processo pelo ID."""
    return processo


@router.patch("/{processo_id}", response_model=ProcessoResponse)
def atualizar_processo(
    dados: ProcessoUpdate,
    processo: Processo = Depends(_get_processo_or_404),
    repo: ProcessoRepository = Depends(_get_repository),
):
    """Atualiza parcialmente os dados de um processo."""
    campos = dados.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum campo enviado para atualizacao.",
        )
    return repo.atualizar(processo, campos)


@router.delete("/{processo_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_processo(
    processo: Processo = Depends(_get_processo_or_404),
    repo: ProcessoRepository = Depends(_get_repository),
):
    """Remove um processo e todos os dados associados (cascade)."""
    repo.deletar(processo)
