"""
Schemas Pydantic para o dominio de Litigation Finance.

Define os contratos de entrada e saida da calculadora de pricing.
Todas as validacoes de fronteira (valores negativos, ranges) sao
tratadas aqui — o service recebe dados ja validados.
"""

from pydantic import BaseModel, Field


class PricingRequest(BaseModel):
    """Dados de entrada para calculo de preco maximo de compra de um processo.

    Exemplo de uso por um fundo de investimento:
        - O processo pede R$ 500.000 em danos morais
        - Probabilidade de ganho estimada: 65%
        - Tempo estimado ate transito em julgado: 36 meses
        - O fundo exige retorno minimo de 20% ao ano
        - Custas estimadas (honorarios, pericia, etc): R$ 30.000
    """

    valor_pedido: float = Field(
        ...,
        gt=0,
        description="Valor total do pedido/causa em reais (R$).",
        examples=[500_000.0],
    )
    probabilidade_ganho: float = Field(
        ...,
        ge=0.01,
        le=1.0,
        description="Probabilidade de exito (0.01 a 1.0). Ex: 0.65 = 65%.",
        examples=[0.65],
    )
    tempo_estimado_meses: int = Field(
        ...,
        gt=0,
        le=240,
        description="Tempo estimado em meses ate o transito em julgado.",
        examples=[36],
    )
    taxa_retorno_anual_alvo: float = Field(
        ...,
        gt=0,
        le=5.0,
        description="TIR minima exigida pelo fundo (decimal). Ex: 0.20 = 20% a.a.",
        examples=[0.20],
    )
    custas_estimadas: float = Field(
        ...,
        ge=0,
        description="Custas processuais estimadas em reais (honorarios, pericias, etc).",
        examples=[30_000.0],
    )


class PricingResponse(BaseModel):
    """Resultado do calculo de pricing para decisao de investimento.

    Metricas retornadas:
    - valor_esperado: quanto o processo "vale" estatisticamente
    - preco_maximo_compra: maximo que o fundo deve pagar hoje (Valor Presente)
    - lucro_projetado: diferenca entre valor esperado e preco de compra
    - nivel_risco: classificacao qualitativa baseada na probabilidade
    - margem_seguranca: percentual entre EV e preco maximo (quanto maior, mais seguro)
    """

    valor_esperado: float = Field(
        ..., description="Expected Value = (Valor * Probabilidade) - Custas."
    )
    preco_maximo_compra: float = Field(
        ..., description="Valor Presente do EV descontado pela TIR alvo."
    )
    lucro_projetado: float = Field(
        ..., description="Diferenca entre valor esperado e preco maximo de compra."
    )
    nivel_risco: str = Field(
        ..., description="Classificacao: BAIXO (p>=0.7), MEDIO (p>=0.4), ALTO (p<0.4)."
    )
    margem_seguranca: float = Field(
        ..., description="Percentual de margem entre EV e preco de compra."
    )

    # ── Dados de entrada espelhados para rastreabilidade ─
    parametros: dict = Field(
        ..., description="Parametros de entrada usados no calculo."
    )
