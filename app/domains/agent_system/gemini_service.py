"""
Servico de IA com Google Gemini para analise juridica.

Este modulo encapsula toda a comunicacao com a API do Google Gemini,
fornecendo metodos especializados para o dominio juridico:

    - Analise de contradicoes entre depoimentos
    - Extracao inteligente de dados de documentos
    - Avaliacao de confiabilidade de testemunhos

Utiliza o SDK oficial `google-generativeai` com tratamento robusto
de erros (timeout, rate limit, falhas de API) para garantir que
as tasks do Celery nunca quebrem silenciosamente.
"""

import json
import logging
import time
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.core.config import settings

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# PROMPTS ESPECIALIZADOS (SYSTEM INSTRUCTIONS)
# ════════════════════════════════════════════════════

SYSTEM_INSTRUCTION_ANALISE_CONTRADICOES = """
Voce e um Arquiteto de Dados Juridicos e Investigador Senior.
Sua missao e analisar depoimentos de testemunhas em processos judiciais brasileiros,
identificando inconsistencias, contradicoes logicas e estimando o risco processual.

REGRAS ESTRITAS DE SAIDA:
1. Voce DEVE retornar APENAS um objeto JSON valido.
2. NAO inclua marcacoes de markdown (como ```json ou ```).
3. NAO inclua nenhum texto antes ou depois do JSON.

REGRAS DE ANALISE:
1. Compare cada depoimento com TODOS os outros do mesmo processo.
2. Identifique CONTRADICOES DIRETAS (afirmacoes opostas sobre o mesmo fato).
3. Identifique MARCADORES DE INCERTEZA (ex: "acho que", "talvez", "nao tenho certeza").
4. Identifique INCONSISTENCIAS TEMPORAIS (datas, horarios conflitantes).
5. Identifique INCONSISTENCIAS ESPACIAIS (locais conflitantes).
6. Atribua um SCORE DE CONFIABILIDADE de 0.0 (nao confiavel) a 1.0 (totalmente confiavel).

CRITERIOS PARA O SCORE:
- 1.0: Depoimento consistente, sem incertezas, corrobora outros depoimentos
- 0.7-0.9: Pequenas incertezas mas essencialmente coerente
- 0.4-0.6: Incertezas significativas ou contradicoes menores
- 0.1-0.3: Contradicoes graves ou muitas incertezas
- 0.0: Depoimento completamente inconsistente

FORMATO JSON ESPERADO:
{
    "score_confiabilidade": 0.85,
    "total_contradicoes": 2,
    "total_incertezas": 1,
    "risco_geral": "BAIXO",
    "contradicoes": [
        {
            "tipo": "CONTRADICAO_DIRETA",
            "testemunha_1": "Nome A",
            "afirmacao_1": "trecho exato",
            "testemunha_2": "Nome B",
            "afirmacao_2": "trecho exato",
            "gravidade": "ALTA",
            "explicacao": "descricao da contradicao"
        }
    ],
    "incertezas": [
        {
            "testemunha": "Nome",
            "trecho": "trecho exato com incerteza",
            "marcador": "acho que"
        }
    ],
    "resumo_analise": "Resumo conciso em portugues da analise completa",
    "recomendacao": "Recomendacao ao advogado/juiz"
}
"""

SYSTEM_INSTRUCTION_INVESTIGADOR = """
Voce e um Arquiteto de Dados Juridicos e Investigador Senior.
Sua missao e analisar o texto de processos judiciais e identificar
inconsistencias, contradicoes logicas e estimar o risco processual.

REGRAS ESTRITAS DE SAIDA:
1. Voce DEVE retornar APENAS um objeto JSON valido.
2. NAO inclua marcacoes de markdown (como ```json ou ```).
3. NAO inclua nenhum texto antes ou depois do JSON.

FORMATO JSON ESPERADO:
{
  "risco_geral": "BAIXO | MEDIO | ALTO",
  "resumo_analise": "Uma frase resumindo o principal ponto de atencao.",
  "depoimentos_e_fatos": [
    {
      "autor_ou_testemunha": "Nome da pessoa ou Documento X",
      "texto_base": "Trecho da alegacao ou depoimento",
      "score_ia": 0.85,
      "analise_contradicao_ia": "Explicacao direta: por que isso e uma contradicao em relacao ao resto do processo? Se nao houver, diga Consistente."
    }
  ]
}

REGRAS:
- score_ia e um float de 0.0 a 1.0, onde 1.0 e totalmente consistente e 0.0 e totalmente contraditorio
- Se nao houver depoimentos explicitos, analise as alegacoes das partes (autor, reu, peticoes)
- Identifique trechos que possam ser questionados em audiencia
- Se um campo nao puder ser extraido, use null
- Nunca invente dados. Analise apenas o que esta no texto.
"""

