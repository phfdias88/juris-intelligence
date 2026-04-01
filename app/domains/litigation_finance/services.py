"""
Motor de Pricing para Litigation Finance.

Implementa a matematica financeira de precificacao de ativos judiciais.
Um fundo de investimento usa este servico para determinar o preco maximo
que deve pagar por um processo judicial, garantindo uma TIR alvo.

Formulas implementadas:

    Valor Esperado (EV):
        EV = (V × p) - C
        Onde: V = valor da causa, p = probabilidade de ganho, C = custas

    Preco Maximo de Compra (Valor Presente ajustado ao risco):
        PV = EV / (1 + r)^t
        Onde: r = taxa de retorno anual (TIR), t = tempo em anos

    Margem de Seguranca:
        MS = ((EV - PV) / PV) × 100
"""

from app.domains.litigation_finance.schemas import PricingRequest, PricingResponse


class PricingService:
    """Servico de calculo de preco de compra de processos judiciais.

    Responsabilidades:
    - Calcular o Valor Esperado (Expected Value) do processo
    - Descontar o EV a valor presente usando a TIR exigida pelo fundo
    - Classificar o nivel de risco com base na probabilidade
    - Validar viabilidade financeira (rejeitar EV negativo)
    """

    @staticmethod
    def calcular_preco_compra(dados: PricingRequest) -> PricingResponse:
        """Calcula o preco maximo que um fundo deve pagar pelo processo.

        Args:
            dados: Parametros validados pelo schema PricingRequest.

        Returns:
            PricingResponse com todas as metricas de precificacao.

        Raises:
            ValueError: Se o Valor Esperado for negativo (processo inviavel)
                        ou se os parametros gerarem divisao por zero.
        """

        # ── 1. Valor Esperado (Expected Value) ──────
        #    EV = (V × p) - C
        #    Representa quanto o processo "vale" estatisticamente,
        #    descontando as custas operacionais.
        valor_esperado = (dados.valor_pedido * dados.probabilidade_ganho) - dados.custas_estimadas

        if valor_esperado <= 0:
            raise ValueError(
                f"Processo inviavel: Valor Esperado negativo (R$ {valor_esperado:,.2f}). "
                f"As custas estimadas (R$ {dados.custas_estimadas:,.2f}) superam o "
                f"retorno esperado (R$ {dados.valor_pedido * dados.probabilidade_ganho:,.2f})."
            )

        # ── 2. Conversao de tempo (meses → anos) ────
        tempo_anos = dados.tempo_estimado_meses / 12

        # ── 3. Preco Maximo de Compra (Valor Presente) ─
        #    PV = EV / (1 + r)^t
        #    Desconta o valor esperado futuro para o valor de "hoje",
        #    usando a TIR alvo do fundo como taxa de desconto.
        #    Isso garante que, se o fundo pagar este preco, tera
        #    exatamente a TIR desejada como retorno.
        fator_desconto = (1 + dados.taxa_retorno_anual_alvo) ** tempo_anos

        if fator_desconto == 0:
            raise ValueError("Erro de calculo: fator de desconto resultou em zero.")

        preco_maximo_compra = valor_esperado / fator_desconto

        # ── 4. Lucro Projetado ───────────────────────
        #    Diferenca entre o que o processo vale (EV) e o que
        #    o fundo paga hoje (PV). Este e o "spread" do investidor.
        lucro_projetado = valor_esperado - preco_maximo_compra

        # ── 5. Margem de Seguranca ───────────────────
        #    Quanto maior a margem, mais "protegido" o investimento.
        #    MS = ((EV - PV) / PV) × 100
        margem_seguranca = round((lucro_projetado / preco_maximo_compra) * 100, 2)

        # ── 6. Classificacao de Risco ────────────────
        nivel_risco = PricingService._classificar_risco(dados.probabilidade_ganho)

        return PricingResponse(
            valor_esperado=round(valor_esperado, 2),
            preco_maximo_compra=round(preco_maximo_compra, 2),
            lucro_projetado=round(lucro_projetado, 2),
            nivel_risco=nivel_risco,
            margem_seguranca=margem_seguranca,
            parametros={
                "valor_pedido": dados.valor_pedido,
                "probabilidade_ganho": dados.probabilidade_ganho,
                "tempo_estimado_meses": dados.tempo_estimado_meses,
                "taxa_retorno_anual_alvo": dados.taxa_retorno_anual_alvo,
                "custas_estimadas": dados.custas_estimadas,
                "tempo_em_anos": round(tempo_anos, 4),
                "fator_desconto": round(fator_desconto, 6),
            },
        )

    @staticmethod
    def _classificar_risco(probabilidade: float) -> str:
        """Classifica o nivel de risco com base na probabilidade de ganho.

        Faixas:
            >= 0.70 → BAIXO  (alta chance de exito)
            >= 0.40 → MEDIO  (incerteza moderada)
            <  0.40 → ALTO   (aposta arriscada)
        """
        if probabilidade >= 0.70:
            return "BAIXO"
        elif probabilidade >= 0.40:
            return "MEDIO"
        return "ALTO"
