"""
Schemas do dominio de Jurimetria Preditiva.

Define os contratos para predicao granular a nivel de pedido individual.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domains.shared.models import TipoPedido


class PredicaoPedidoRequest(BaseModel):
    """Entrada para solicitar predicao de um pedido especifico."""
    processo_id: int
    tipo_pedido: TipoPedido
    descricao: str | None = None
    valor_pedido: float | None = Field(default=None, gt=0)
    juiz_responsavel: str | None = Field(
        default=None,
        description="Nome do juiz — influencia diretamente a predicao.",
    )


class PredicaoPedidoResponse(BaseModel):
    """Resultado da predicao jurimetrica para um pedido."""
    pedido_id: int
    processo_id: int
    tipo_pedido: TipoPedido
    valor_pedido: float | None = None
    probabilidade_deferimento: float = Field(
        ..., description="Probabilidade de o pedido ser deferido (0 a 1)."
    )
    valor_estimado: float | None = Field(
        default=None, description="Valor estimado de condenacao pelo modelo."
    )
    fundamentacao_ia: str = Field(
        ..., description="Explicacao textual da predicao."
    )
    nivel_confianca: str = Field(
        ..., description="ALTO, MEDIO ou BAIXO — quanto o modelo confia na predicao."
    )

    model_config = ConfigDict(from_attributes=True)


class ScoreConsolidadoResponse(BaseModel):
    """Score consolidado de um processo (media ponderada de todos os pedidos)."""
    processo_id: int
    total_pedidos: int
    probabilidade_ganho_consolidada: float
    valor_total_estimado: float
    nivel_risco_geral: str
    pedidos: list[PredicaoPedidoResponse]
