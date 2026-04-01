"""
Tarefas assincronas do Celery (Workers de IA).

Este modulo contem as tarefas pesadas que NAO devem rodar no loop do FastAPI.
Cada tarefa:
    1. Recebe um ID (nao o objeto inteiro — serializacao JSON)
    2. Abre sua propria sessao de banco
    3. Processa a logica (IA/NLP via Gemini ou fallback heuristico)
    4. Atualiza o banco com o resultado
    5. Fecha a sessao

IMPORTANTE: Workers Celery nao compartilham a sessao do FastAPI.
Cada task cria e fecha sua propria sessao via SessionLocal().

Para iniciar o worker:
    celery -A app.core.celery_app worker --loglevel=info --pool=solo
"""

import logging

from celery import states

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.domains.shared.models import Depoimento, StatusDepoimento

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="analisar_contradicao_testemunhas",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def analisar_contradicao_testemunhas_task(self, depoimento_id: int) -> dict:
    """Analisa um depoimento em busca de contradicoes com testemunhos anteriores.

    Utiliza o Google Gemini como cerebro de IA para analise semantica profunda.
    Em caso de falha do Gemini (sem API key, rate limit, timeout), cai
    automaticamente para analise heuristica local (fallback).

    Fluxo:
        1. Busca o depoimento e muda status para PROCESSANDO
        2. Coleta depoimentos anteriores do mesmo processo
        3. Envia para GeminiLegalAgent.analisar_contradicoes_depoimentos()
        4. Atualiza o depoimento com os resultados da IA
        5. Muda status para CONCLUIDO

    Args:
        depoimento_id: ID do depoimento a ser analisado.

    Returns:
        dict com score_confiabilidade e resumo da analise.
    """
    from app.domains.agent_system.gemini_service import GeminiLegalAgent

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

        # ── 2. Coletar depoimentos anteriores ───────
        depoimentos_anteriores = (
            db.query(Depoimento)
            .filter(
                Depoimento.processo_id == depoimento.processo_id,
                Depoimento.id != depoimento.id,
            )
            .all()
        )

        anteriores_formatados = [
            {
                "nome": d.testemunha_nome,
                "texto": d.texto_depoimento,
            }
            for d in depoimentos_anteriores
        ]

        # ── 3. Analisar via Gemini (ou fallback) ────
        agent = GeminiLegalAgent()
        resultado_ia = agent.analisar_contradicoes_depoimentos(
            depoimento_atual={
                "nome": depoimento.testemunha_nome,
                "texto": depoimento.texto_depoimento,
            },
            depoimentos_anteriores=anteriores_formatados if anteriores_formatados else None,
        )

        # ── 4. Extrair dados do resultado ───────────
        score = resultado_ia.get("score_confiabilidade", 0.5)
        score = round(max(0.0, min(1.0, float(score))), 4)

        total_contradicoes = resultado_ia.get("total_contradicoes", 0)
        total_incertezas = resultado_ia.get("total_incertezas", 0)

        # Montar relatorio legivel
        partes_relatorio = []

        if total_incertezas > 0:
            incertezas = resultado_ia.get("incertezas", [])
            marcadores = [
                i.get("marcador", "") for i in incertezas if isinstance(i, dict)
            ]
            if marcadores:
                partes_relatorio.append(
                    f"Marcadores de incerteza ({total_incertezas}): "
                    + ", ".join(f'"{m}"' for m in marcadores if m)
                )

        if total_contradicoes > 0:
            contradicoes = resultado_ia.get("contradicoes", [])
            descricoes = []
            for c in contradicoes:
                if isinstance(c, dict):
                    explicacao = c.get("explicacao", "")
                    t1 = c.get("testemunha_1", "")
                    a1 = c.get("afirmacao_1", "")
                    t2 = c.get("testemunha_2", "")
                    a2 = c.get("afirmacao_2", "")
                    if t1 and a1 and t2 and a2:
                        descricoes.append(
                            f'Testemunha atual diz "{a1}" mas '
                            f'{t2} afirmou "{a2}"'
                        )
                    elif explicacao:
                        descricoes.append(explicacao)
            if descricoes:
                partes_relatorio.append(
                    f"Contradicoes detectadas ({total_contradicoes}): "
                    + "; ".join(descricoes)
                )

        # Adicionar resumo da IA se disponivel
        resumo_ia = resultado_ia.get("resumo_analise", "")
        if resumo_ia and not partes_relatorio:
            partes_relatorio.append(resumo_ia)

        if not partes_relatorio:
            partes_relatorio.append(
                "Nenhuma inconsistencia detectada nesta analise preliminar."
            )

        relatorio = " | ".join(partes_relatorio)

        # Indicar se usou Gemini ou fallback
        modo = resultado_ia.get("_modo", "gemini")
        if modo != "fallback_heuristico":
            relatorio = f"[Gemini IA] {relatorio}"

        # ── 5. Persistir resultado e finalizar ──────
        depoimento.analise_contradicao_ia = relatorio
        depoimento.score_confiabilidade = score
        depoimento.status_analise = StatusDepoimento.CONCLUIDO
        db.commit()

        logger.info(
            f"Analise do depoimento {depoimento_id} concluida (modo={modo}). "
            f"Score: {score}, Contradicoes: {total_contradicoes}"
        )

        return {
            "depoimento_id": depoimento_id,
            "score_confiabilidade": score,
            "total_incertezas": total_incertezas,
            "total_contradicoes": total_contradicoes,
            "resumo": relatorio,
            "status": "concluido",
            "modo_analise": modo,
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
    2. (Opcional) GeminiLegalAgent enriquece a extracao
    3. Dados sao extraidos e validados
    4. Se salvar_processo=True, cria um Processo no banco

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