SYSTEM_INSTRUCTION_EXTRACAO_DOCUMENTO = """
Voce e um Assistente Juridico especializado em extracao de dados de documentos
processuais brasileiros. Sua funcao e ler o documento completo e extrair todas
as informacoes relevantes com precisao.

REGRAS ESTRITAS DE SAIDA:
1. Voce DEVE retornar APENAS um objeto JSON valido.
2. NAO inclua marcacoes de markdown (como ```json ou ```).
3. NAO inclua nenhum texto antes ou depois do JSON.

FORMATO JSON ESPERADO:
{
    "numero_cnj": "1234567-89.2024.8.26.0100",
    "tribunal": "TJSP",
    "vara": "5a Vara Civel",
    "comarca": "Sao Paulo",
    "tipo_acao": "trabalhista",
    "autor": "Nome do Autor",
    "reu": "Nome do Reu",
    "cpfs": ["123.456.789-00"],
    "cnpjs": ["12.345.678/0001-90"],
    "valores": [150000.00],
    "juiz_responsavel": "Nome do Juiz",
    "data_distribuicao": "2024-01-15",
    "resumo": "Resumo conciso do processo em 2-3 frases",
    "confianca": 0.9
}

Se um campo nao for encontrado, use null. Nunca invente dados.
"""


# ════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ════════════════════════════════════════════════════

