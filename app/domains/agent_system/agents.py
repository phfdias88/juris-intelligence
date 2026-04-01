"""
Arquitetura Multiagente para processamento de documentos juridicos.

Padrao: Agentes Especializados orquestrados por um Supervisor.

    ┌─────────────────────────────────────────┐
    │           AgenteSupervisor              │
    │   (orquestra, valida, consolida)        │
    │                                         │
    │  ┌──────────┐  ┌───────────────────┐   │
    │  │ Extrator  │  │ Analista Logico   │   │
    │  │ (PDF→dados│  │ (contradicoes,    │   │
    │  │  CPF,valor│  │  incertezas)      │   │
    │  └──────────┘  └───────────────────┘   │
    └─────────────────────────────────────────┘

Cada agente:
- Recebe input estruturado
- Processa com logica especializada (mock no MVP, LLM em producao)
- Retorna resultado tipado
- O Supervisor valida antes de entregar ao usuario

Em producao, cada agente sera um wrapper de LangChain/LlamaIndex Agent
com tools especificas e prompts otimizados para sua funcao.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# TIPOS DE RESULTADO
# ════════════════════════════════════════════════════

@dataclass
class DadosExtraidos:
    """Resultado do AgenteExtrator — dados estruturados de um documento."""
    texto_completo: str = ""
    numero_cnj: str | None = None
    cpfs_encontrados: list[str] = field(default_factory=list)
    cnpjs_encontrados: list[str] = field(default_factory=list)
    valores_monetarios: list[float] = field(default_factory=list)
    nomes_partes: list[str] = field(default_factory=list)
    tribunal: str | None = None
    vara: str | None = None
    tipo_acao: str | None = None
    data_distribuicao: str | None = None
    confianca: float = 0.0
    erros: list[str] = field(default_factory=list)


@dataclass
class AnaliseLogica:
    """Resultado do AgenteAnalistaLogico — analise de contradições."""
    incertezas: list[str] = field(default_factory=list)
    contradicoes: list[str] = field(default_factory=list)
    entidades_extraidas: dict = field(default_factory=dict)
    score_confiabilidade: float = 1.0
    relatorio: str = ""


@dataclass
class ResultadoSupervisor:
    """Resultado consolidado do AgenteSupervisor."""
    dados_extraidos: DadosExtraidos | None = None
    analise_logica: AnaliseLogica | None = None
    aprovado: bool = False
    score_qualidade: float = 0.0
    observacoes_supervisor: str = ""
    alertas: list[str] = field(default_factory=list)


# ════════════════════════════════════════════════════
# AGENTE EXTRATOR
# ════════════════════════════════════════════════════

class AgenteExtrator:
    """Especialista em extrair dados estruturados de textos juridicos.

    Responsabilidades:
    - Extrair CPFs, CNPJs, valores monetarios
    - Identificar numero CNJ do processo
    - Encontrar nomes das partes (autor, reu)
    - Detectar tribunal, vara e tipo de acao

    TODO(LLM): Em producao, este agente usara um LLM com prompt
    otimizado para extracao de entidades juridicas, combinado com
    regex para validacao. Stack sugerida:
        - LangChain Agent com tools de regex
        - Prompt few-shot com exemplos de pecas processuais
        - Output parser estruturado (PydanticOutputParser)
    """

    # Padroes regex para extracao
    REGEX_CNJ = r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}"
    REGEX_CPF = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    REGEX_CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
    REGEX_VALOR = r"R\$\s*[\d.,]+(?:\.\d{3})*(?:,\d{2})?"
    REGEX_DATA = r"\d{2}/\d{2}/\d{4}"

    TRIBUNAIS_CONHECIDOS = [
        "TJSP", "TJRJ", "TJMG", "TJRS", "TJPR", "TJSC", "TJBA",
        "TJPE", "TJCE", "TJGO", "TJDF", "TJMT", "TJMS", "TJPA",
        "TJAM", "TJMA", "TJAL", "TJSE", "TJRN", "TJPB", "TJPI",
        "TJES", "TJRO", "TJAC", "TJAP", "TJRR", "TJTO",
        "TRT", "TRF", "TST", "STJ", "STF",
    ]

    def executar(self, texto: str) -> DadosExtraidos:
        """Extrai dados estruturados de um texto juridico.

        Args:
            texto: Texto bruto extraido de PDF ou digitado.

        Returns:
            DadosExtraidos com todos os campos preenchidos.
        """
        resultado = DadosExtraidos(texto_completo=texto)

        if not texto or len(texto.strip()) < 20:
            resultado.erros.append("Texto muito curto para extracao.")
            resultado.confianca = 0.0
            return resultado

        # ── Extrair numero CNJ ───────────────────────
        cnj_match = re.search(self.REGEX_CNJ, texto)
        if cnj_match:
            resultado.numero_cnj = cnj_match.group()

        # ── Extrair CPFs ─────────────────────────────
        resultado.cpfs_encontrados = list(set(re.findall(self.REGEX_CPF, texto)))

        # ── Extrair CNPJs ────────────────────────────
        resultado.cnpjs_encontrados = list(set(re.findall(self.REGEX_CNPJ, texto)))

        # ── Extrair valores monetarios ───────────────
        valores_raw = re.findall(self.REGEX_VALOR, texto)
        for v in valores_raw:
            try:
                limpo = v.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                valor_float = float(limpo)
                if valor_float > 0:
                    resultado.valores_monetarios.append(valor_float)
            except ValueError:
                continue

        # ── Detectar tribunal ────────────────────────
        texto_upper = texto.upper()
        for tribunal in self.TRIBUNAIS_CONHECIDOS:
            if tribunal in texto_upper:
                resultado.tribunal = tribunal
                break

        # ── Detectar tipo de acao ────────────────────
        # TODO(LLM): Classificacao com modelo treinado
        tipos_acao = {
            "trabalhista": ["reclamacao trabalhista", "horas extras", "rescisao", "clt"],
            "consumidor": ["codigo de defesa do consumidor", "cdc", "relacao de consumo"],
            "civel": ["acao civel", "indenizacao", "obrigacao de fazer"],
            "previdenciaria": ["inss", "aposentadoria", "beneficio previdenciario"],
        }
        texto_lower = texto.lower()
        for tipo, palavras in tipos_acao.items():
            if any(p in texto_lower for p in palavras):
                resultado.tipo_acao = tipo
                break

        # ── Extrair datas ────────────────────────────
        datas = re.findall(self.REGEX_DATA, texto)
        if datas:
            resultado.data_distribuicao = datas[0]

        # ── Calcular confianca da extracao ───────────
        campos_preenchidos = sum([
            bool(resultado.numero_cnj),
            len(resultado.cpfs_encontrados) > 0,
            len(resultado.valores_monetarios) > 0,
            bool(resultado.tribunal),
            bool(resultado.tipo_acao),
        ])
        resultado.confianca = round(campos_preenchidos / 5, 2)

        logger.info(
            f"Extracao concluida: CNJ={resultado.numero_cnj}, "
            f"CPFs={len(resultado.cpfs_encontrados)}, "
            f"Valores={len(resultado.valores_monetarios)}, "
            f"Confianca={resultado.confianca}"
        )

        return resultado


# ════════════════════════════════════════════════════
# AGENTE ANALISTA LOGICO
# ════════════════════════════════════════════════════

class AgenteAnalistaLogico:
    """Especialista em detectar contradicoes e inconsistencias em textos.

    Responsabilidades:
    - Analisar depoimentos buscando marcadores de incerteza
    - Cruzar depoimentos para encontrar contradicoes factuais
    - Extrair entidades relevantes (datas, locais, pessoas)

    TODO(LLM): Em producao, usara:
        - Sentence embeddings (paraphrase-multilingual) para
          similaridade semantica entre depoimentos
        - LLM para reasoning sobre contradicoes logicas
        - Chain-of-thought para explicar o raciocinio
    """

    MARCADORES_INCERTEZA = [
        "nao tenho certeza", "acho que", "talvez", "nao me lembro",
        "pode ser que", "se nao me engano", "nao sei ao certo",
        "acredito que", "me parece que", "nao tenho como afirmar",
    ]

    PARES_CONTRADITORIOS = [
        ("estava presente", "nao estava presente"),
        ("vi claramente", "nao consegui ver"),
        ("antes do", "depois do"),
        ("confirmou", "negou"),
        ("concordou", "discordou"),
        ("disse que sim", "disse que nao"),
        ("estava aberto", "estava fechado"),
        ("de manha", "de noite"),
    ]

    def executar(self, texto: str, textos_anteriores: list[dict] | None = None) -> AnaliseLogica:
        """Analisa um texto em busca de inconsistencias.

        Args:
            texto: Texto do depoimento a analisar.
            textos_anteriores: Lista de dicts com 'nome' e 'texto'
                               dos depoimentos anteriores.

        Returns:
            AnaliseLogica com incertezas, contradicoes e score.
        """
        resultado = AnaliseLogica()
        texto_lower = texto.lower()

        # ── Detectar incertezas ──────────────────────
        resultado.incertezas = [m for m in self.MARCADORES_INCERTEZA if m in texto_lower]

        # ── Extrair entidades ────────────────────────
        # TODO(LLM): Named Entity Recognition com spaCy ou LLM
        datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
        horas = re.findall(r"\d{1,2}[h:]\d{2}", texto)
        resultado.entidades_extraidas = {
            "datas_mencionadas": datas,
            "horarios_mencionados": horas,
        }

        # ── Detectar contradicoes com textos anteriores
        if textos_anteriores:
            for anterior in textos_anteriores:
                nome = anterior.get("nome", "Testemunha anterior")
                texto_ant = anterior.get("texto", "").lower()

                for afirmacao, negacao in self.PARES_CONTRADITORIOS:
                    if afirmacao in texto_lower and negacao in texto_ant:
                        resultado.contradicoes.append(
                            f'Diz "{afirmacao}" mas {nome} afirmou "{negacao}"'
                        )
                    elif negacao in texto_lower and afirmacao in texto_ant:
                        resultado.contradicoes.append(
                            f'Diz "{negacao}" mas {nome} afirmou "{afirmacao}"'
                        )

        # ── Calcular score ───────────────────────────
        score = 1.0
        score -= len(resultado.incertezas) * 0.08
        score -= len(resultado.contradicoes) * 0.15
        if len(texto_lower) < 100:
            score -= 0.10
        resultado.score_confiabilidade = round(max(0.0, min(1.0, score)), 4)

        # ── Montar relatorio ─────────────────────────
        partes = []
        if resultado.incertezas:
            partes.append(
                f"Incertezas ({len(resultado.incertezas)}): "
                + ", ".join(f'"{m}"' for m in resultado.incertezas)
            )
        if resultado.contradicoes:
            partes.append(
                f"Contradicoes ({len(resultado.contradicoes)}): "
                + "; ".join(resultado.contradicoes)
            )
        if not partes:
            partes.append("Nenhuma inconsistencia detectada.")
        resultado.relatorio = " | ".join(partes)

        return resultado


# ════════════════════════════════════════════════════
# AGENTE SUPERVISOR
# ════════════════════════════════════════════════════

class AgenteSupervisor:
    """Orquestra os demais agentes e valida resultados antes da entrega.

    Responsabilidades:
    - Decidir quais agentes acionar com base no tipo de input
    - Validar a qualidade do output de cada agente
    - Gerar alertas quando a confianca e baixa
    - Consolidar resultados em formato final

    TODO(LLM): Em producao, o Supervisor sera um LLM (GPT-4/Claude)
    que recebe os outputs dos agentes e aplica reasoning para:
        1. Verificar se os dados extraidos sao coerentes
        2. Detectar possiveis alucinacoes dos sub-agentes
        3. Decidir se precisa reprocessar com parametros diferentes
        4. Gerar observacoes em linguagem natural para o usuario
    """

    def __init__(self):
        self.extrator = AgenteExtrator()
        self.analista = AgenteAnalistaLogico()

    def processar_documento(self, texto: str) -> ResultadoSupervisor:
        """Pipeline completo de processamento de documento.

        Fluxo:
        1. AgenteExtrator → extrai dados estruturados
        2. Supervisor → valida qualidade da extracao
        3. Retorna resultado consolidado com alertas

        Args:
            texto: Texto bruto do documento juridico.

        Returns:
            ResultadoSupervisor com dados extraidos e validacao.
        """
        resultado = ResultadoSupervisor()

        # ── Fase 1: Extracao ─────────────────────────
        logger.info("Supervisor: acionando AgenteExtrator...")
        dados = self.extrator.executar(texto)
        resultado.dados_extraidos = dados

        # ── Fase 2: Validacao do Supervisor ──────────
        alertas = []

        if not dados.numero_cnj:
            alertas.append("Numero CNJ nao encontrado no documento.")

        if not dados.valores_monetarios:
            alertas.append("Nenhum valor monetario detectado.")

        if dados.confianca < 0.4:
            alertas.append(
                f"Confianca da extracao muito baixa ({dados.confianca:.0%}). "
                "Recomenda-se revisao manual."
            )

        if dados.erros:
            alertas.extend(dados.erros)

        resultado.alertas = alertas
        resultado.score_qualidade = dados.confianca
        resultado.aprovado = dados.confianca >= 0.4 and not dados.erros

        # ── Observacoes do Supervisor ────────────────
        # TODO(LLM): Gerar observacoes com LLM baseado nos dados
        if resultado.aprovado:
            resultado.observacoes_supervisor = (
                f"Documento processado com sucesso. "
                f"Confianca: {dados.confianca:.0%}. "
                f"Dados extraidos: CNJ={dados.numero_cnj}, "
                f"{len(dados.cpfs_encontrados)} CPF(s), "
                f"{len(dados.valores_monetarios)} valor(es)."
            )
        else:
            resultado.observacoes_supervisor = (
                f"Documento requer atencao. "
                f"Confianca: {dados.confianca:.0%}. "
                f"Alertas: {'; '.join(alertas)}"
            )

        logger.info(
            f"Supervisor: processamento concluido. "
            f"Aprovado={resultado.aprovado}, "
            f"Qualidade={resultado.score_qualidade}"
        )

        return resultado

    def analisar_depoimento(
        self,
        texto: str,
        testemunha_nome: str,
        depoimentos_anteriores: list[dict] | None = None,
    ) -> ResultadoSupervisor:
        """Pipeline de analise de depoimento com deteccao de contradicoes.

        Fluxo:
        1. AgenteAnalistaLogico → detecta incertezas e contradicoes
        2. Supervisor → valida e consolida
        3. Retorna resultado com score de confiabilidade

        Args:
            texto: Texto do depoimento.
            testemunha_nome: Nome da testemunha.
            depoimentos_anteriores: Depoimentos anteriores para comparacao.

        Returns:
            ResultadoSupervisor com analise logica e validacao.
        """
        resultado = ResultadoSupervisor()

        # ── Fase 1: Analise Logica ───────────────────
        logger.info(f"Supervisor: analisando depoimento de '{testemunha_nome}'...")
        analise = self.analista.executar(texto, depoimentos_anteriores)
        resultado.analise_logica = analise

        # ── Fase 2: Validacao do Supervisor ──────────
        alertas = []

        if analise.score_confiabilidade < 0.5:
            alertas.append(
                f"Score de confiabilidade BAIXO ({analise.score_confiabilidade:.2f}). "
                "Depoimento potencialmente comprometido."
            )

        if len(analise.contradicoes) >= 3:
            alertas.append(
                f"ALERTA: {len(analise.contradicoes)} contradicoes detectadas. "
                "Sugere-se investigacao aprofundada."
            )

        resultado.alertas = alertas
        resultado.score_qualidade = analise.score_confiabilidade
        resultado.aprovado = analise.score_confiabilidade >= 0.5

        resultado.observacoes_supervisor = (
            f"Depoimento de '{testemunha_nome}' analisado. "
            f"Score: {analise.score_confiabilidade:.2f}. "
            f"{analise.relatorio}"
        )

        return resultado
