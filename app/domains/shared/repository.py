"""
Repositorio centralizado para acesso a dados das entidades compartilhadas.

Todos os dominios que precisam ler/escrever Processos, Depoimentos,
PedidosProcessuais ou AtivosFinanceiros passam por aqui.
"""

from sqlalchemy.orm import Session, joinedload

from app.domains.shared.models import (
    AtivoFinanceiro,
    Depoimento,
    PedidoProcessual,
    Processo,
)


class ProcessoRepository:
    """Camada de acesso a dados para a entidade Processo e relacionamentos."""

    def __init__(self, db: Session):
        self.db = db

    # ── Processo ─────────────────────────────────

    def criar(self, processo: Processo) -> Processo:
        """Persiste um novo processo no banco de dados."""
        self.db.add(processo)
        self.db.commit()
        self.db.refresh(processo)
        return processo

    def buscar_por_id(self, processo_id: int) -> Processo | None:
        """Retorna um processo pelo ID com relacionamentos carregados."""
        return (
            self.db.query(Processo)
            .options(
                joinedload(Processo.pedidos),
                joinedload(Processo.depoimentos),
                joinedload(Processo.ativo_financeiro),
            )
            .filter(Processo.id == processo_id)
            .first()
        )

    def buscar_por_cnj(self, numero_cnj: str) -> Processo | None:
        """Retorna um processo pelo numero CNJ."""
        return self.db.query(Processo).filter(Processo.numero_cnj == numero_cnj).first()

    def listar(self, skip: int = 0, limit: int = 50) -> list[Processo]:
        """Lista processos com paginacao."""
        return self.db.query(Processo).offset(skip).limit(limit).all()

    def atualizar(self, processo: Processo, dados: dict) -> Processo:
        """Atualiza campos de um processo existente."""
        for campo, valor in dados.items():
            if valor is not None:
                setattr(processo, campo, valor)
        self.db.commit()
        self.db.refresh(processo)
        return processo

    def deletar(self, processo: Processo) -> None:
        """Remove um processo e seus relacionamentos (cascade)."""
        self.db.delete(processo)
        self.db.commit()

    # ── Depoimento ───────────────────────────────

    def criar_depoimento(self, depoimento: Depoimento) -> Depoimento:
        """Persiste um novo depoimento."""
        self.db.add(depoimento)
        self.db.commit()
        self.db.refresh(depoimento)
        return depoimento

    def buscar_depoimento_por_id(self, depoimento_id: int) -> Depoimento | None:
        """Retorna um depoimento pelo ID."""
        return self.db.query(Depoimento).filter(Depoimento.id == depoimento_id).first()

    def listar_depoimentos(self, processo_id: int) -> list[Depoimento]:
        """Lista todos os depoimentos de um processo."""
        return (
            self.db.query(Depoimento)
            .filter(Depoimento.processo_id == processo_id)
            .all()
        )

    # ── Pedido Processual ────────────────────────

    def criar_pedido(self, pedido: PedidoProcessual) -> PedidoProcessual:
        """Persiste um novo pedido processual."""
        self.db.add(pedido)
        self.db.commit()
        self.db.refresh(pedido)
        return pedido

    def listar_pedidos(self, processo_id: int) -> list[PedidoProcessual]:
        """Lista todos os pedidos de um processo."""
        return (
            self.db.query(PedidoProcessual)
            .filter(PedidoProcessual.processo_id == processo_id)
            .all()
        )

    def atualizar_pedido(self, pedido: PedidoProcessual, dados: dict) -> PedidoProcessual:
        """Atualiza campos de um pedido (usado pelo servico de jurimetria)."""
        for campo, valor in dados.items():
            if valor is not None:
                setattr(pedido, campo, valor)
        self.db.commit()
        self.db.refresh(pedido)
        return pedido

    # ── Ativo Financeiro ─────────────────────────

    def criar_ativo(self, ativo: AtivoFinanceiro) -> AtivoFinanceiro:
        """Persiste um novo ativo financeiro."""
        self.db.add(ativo)
        self.db.commit()
        self.db.refresh(ativo)
        return ativo

    def buscar_ativo_por_processo(self, processo_id: int) -> AtivoFinanceiro | None:
        """Retorna o ativo financeiro vinculado a um processo."""
        return (
            self.db.query(AtivoFinanceiro)
            .filter(AtivoFinanceiro.processo_id == processo_id)
            .first()
        )
