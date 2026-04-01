"""
Servico de Jurimetria Preditiva.

Implementa a predicao granular a nivel de pedido individual.
Em vez de prever "ganhou ou perdeu o processo", prediz o resultado
de cada pedido especifico (ex: Danos Morais, Horas Extras) considerando
o tipo de pedido, valor, juiz e tribunal.

No MVP, usa tabelas de probabilidade base por tipo de pedido e
ajustes por juiz. Em producao, sera substituido por modelo de ML
treinado com dados historicos reais de decisoes judiciais.
"""

import random

from app.domains.jurimetrics.schemas import (
    PredicaoPedidoRequest,
    PredicaoPedidoResponse,
    ScoreConsolidadoResponse,
)
from app.domains.shared.models import PedidoProcessual, Processo
from app.domains.shared.repository import ProcessoRepository


# ── Tabela de probabilidades base por tipo de pedido ─
# TODO(IA): Substituir por modelo de ML treinado com dataset
# de decisoes judiciais (TJ, TRT, TST). Fonte: DataJud / CNJ.
PROB_BASE_POR_TIPO = {
    "danos_morais": 0.62,
    "danos_materiais": 0.55,
    "horas_extras": 0.71,
    "rescisao_indireta": 0.38,
    "adicional_insalubridade": 0.58,
    "verbas_rescisorias": 0.78,
    "indenizacao": 0.50,
    "outro": 0.45,
}

# Simulacao de historico de juizes (ajuste positivo ou negativo)
# TODO(IA): Substituir por scoring real baseado em decisoes passadas
AJUSTE_JUIZ = {
    "maria silva": 0.08,
    "joao oliveira": -0.05,
    "ana santos": 0.12,
    "carlos pereira": -0.10,
}


