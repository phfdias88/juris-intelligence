"""
Modelos de dados universais do sistema (shared_models).

Este arquivo e a FUNDACAO de toda a plataforma. Todos os dominios
(legal_intelligence, jurimetrics, litigation_finance, agent_system)
referenciam estes modelos.

Hierarquia de relacionamentos:
    Processo (1) ──► (N) PedidoProcessual
    Processo (1) ──► (N) Depoimento
    Processo (1) ──► (1) AtivoFinanceiro

Convencoes:
    - Todos os modelos herdam de Base (SQLAlchemy declarative)
    - Timestamps UTC em todas as entidades
    - Enums como str + enum.Enum para serializacao JSON nativa
    - Foreign keys com ON DELETE CASCADE para integridade referencial
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ════════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════════

class StatusProcesso(str, enum.Enum):
    """Status do ciclo de vida de um processo judicial."""
    ATIVO = "ativo"
    SUSPENSO = "suspenso"
    ARQUIVADO = "arquivado"
    ENCERRADO = "encerrado"
    EM_RECURSO = "em_recurso"


class TipoPedido(str, enum.Enum):
    """Categorias de pedidos processuais para predicao granular."""
    DANOS_MORAIS = "danos_morais"
    DANOS_MATERIAIS = "danos_materiais"
    HORAS_EXTRAS = "horas_extras"
    RESCISAO_INDIRETA = "rescisao_indireta"
    ADICIONAL_INSALUBRIDADE = "adicional_insalubridade"
    VERBAS_RESCISORIAS = "verbas_rescisorias"
    INDENIZACAO = "indenizacao"
    OUTRO = "outro"


class StatusDepoimento(str, enum.Enum):
    """Status da analise de IA sobre o depoimento."""
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class StatusAtivo(str, enum.Enum):
    """Status do ativo financeiro vinculado ao processo."""
    EM_ANALISE = "em_analise"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"
    ADQUIRIDO = "adquirido"
    LIQUIDADO = "liquidado"


# ════════════════════════════════════════════════════
# MODELO: PROCESSO
# ════════════════════════════════════════════════════

class Processo(Base):
    """Entidade central — representa um processo judicial no sistema.

    Todo o ecossistema gira em torno desta entidade:
    - Legal Intelligence consulta seus Depoimentos
    - Jurimetrics analisa seus PedidosProcessuais
    - Litigation Finance precifica atraves do AtivoFinanceiro
    """

    __tablename__ = "processos"

    id = Column(Integer, primary_key=True, index=True)
    numero_cnj = Column(String(25), unique=True, nullable=False, index=True)
    tribunal = Column(String(50), nullable=False)
    vara = Column(String(100), nullable=True)
    comarca = Column(String(100), nullable=True)
    tipo_acao = Column(String(100), nullable=True)
    valor_causa = Column(Float, nullable=False)
    status = Column(
        Enum(StatusProcesso), default=StatusProcesso.ATIVO, nullable=False
    )
    autor = Column(String(200), nullable=True)
    reu = Column(String(200), nullable=True)
    cpf_cnpj_autor = Column(String(18), nullable=True, index=True)
    cpf_cnpj_reu = Column(String(18), nullable=True, index=True)
    advogado_autor = Column(String(200), nullable=True)
    advogado_reu = Column(String(200), nullable=True)
    juiz_responsavel = Column(String(200), nullable=True)
    data_distribuicao = Column(DateTime, nullable=True)
    resumo = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relacionamentos ──────────────────────────
    pedidos = relationship(
        "PedidoProcessual",
        back_populates="processo",
        cascade="all, delete-orphan",
    )
    depoimentos = relationship(
        "Depoimento",
        back_populates="processo",
        cascade="all, delete-orphan",
    )
    ativo_financeiro = relationship(
        "AtivoFinanceiro",
        back_populates="processo",
        uselist=False,  # Relacao 1:1
        cascade="all, delete-orphan",
    )


# ════════════════════════════════════════════════════
# MODELO: PEDIDO PROCESSUAL
# ════════════════════════════════════════════════════

class PedidoProcessual(Base):
    """Representa um pedido especifico dentro de um processo.

    Este modelo e a base da JURIMETRIA GRANULAR — em vez de prever
    "ganhou ou perdeu o processo", prevemos o resultado de cada pedido
    individualmente (ex: 78% de chance de ganhar Danos Morais com Juiz X).

    Campos de predicao (probabilidade_deferimento, valor_estimado) sao
    preenchidos pelo dominio jurimetrics/ quando o scoring e executado.
    """

    __tablename__ = "pedidos_processuais"

    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(
        Integer,
        ForeignKey("processos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_pedido = Column(Enum(TipoPedido), nullable=False)
    descricao = Column(Text, nullable=True)
    valor_pedido = Column(Float, nullable=True)

    # ── Campos preenchidos pela IA (jurimetrics) ─
    probabilidade_deferimento = Column(Float, nullable=True)
    valor_estimado = Column(Float, nullable=True)
    fundamentacao_ia = Column(Text, nullable=True)

    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relacionamento ───────────────────────────
    processo = relationship("Processo", back_populates="pedidos")


# ════════════════════════════════════════════════════
# MODELO: DEPOIMENTO
# ════════════════════════════════════════════════════

class Depoimento(Base):
    """Depoimento de testemunha vinculado a um processo.

    Fluxo de processamento:
    1. Depoimento e criado com status PENDENTE
    2. Rota dispara task Celery (analisar_contradicao_testemunhas_task)
    3. Worker muda status para PROCESSANDO
    4. IA analisa e preenche analise_contradicao_ia + score_confiabilidade
    5. Status muda para CONCLUIDO (ou ERRO se falhar)

    O campo 'celery_task_id' permite rastrear o progresso da tarefa
    assincrona e consultar o resultado via API.
    """

    __tablename__ = "depoimentos"

    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(
        Integer,
        ForeignKey("processos.id", ondelete="CASCADE"),
        nullable=False,
    )
    testemunha_nome = Column(String(200), nullable=False)
    texto_depoimento = Column(Text, nullable=False)

    # ── Status de processamento assincrono ───────
    status_analise = Column(
        Enum(StatusDepoimento),
        default=StatusDepoimento.PENDENTE,
        nullable=False,
    )
    celery_task_id = Column(String(255), nullable=True)

    # ── Campos preenchidos pela IA (legal_intelligence) ─
    analise_contradicao_ia = Column(Text, nullable=True)
    score_confiabilidade = Column(Float, nullable=True)

    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relacionamento ───────────────────────────
    processo = relationship("Processo", back_populates="depoimentos")


# ════════════════════════════════════════════════════
# MODELO: ATIVO FINANCEIRO
# ════════════════════════════════════════════════════

class AtivoFinanceiro(Base):
    """Vincula um processo ao modulo de Litigation Finance.

    Este modelo transforma um "processo judicial" em um "ativo financeiro"
    precificavel. Um fundo de investimento usa estes dados para decidir
    se compra ou nao o direito creditorio do processo.

    Metricas financeiras:
    - tir_estimada: Taxa Interna de Retorno projetada
    - valor_aquisicao: quanto o fundo pagou (ou pagaria) pelo processo
    - roi_esperado: retorno sobre investimento projetado
    - score_solvencia_reu: capacidade do reu de pagar (pesquisa patrimonial)
    - tempo_estimado_meses: tempo medio ate liquidacao (extraido via jurimetria)
    """

    __tablename__ = "ativos_financeiros"
    __table_args__ = (
        UniqueConstraint("processo_id", name="uq_ativo_processo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(
        Integer,
        ForeignKey("processos.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(
        Enum(StatusAtivo), default=StatusAtivo.EM_ANALISE, nullable=False
    )

    # ── Metricas financeiras ─────────────────────
    valor_aquisicao = Column(Float, nullable=True)
    tir_estimada = Column(Float, nullable=True)
    roi_esperado = Column(Float, nullable=True)
    score_solvencia_reu = Column(Float, nullable=True)
    tempo_estimado_meses = Column(Integer, nullable=True)

    # ── Dados de pricing ─────────────────────────
    probabilidade_ganho_consolidada = Column(Float, nullable=True)
    valor_recuperavel_estimado = Column(Float, nullable=True)
    desconto_aplicado = Column(Float, nullable=True)
    observacoes = Column(Text, nullable=True)

    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relacionamento ───────────────────────────
    processo = relationship("Processo", back_populates="ativo_financeiro")
