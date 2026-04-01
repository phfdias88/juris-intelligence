"""
Router do dominio de Litigation Finance.

Endpoints para precificacao de ativos judiciais e analise de risco financeiro.
"""

from fastapi import APIRouter, HTTPException, status

from app.domains.litigation_finance.schemas import PricingRequest, PricingResponse
from app.domains.litigation_finance.services import PricingService

router = APIRouter(prefix="/finance", tags=["Litigation Finance"])


@router.post(
    "/calculate-pricing",
    response_model=PricingResponse,
    status_code=status.HTTP_200_OK,
    summary="Calcular preco maximo de compra de um processo",
    description=(
        "Recebe os parametros de um processo judicial e retorna o preco "
        "maximo que um fundo deve pagar para atingir a TIR alvo desejada. "
        "Usa a formula de Valor Presente ajustado ao risco."
    ),
)
def calcular_pricing(dados: PricingRequest):
    """Calcula o pricing de um ativo judicial para decisao de investimento.

    Exemplo de fluxo:
        1. Analista do fundo insere dados do processo
        2. API retorna preco maximo de compra e metricas de risco
        3. Fundo decide se compra ou rejeita o ativo

    Raises:
        HTTP 400: Quando o processo e financeiramente inviavel (EV negativo)
                  ou parametros geram erro de calculo.
    """
    try:
        return PricingService.calcular_preco_compra(dados)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
