"""
Router do dominio Agent System.

Endpoints para processamento de documentos juridicos via pipeline
multiagente (Extrator + Analista Logico + Supervisor + Gemini).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.agent_system.agents import AgenteSupervisor
from app.domains.agent_system.schemas import (
    DocumentoTextoRequest,
    DadosExtraidosResponse,
    ProcessamentoResponse,
    UploadResponse,
)
from app.domains.agent_system.tools import extrair_texto_pdf, limpar_texto_juridico
from app.domains.shared.models import Processo

router = APIRouter(prefix="/agents", tags=["Agent System"])


@router.post(
    "/process-text",
    response_model=ProcessamentoResponse,
    summary="Processar texto juridico via pipeline multiagente",
    description=(
        "Recebe texto bruto de um documento juridico e processa "
        "pelo pipeline: AgenteExtrator → Gemini IA → AgenteSupervisor. "
        "Extrai CNJ, CPFs, valores e classifica o tipo de acao. "
        "Se salvar_processo=True, cria o processo no banco de forma "
        "sincrona e retorna o ID imediatamente."
    ),
)
def processar_texto(dados: DocumentoTextoRequest, db: Session = Depends(get_db)):
    """Processa texto juridico e opcionalmente cria o processo no banco."""
    supervisor = AgenteSupervisor()
    resultado = supervisor.processar_documento(dados.texto)

    response = ProcessamentoResponse(
        aprovado=resultado.aprovado,
        score_qualidade=resultado.score_qualidade,
        observacoes_supervisor=resultado.observacoes_supervisor,
        alertas=resultado.alertas,
    )

    if resultado.dados_extraidos:
        d = resultado.dados_extraidos
        response.dados_extraidos = DadosExtraidosResponse(
            numero_cnj=d.numero_cnj,
            cpfs_encontrados=d.cpfs_encontrados,
            cnpjs_encontrados=d.cnpjs_encontrados,
            valores_monetarios=d.valores_monetarios,
            nomes_partes=d.nomes_partes,
            tribunal=d.tribunal,
            vara=d.vara,
            tipo_acao=d.tipo_acao,
            data_distribuicao=d.data_distribuicao,
            confianca=d.confianca,
        )

        # Criar processo de forma SINCRONA para retornar o ID imediatamente
        if dados.salvar_processo and resultado.aprovado and d.numero_cnj:
            valor_causa = max(d.valores_monetarios) if d.valores_monetarios else 0.0

            processo_existente = (
                db.query(Processo)
                .filter(Processo.numero_cnj == d.numero_cnj)
                .first()
            )

            if processo_existente:
                response.processo_criado_id = processo_existente.id
                response.alertas.append(
                    f"Processo CNJ {d.numero_cnj} ja existe (id={processo_existente.id})."
                )
            else:
                # Converter data_distribuicao string para datetime
                data_dist = None
                if d.data_distribuicao:
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            data_dist = datetime.strptime(d.data_distribuicao, fmt)
                            break
                        except ValueError:
                            continue

                novo_processo = Processo(
                    numero_cnj=d.numero_cnj,
                    tribunal=d.tribunal or "NAO_IDENTIFICADO",
                    tipo_acao=d.tipo_acao,
                    valor_causa=valor_causa,
                    autor=d.nomes_partes[0] if d.nomes_partes else None,
                    reu=d.nomes_partes[1] if len(d.nomes_partes) > 1 else None,
                    data_distribuicao=data_dist,
                    resumo=resultado.observacoes_supervisor,
                )
                db.add(novo_processo)
                db.commit()
                db.refresh(novo_processo)
                response.processo_criado_id = novo_processo.id
                response.alertas.append(
                    f"Processo criado com sucesso (id={novo_processo.id})."
                )

        elif dados.salvar_processo and not resultado.aprovado:
            response.alertas.append(
                "Dados insuficientes para criar o processo automaticamente. "
                "Revise o documento e tente novamente."
            )

    return response


@router.post(
    "/upload-pdf",
    response_model=ProcessamentoResponse,
    summary="Upload e processamento de PDF juridico",
)
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Recebe um PDF, extrai texto e processa via pipeline multiagente."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos PDF sao aceitos.",
        )

    conteudo = await file.read()

    if len(conteudo) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo muito grande. Maximo: 10MB.",
        )

    try:
        texto_bruto = extrair_texto_pdf(conteudo)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PyPDF2 nao instalado. Execute: pip install PyPDF2",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    texto_limpo = limpar_texto_juridico(texto_bruto)

    supervisor = AgenteSupervisor()
    resultado = supervisor.processar_documento(texto_limpo)

    response = ProcessamentoResponse(
        aprovado=resultado.aprovado,
        score_qualidade=resultado.score_qualidade,
        observacoes_supervisor=resultado.observacoes_supervisor,
        alertas=resultado.alertas,
    )

    if resultado.dados_extraidos:
        d = resultado.dados_extraidos
        response.dados_extraidos = DadosExtraidosResponse(
            numero_cnj=d.numero_cnj,
            cpfs_encontrados=d.cpfs_encontrados,
            cnpjs_encontrados=d.cnpjs_encontrados,
            valores_monetarios=d.valores_monetarios,
            nomes_partes=d.nomes_partes,
            tribunal=d.tribunal,
            vara=d.vara,
            tipo_acao=d.tipo_acao,
            data_distribuicao=d.data_distribuicao,
            confianca=d.confianca,
        )

    response.alertas.insert(0, f"PDF '{file.filename}' processado ({len(texto_limpo)} caracteres).")

    return response