class GeminiLegalAgent:
    """Agente de IA juridica alimentado pelo Google Gemini.

    Responsabilidades:
    - Analisar contradicoes entre depoimentos de testemunhas
    - Extrair dados estruturados de documentos processuais
    - Garantir resiliencia (retry, timeout, fallback)

    Uso:
        agent = GeminiLegalAgent()
        resultado = agent.analisar_contradicoes_depoimentos(
            depoimento_atual={"nome": "Carlos", "texto": "..."},
            depoimentos_anteriores=[{"nome": "Maria", "texto": "..."}],
        )
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5

    def __init__(self):
        """Inicializa o agente com a API Key do Gemini."""
        self._api_key = settings.GEMINI_API_KEY
        self._model_name = settings.GEMINI_MODEL
        self._configured = False

        if self._api_key:
            try:
                genai.configure(api_key=self._api_key)
                self._configured = True
                logger.info(
                    f"GeminiLegalAgent configurado com modelo '{self._model_name}'"
                )
            except Exception as e:
                logger.warning(f"Falha ao configurar Gemini API: {e}")
        else:
            logger.warning(
                "GEMINI_API_KEY nao configurada. "
                "O agente funcionara em modo fallback (heuristicas locais)."
            )

    @property
    def is_available(self) -> bool:
        """Verifica se a API do Gemini esta configurada e disponivel."""
        return self._configured and bool(self._api_key)

    def _call_gemini(
        self,
        system_instruction: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Chama a API do Gemini com retry e tratamento de erros.

        Args:
            system_instruction: Instrucao de sistema (persona/regras).
            user_prompt: Prompt do usuario com os dados a analisar.

        Returns:
            dict com a resposta parseada do Gemini.

        Raises:
            RuntimeError: Se todas as tentativas falharem.
        """
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_instruction,
            generation_config=genai.types.GenerationConfig(
                temperature=settings.GEMINI_TEMPERATURE,
                max_output_tokens=settings.GEMINI_MAX_TOKENS,
                response_mime_type="application/json",
            ),
        )

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    f"Gemini API call (tentativa {attempt}/{self.MAX_RETRIES})..."
                )
                response = model.generate_content(user_prompt)

                # Extrair texto da resposta
                text = response.text.strip()

                # Limpar markdown se presente (```json ... ```)
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()

                # Parsear JSON
                parsed = json.loads(text)
                logger.info("Gemini respondeu com sucesso.")
                return parsed

            except google_exceptions.ResourceExhausted as e:
                # Rate limit — aguardar mais tempo
                last_error = e
                wait = self.RETRY_DELAY_SECONDS * attempt * 2
                logger.warning(
                    f"Rate limit atingido (tentativa {attempt}). "
                    f"Aguardando {wait}s..."
                )
                time.sleep(wait)

            except google_exceptions.DeadlineExceeded as e:
                last_error = e
                logger.warning(
                    f"Timeout na API Gemini (tentativa {attempt}): {e}"
                )
                time.sleep(self.RETRY_DELAY_SECONDS)

            except google_exceptions.InvalidArgument as e:
                # Erro de input — nao adianta retry
                logger.error(f"Input invalido para Gemini: {e}")
                raise RuntimeError(f"Input invalido para Gemini: {e}") from e

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    f"Gemini retornou JSON invalido (tentativa {attempt}): {e}"
                )
                time.sleep(self.RETRY_DELAY_SECONDS)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Erro inesperado na API Gemini (tentativa {attempt}): {e}"
                )
                time.sleep(self.RETRY_DELAY_SECONDS)

        # Todas as tentativas falharam
        error_msg = (
            f"Gemini API falhou apos {self.MAX_RETRIES} tentativas. "
            f"Ultimo erro: {last_error}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # ── ANALISE DE CONTRADICOES ──────────────────────

    def analisar_contradicoes_depoimentos(
        self,
        depoimento_atual: dict[str, str],
        depoimentos_anteriores: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Analisa contradicoes entre depoimentos usando Gemini.

        Args:
            depoimento_atual: {"nome": "Carlos", "texto": "..."}.
            depoimentos_anteriores: Lista de {"nome": str, "texto": str}.

        Returns:
            dict com score_confiabilidade, contradicoes, incertezas, etc.
        """
        if not self.is_available:
            logger.info("Gemini indisponivel — usando analise heuristica.")
            return self._fallback_analise_contradicoes(
                depoimento_atual, depoimentos_anteriores
            )

        # Montar prompt com todos os depoimentos
        prompt_parts = [
            "ANALISE OS SEGUINTES DEPOIMENTOS DO MESMO PROCESSO JUDICIAL:\n",
        ]

        # Depoimentos anteriores
        if depoimentos_anteriores:
            prompt_parts.append("=== DEPOIMENTOS ANTERIORES ===\n")
            for i, dep in enumerate(depoimentos_anteriores, 1):
                prompt_parts.append(
                    f"DEPOIMENTO {i} — Testemunha: {dep['nome']}\n"
                    f'"{dep["texto"]}"\n'
                )

        # Depoimento atual (foco da analise)
        prompt_parts.append(
            f"\n=== DEPOIMENTO EM ANALISE ===\n"
            f"Testemunha: {depoimento_atual['nome']}\n"
            f'"{depoimento_atual["texto"]}"\n'
        )

        prompt_parts.append(
            "\nAnalise o DEPOIMENTO EM ANALISE comparando-o com "
            "todos os depoimentos anteriores. Retorne o JSON conforme "
            "o formato especificado nas instrucoes."
        )

        user_prompt = "\n".join(prompt_parts)

        try:
            result = self._call_gemini(
                system_instruction=SYSTEM_INSTRUCTION_ANALISE_CONTRADICOES,
                user_prompt=user_prompt,
            )
            # Garantir campos obrigatorios
            result.setdefault("score_confiabilidade", 0.5)
            result.setdefault("total_contradicoes", 0)
            result.setdefault("total_incertezas", 0)
            result.setdefault("contradicoes", [])
            result.setdefault("incertezas", [])
            result.setdefault("resumo_analise", "Analise concluida pelo Gemini.")
            result.setdefault("recomendacao", "")
            return result

        except RuntimeError:
            logger.warning("Gemini falhou — caindo para analise heuristica.")
            return self._fallback_analise_contradicoes(
                depoimento_atual, depoimentos_anteriores
            )

    # ── ANALISE PROFUNDA (PROMPT INVESTIGADOR) ────────

    def analisar_processo_completo(self, texto: str) -> dict[str, Any]:
        """Analise profunda de um processo inteiro usando o Prompt Investigador.

        Identifica riscos, contradicoes entre alegacoes das partes,
        e pontos vulneraveis para audiencia.

        Args:
            texto: Texto completo do processo judicial.

        Returns:
            dict com risco_geral, resumo_analise, depoimentos_e_fatos.
        """
        if not self.is_available:
            logger.info("Gemini indisponivel — analise profunda nao disponivel.")
            return {
                "risco_geral": "MEDIO",
                "resumo_analise": "Analise profunda indisponivel (Gemini offline). Usando dados da extracao.",
                "depoimentos_e_fatos": [],
            }

        user_prompt = (
            "ANALISE O SEGUINTE PROCESSO JUDICIAL COMPLETO.\n"
            "Identifique todas as inconsistencias, contradicoes entre as partes, "
            "e avalie o risco processual geral.\n\n"
            f"{texto}\n\n"
            "Retorne o JSON conforme o formato especificado nas instrucoes."
        )

        try:
            result = self._call_gemini(
                system_instruction=SYSTEM_INSTRUCTION_INVESTIGADOR,
                user_prompt=user_prompt,
            )
            result.setdefault("risco_geral", "MEDIO")
            result.setdefault("resumo_analise", "Analise concluida pelo Gemini.")
            result.setdefault("depoimentos_e_fatos", [])
            return result

        except RuntimeError:
            logger.warning("Gemini falhou na analise profunda.")
            return {
                "risco_geral": "MEDIO",
                "resumo_analise": "Gemini falhou apos tentativas. Analise manual recomendada.",
                "depoimentos_e_fatos": [],
            }

    # ── EXTRACAO DE DOCUMENTO ────────────────────────

    def extrair_dados_documento(self, texto: str) -> dict[str, Any]:
        """Extrai dados estruturados de um documento juridico usando Gemini.

        Args:
            texto: Texto completo do documento processual.

        Returns:
            dict com numero_cnj, tribunal, partes, valores, etc.
        """
        if not self.is_available:
            logger.info("Gemini indisponivel — usando extracao por regex.")
            return {}

        user_prompt = (
            "EXTRAIA TODOS OS DADOS DO SEGUINTE DOCUMENTO PROCESSUAL:\n\n"
            f"{texto}\n\n"
            "Retorne o JSON conforme o formato especificado nas instrucoes."
        )

        try:
            return self._call_gemini(
                system_instruction=SYSTEM_INSTRUCTION_EXTRACAO_DOCUMENTO,
                user_prompt=user_prompt,
            )
        except RuntimeError:
            logger.warning("Gemini falhou na extracao — retornando vazio.")
            return {}

    # ── FALLBACK HEURISTICO ──────────────────────────

    def _fallback_analise_contradicoes(
        self,
        depoimento_atual: dict[str, str],
        depoimentos_anteriores: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Analise heuristica local (mesmo algoritmo do mock original).

        Usado quando o Gemini esta indisponivel (sem API key, rate limit,
        timeout, etc). Garante que o sistema nunca para de funcionar.
        """
        from app.domains.agent_system.agents import AgenteAnalistaLogico

        analista = AgenteAnalistaLogico()

        textos_anteriores = None
        if depoimentos_anteriores:
            textos_anteriores = [
                {"nome": d["nome"], "texto": d["texto"]}
                for d in depoimentos_anteriores
            ]

        analise = analista.executar(
            depoimento_atual["texto"], textos_anteriores
        )

        # Converter para formato padrao
        contradicoes_formatadas = [
            {
                "tipo": "CONTRADICAO_DIRETA",
                "explicacao": c,
                "gravidade": "MEDIA",
            }
            for c in analise.contradicoes
        ]

        incertezas_formatadas = [
            {
                "testemunha": depoimento_atual["nome"],
                "marcador": m,
                "trecho": "",
            }
            for m in analise.incertezas
        ]

        return {
            "score_confiabilidade": analise.score_confiabilidade,
            "total_contradicoes": len(analise.contradicoes),
            "total_incertezas": len(analise.incertezas),
            "contradicoes": contradicoes_formatadas,
            "incertezas": incertezas_formatadas,
            "resumo_analise": analise.relatorio,
            "recomendacao": (
                "Analise realizada por heuristicas locais (Gemini indisponivel). "
                "Resultados podem ser menos precisos."
            ),
            "_modo": "fallback_heuristico",
        }
