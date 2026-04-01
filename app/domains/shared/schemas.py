"""
Schemas Pydantic compartilhados para validacao de entrada/saida da API.

Cada modelo possui tres variantes:
- *Create: campos obrigatorios para criacao
- *Update: campos opcionais para atualizacao parcial (PATCH)
- *Response: campos retornados ao cliente (from_attributes=True)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.shared.models import (
    StatusAtivo,
    StatusDepoimento,
    StatusProcesso,
    TipoPedido,
)


# ════════════════════════════════════════════════════
# PROCESSO
# ════════════════════════════════════════════════════

class ProcessoCreate(BaseModel):
    """Schema para criacao de um novo processo judicial."""
    numero_cnj: str = Field(
        ..., min_length=20, max_length=25,
        examples=["0000000-00.0000.0.00.0000"],
    )
    tribunal: str = Field(..., max_length=50)
    vara: str | None = None
    comarca: str | None = None
    tipo_acao: str | None = None
    valor_causa: float = Field(..., gt=0)
    autor: str | None = None
    reu: str | None = None
    cpf_cnpj_autor: str | None = None
    cpf_cnpj_reu: str | None = None
    advogado_autor: str | None = None
    advogado_reu: str | None = None
    juiz_responsavel: str | None = None
    data_distribuicao: datetime | None = None
    resumo: str | None = None


class ProcessoUpdate(BaseModel):
    """Schema para atualizacao parcial de um processo."""
    tribunal: str | None = None
    vara: str | None = None
    comarca: str | None = None
    tipo_acao: str | None = None
    valor_causa: float | None = Field(default=None, gt=0)
    status: StatusProcesso | None = None
    autor: str | None = None
    reu: str | None = None
    juiz_responsavel: str | None = None
    resumo: str | None = None


class ProcessoResponse(BaseModel):
    """Schema de resposta completa de um processo."""
    id: int
    numero_cnj: str
    tribunal: str
    vara: str | None = None
    comarca: str | None = None
    tipo_acao: str | None = None
    valor_causa: float
    status: StatusProcesso
    autor: str | None = None
    reu: str | None = None
    cpf_cnpj_autor: str | None = None
    cpf_cnpj_reu: str | None = None
    advogado_autor: str | None = None
    advogado_reu: str | None = None
    juiz_responsavel: str | None = None
    data_distribuicao: datetime | None = None
    resumo: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ════════════════════════════════════════════════════
# PEDIDO PROCESSUAL
# ════════════════════════════════════════════════════

class PedidoProcessualCreate(BaseModel):
    """Schema para registrar um pedido dentro de um processo."""
    processo_id: int
    tipo_pedido: TipoPedido
    descricao: str | None = None
    valor_pedido: float | None = Field(default=None, gt=0)


class PedidoProcessualResponse(BaseModel):
    """Schema de resposta de um pedido processual com dados de predicao."""
    id: int
    processo_id: int
    tipo_pedido: TipoPedido
    descricao: str | None = None
    valor_pedido: float | None = None
    probabilidade_deferimento: float | None = None
    valor_estimado: float | None = None
    fundamentacao_ia: str | None = None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


# ════════════════════════════════════════════════════
# DEPOIMENTO
# ════════════════════════════════════════════════════

class DepoimentoCreate(BaseModel):
    """Schema para registrar um depoimento de testemunha."""
    processo_id: int
    testemunha_nome: str = Field(..., max_length=200)
    texto_depoimento: str = Field(..., min_length=10)


class DepoimentoResponse(BaseModel):
    """Schema de resposta com status da analise assincrona."""
    id: int
    processo_id: int
    testemunha_nome: str
    texto_depoimento: str
    status_analise: StatusDepoimento
    celery_task_id: str | None = None
    analise_contradicao_ia: str | None = None
    score_confiabilidade: float | None = None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


# ════════════════════════════════════════════════════
# ATIVO FINANCEIRO
# ════════════════════════════════════════════════════

class AtivoFinanceiroCreate(BaseModel):
    """Schema para vincular um processo como ativo financeiro."""
    processo_id: int
    valor_aquisicao: float | None = Field(default=None, gt=0)


class AtivoFinanceiroResponse(BaseModel):
    """Schema de resposta do ativo financeiro com metricas de pricing."""
    id: int
    processo_id: int
    status: StatusAtivo
    valor_aquisicao: float | None = None
    tir_estimada: float | None = None
    roi_esperado: float | None = None
    score_solvencia_reu: float | None = None
    tempo_estimado_meses: int | None = None
    probabilidade_ganho_consolidada: float | None = None
    valor_recuperavel_estimado: float | None = None
    desconto_aplicado: float | None = None
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ════════════════════════════════════════════════════
# RESPOSTAS GENERICAS
# ════════════════════════════════════════════════════

class TaskDispatchResponse(BaseModel):
    """Resposta padrao para endpoints que disparam tarefas Celery."""
    mensagem: str
    task_id: str
    status: str = "enviado"
