"""
Tarefas assincronas do Celery (Workers de IA).

Este modulo contem as tarefas pesadas que NAO devem rodar no loop do FastAPI.
Cada tarefa:
    1. Recebe um ID (nao o objeto inteiro — serializacao JSON)
    2. Abre sua propria sessao de banco
    3. Processa a logica (IA/NLP)
    4. Atualiza o banco com o resultado
    5. Fecha a sessao

IMPORTANTE: Workers Celery nao compartilham a sessao do FastAPI.
Cada task cria e fecha sua propria sessao via SessionLocal().

Para iniciar o worker:
    celery -A app.core.celery_app worker --loglevel=info --pool=solo
"""

import logging
import time

from celery import states

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.domains.shared.models import Depoimento, StatusDepoimento

logger = logging.getLogger(__name__)


# ── Marcadores de incerteza (mock NLP) ───────────
# TODO(NLP): Substituir por modelo de NLP real (ex: BERT fine-tuned
# para deteccao de hedging/incerteza em textos juridicos pt-BR)
MARCADORES_INCERTEZA = [
    "nao tenho certeza",
    "acho que",
    "talvez",
    "nao me lembro",
    "pode ser que",
    "se nao me engano",
    "nao sei ao certo",
    "acredito que",
    "me parece que",
]

PARES_CONTRADITORIOS = [
    ("estava presente", "nao estava presente"),
    ("vi claramente", "nao consegui ver"),
    ("antes do", "depois do"),
    ("confirmou", "negou"),
    ("concordou", "discordou"),
    ("disse que sim", "disse que nao"),
]