class JurimetricsService:
    """Servico de predicao jurimetrica granular."""

    def __init__(self, repository: ProcessoRepository):
        self.repository = repository

    def predizer_pedido(
        self, request: PredicaoPedidoRequest, processo: Processo
    ) -> PredicaoPedidoResponse:
        """Gera predicao para um pedido individual dentro de um processo.

        Variaveis consideradas (mock):
        - Tipo do pedido: cada categoria tem taxa historica de deferimento
        - Juiz: ajuste baseado em historico de decisoes do magistrado
        - Valor do pedido: pedidos de valor muito alto sofrem penalidade
        - Tribunal: tribunais trabalhistas tendem a ser mais favoraveis ao autor

        Returns:
            PredicaoPedidoResponse com probabilidade, valor estimado e fundamentacao.
        """
        # ── 1. Probabilidade base pelo tipo de pedido ─
        prob_base = PROB_BASE_POR_TIPO.get(request.tipo_pedido.value, 0.45)

        # ── 2. Ajuste pelo juiz responsavel ──────────
        ajuste_juiz = 0.0
        juiz_nome = request.juiz_responsavel or processo.juiz_responsavel
        fundamentacao_partes = [
            f"Probabilidade base para '{request.tipo_pedido.value}': {prob_base:.0%}"
        ]

        if juiz_nome:
            ajuste_juiz = AJUSTE_JUIZ.get(juiz_nome.lower(), 0.0)
            if ajuste_juiz != 0:
                direcao = "favoravel" if ajuste_juiz > 0 else "desfavoravel"
                fundamentacao_partes.append(
                    f"Ajuste pelo historico do Juiz '{juiz_nome}': "
                    f"{ajuste_juiz:+.0%} ({direcao})"
                )

        # ── 3. Ajuste pelo valor do pedido ───────────
        ajuste_valor = 0.0
        if request.valor_pedido and request.valor_pedido > 500_000:
            ajuste_valor = -0.08
            fundamentacao_partes.append(
                "Penalidade por valor elevado (>R$500k): -8%"
            )

        # ── 4. Variacao estocastica (simula incerteza) ─
        # TODO(IA): Remover quando modelo real estiver integrado
        variacao = random.uniform(-0.03, 0.03)

        # ── 5. Probabilidade final ───────────────────
        prob_final = max(0.01, min(0.99, prob_base + ajuste_juiz + ajuste_valor + variacao))
        prob_final = round(prob_final, 4)

        # ── 6. Valor estimado de condenacao ──────────
        valor_estimado = None
        if request.valor_pedido:
            # Tribunais raramente deferem 100% do pedido
            fator_reducao = random.uniform(0.4, 0.85)
            valor_estimado = round(request.valor_pedido * prob_final * fator_reducao, 2)
            fundamentacao_partes.append(
                f"Valor estimado de condenacao: R$ {valor_estimado:,.2f}"
            )

        # ── 7. Nivel de confianca ────────────────────
        if juiz_nome and juiz_nome.lower() in AJUSTE_JUIZ:
            nivel_confianca = "ALTO"
            fundamentacao_partes.append(
                "Confianca ALTA: juiz possui historico mapeado."
            )
        elif request.tipo_pedido.value in ("horas_extras", "verbas_rescisorias"):
            nivel_confianca = "MEDIO"
            fundamentacao_partes.append(
                "Confianca MEDIA: tipo de pedido com jurisprudencia consolidada."
            )
        else:
            nivel_confianca = "BAIXO"
            fundamentacao_partes.append(
                "Confianca BAIXA: dados insuficientes para predicao robusta (MVP)."
            )

        fundamentacao = " | ".join(fundamentacao_partes)

        # ── 8. Persistir pedido no banco ─────────────
        pedido = PedidoProcessual(
            processo_id=request.processo_id,
            tipo_pedido=request.tipo_pedido,
            descricao=request.descricao,
            valor_pedido=request.valor_pedido,
            probabilidade_deferimento=prob_final,
            valor_estimado=valor_estimado,
            fundamentacao_ia=fundamentacao,
        )
        pedido = self.repository.criar_pedido(pedido)

        return PredicaoPedidoResponse(
            pedido_id=pedido.id,
            processo_id=pedido.processo_id,
            tipo_pedido=pedido.tipo_pedido,
            valor_pedido=pedido.valor_pedido,
            probabilidade_deferimento=prob_final,
            valor_estimado=valor_estimado,
            fundamentacao_ia=fundamentacao,
            nivel_confianca=nivel_confianca,
        )

    def score_consolidado(self, processo: Processo) -> ScoreConsolidadoResponse:
        """Calcula o score consolidado do processo baseado em todos os pedidos.

        A probabilidade consolidada e a media ponderada das probabilidades
        de cada pedido, usando o valor do pedido como peso.
        """
        pedidos = self.repository.listar_pedidos(processo.id)

        if not pedidos:
            return ScoreConsolidadoResponse(
                processo_id=processo.id,
                total_pedidos=0,
                probabilidade_ganho_consolidada=0.0,
                valor_total_estimado=0.0,
                nivel_risco_geral="INDETERMINADO",
                pedidos=[],
            )

        # Media ponderada pelo valor do pedido
        soma_pesos = 0.0
        soma_ponderada = 0.0
        valor_total_estimado = 0.0
        pedidos_response = []

        for p in pedidos:
            peso = p.valor_pedido if p.valor_pedido and p.valor_pedido > 0 else 1.0
            prob = p.probabilidade_deferimento or 0.0
            soma_pesos += peso
            soma_ponderada += prob * peso
            valor_total_estimado += p.valor_estimado or 0.0

            pedidos_response.append(PredicaoPedidoResponse(
                pedido_id=p.id,
                processo_id=p.processo_id,
                tipo_pedido=p.tipo_pedido,
                valor_pedido=p.valor_pedido,
                probabilidade_deferimento=prob,
                valor_estimado=p.valor_estimado,
                fundamentacao_ia=p.fundamentacao_ia or "",
                nivel_confianca="MEDIO",
            ))

        prob_consolidada = round(soma_ponderada / soma_pesos, 4) if soma_pesos > 0 else 0.0

        if prob_consolidada >= 0.70:
            nivel = "BAIXO"
        elif prob_consolidada >= 0.40:
            nivel = "MEDIO"
        else:
            nivel = "ALTO"

        return ScoreConsolidadoResponse(
            processo_id=processo.id,
            total_pedidos=len(pedidos),
            probabilidade_ganho_consolidada=prob_consolidada,
            valor_total_estimado=round(valor_total_estimado, 2),
            nivel_risco_geral=nivel,
            pedidos=pedidos_response,
        )