@celery_app.task(
    bind=True,
    name="analisar_contradicao_testemunhas",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def analisar_contradicao_testemunhas_task(self, depoimento_id: int) -> dict:
    """Analisa um depoimento em busca de contradicoes com testemunhos anteriores.

    Esta tarefa simula o processamento de IA que, em producao, sera feito
    pelo agent_system (Agente Analista Logico + Agente Supervisor).

    Fluxo:
        1. Busca o depoimento e muda status para PROCESSANDO
        2. Simula processamento pesado de NLP (sleep)
        3. Executa analise de incertezas e contradicoes (mock)
        4. Atualiza o depoimento com os resultados
        5. Muda status para CONCLUIDO

    Args:
        depoimento_id: ID do depoimento a ser analisado.

    Returns:
        dict com score_confiabilidade e resumo da analise.
    """
    db = SessionLocal()

    try:
        # ── 1. Buscar depoimento e atualizar status ─
        depoimento = db.query(Depoimento).filter(Depoimento.id == depoimento_id).first()

        if not depoimento:
            logger.error(f"Depoimento {depoimento_id} nao encontrado.")
            return {"erro": f"Depoimento {depoimento_id} nao encontrado."}

        depoimento.status_analise = StatusDepoimento.PROCESSANDO
        db.commit()

        logger.info(
            f"Iniciando analise do depoimento {depoimento_id} "
            f"(processo={depoimento.processo_id}, "
            f"testemunha='{depoimento.testemunha_nome}')"
        )

        # ── 2. Simular processamento pesado de IA ───
        # TODO(AGENT_SYSTEM): Aqui e o ponto exato de integracao.
        # Em producao, substituir o bloco abaixo por:
        #
        #   from app.domains.agent_system.agents import AgenteSupervisor
        #   supervisor = AgenteSupervisor()
        #   resultado = supervisor.analisar_depoimento(
        #       depoimento=depoimento,
        #       depoimentos_anteriores=depoimentos_anteriores,
        #   )
        #
        # O AgenteSupervisor orquestra:
        #   1. AgenteAnalistaLogico → detecta contradicoes semanticas
        #   2. AgenteExtrator → extrai entidades (datas, locais, pessoas)
        #   3. O proprio Supervisor → valida e consolida antes de retornar
        time.sleep(5)

        # ── 3. Analise mock (heuristicas) ───────────
        texto_lower = depoimento.texto_depoimento.lower()

        # Detectar marcadores de incerteza
        incertezas = [m for m in MARCADORES_INCERTEZA if m in texto_lower]

        # Comparar com depoimentos anteriores do mesmo processo
        depoimentos_anteriores = (
            db.query(Depoimento)
            .filter(
                Depoimento.processo_id == depoimento.processo_id,
                Depoimento.id != depoimento.id,
            )
            .all()
        )

        contradicoes = []
        for dep_anterior in depoimentos_anteriores:
            texto_ant = dep_anterior.texto_depoimento.lower()
            for afirmacao, negacao in PARES_CONTRADITORIOS:
                if afirmacao in texto_lower and negacao in texto_ant:
                    contradicoes.append(
                        f'Testemunha atual diz "{afirmacao}" mas '
                        f'{dep_anterior.testemunha_nome} afirmou "{negacao}"'
                    )
                elif negacao in texto_lower and afirmacao in texto_ant:
                    contradicoes.append(
                        f'Testemunha atual diz "{negacao}" mas '
                        f'{dep_anterior.testemunha_nome} afirmou "{afirmacao}"'
                    )

        # ── 4. Calcular score e montar relatorio ────
        score = 1.0
        score -= len(incertezas) * 0.08
        score -= len(contradicoes) * 0.15
        if len(texto_lower) < 100:
            score -= 0.10
        score = round(max(0.0, min(1.0, score)), 4)

        partes_relatorio = []
        if incertezas:
            partes_relatorio.append(
                f"Marcadores de incerteza ({len(incertezas)}): "
                + ", ".join(f'"{m}"' for m in incertezas)
            )
        if contradicoes:
            partes_relatorio.append(
                f"Contradicoes detectadas ({len(contradicoes)}): "
                + "; ".join(contradicoes)
            )
        if not partes_relatorio:
            partes_relatorio.append(
                "Nenhuma inconsistencia detectada nesta analise preliminar."
            )

        relatorio = " | ".join(partes_relatorio)

        # ── 5. Persistir resultado e finalizar ──────
        depoimento.analise_contradicao_ia = relatorio
        depoimento.score_confiabilidade = score
        depoimento.status_analise = StatusDepoimento.CONCLUIDO
        db.commit()

        logger.info(
            f"Analise do depoimento {depoimento_id} concluida. "
            f"Score: {score}, Contradicoes: {len(contradicoes)}"
        )

        return {
            "depoimento_id": depoimento_id,
            "score_confiabilidade": score,
            "total_incertezas": len(incertezas),
            "total_contradicoes": len(contradicoes),
            "resumo": relatorio,
            "status": "concluido",
        }

    except Exception as exc:
        # Marcar como erro no banco antes de propagar
        try:
            depoimento = (
                db.query(Depoimento)
                .filter(Depoimento.id == depoimento_id)
                .first()
            )
            if depoimento:
                depoimento.status_analise = StatusDepoimento.ERRO
                db.commit()
        except Exception:
            db.rollback()

        logger.exception(
            f"Erro ao analisar depoimento {depoimento_id}: {exc}"
        )

        # Retry automatico do Celery (ate max_retries)
        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="processar_documento_pipeline",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def processar_documento_pipeline_task(
    self, texto: str, salvar_processo: bool = False
) -> dict:
    """Processa um documento juridico pelo pipeline multiagente.

    Fluxo:
    1. AgenteSupervisor orquestra o AgenteExtrator
    2. Dados sao extraidos e validados
    3. Se salvar_processo=True, cria um Processo no banco

    Args:
        texto: Texto bruto do documento.
        salvar_processo: Se True, persiste como Processo no banco.

    Returns:
        dict com dados extraidos, score de qualidade e processo_id (se criado).
    """
    from app.domains.agent_system.agents import AgenteSupervisor
    from app.domains.shared.models import Processo

    db = SessionLocal()

    try:
        logger.info("Worker: iniciando pipeline multiagente...")

        # ── 1. Processar via Supervisor ──────────────
        supervisor = AgenteSupervisor()
        resultado = supervisor.processar_documento(texto)

        response = {
            "aprovado": resultado.aprovado,
            "score_qualidade": resultado.score_qualidade,
            "observacoes_supervisor": resultado.observacoes_supervisor,
            "alertas": resultado.alertas,
            "dados_extraidos": None,
            "processo_criado_id": None,
        }

        if resultado.dados_extraidos:
            dados = resultado.dados_extraidos
            response["dados_extraidos"] = {
                "numero_cnj": dados.numero_cnj,
                "cpfs_encontrados": dados.cpfs_encontrados,
                "cnpjs_encontrados": dados.cnpjs_encontrados,
                "valores_monetarios": dados.valores_monetarios,
                "tribunal": dados.tribunal,
                "tipo_acao": dados.tipo_acao,
                "confianca": dados.confianca,
            }

            # ── 2. Criar processo se solicitado ──────
            if salvar_processo and resultado.aprovado and dados.numero_cnj:
                valor_causa = max(dados.valores_monetarios) if dados.valores_monetarios else 0.0

                processo_existente = (
                    db.query(Processo)
                    .filter(Processo.numero_cnj == dados.numero_cnj)
                    .first()
                )

                if processo_existente:
                    response["processo_criado_id"] = processo_existente.id
                    response["alertas"].append(
                        f"Processo CNJ {dados.numero_cnj} ja existe (id={processo_existente.id})."
                    )
                else:
                    novo_processo = Processo(
                        numero_cnj=dados.numero_cnj,
                        tribunal=dados.tribunal or "NAO_IDENTIFICADO",
                        tipo_acao=dados.tipo_acao,
                        valor_causa=valor_causa,
                    )
                    db.add(novo_processo)
                    db.commit()
                    db.refresh(novo_processo)
                    response["processo_criado_id"] = novo_processo.id

                    logger.info(
                        f"Processo criado automaticamente: id={novo_processo.id}, "
                        f"cnj={dados.numero_cnj}"
                    )

        logger.info(f"Pipeline concluido. Aprovado={resultado.aprovado}")
        return response

    except Exception as exc:
        logger.exception(f"Erro no pipeline multiagente: {exc}")
        raise self.retry(exc=exc)

    finally:
        db.close()
