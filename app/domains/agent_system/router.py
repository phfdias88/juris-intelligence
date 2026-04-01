"""
Router do dominio Agent System.

Endpoints para processamento de documentos juridicos via pipeline
multiagente (Extrator + Analista Logico + Supervisor).

Suporta:
- Upload de texto direto (sincrono para textos curtos)
- Upload de PDF (assincrono via Celery para arquivos grandes)
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.domains.agent_system.agents import AgenteSupervisor
from app.domains.agent_system.schemas import (
    DocumentoTextoRequest,
    DadosExtraidosResponse,
    ProcessamentoResponse,
    UploadResponse,
)
from app.domains.agent_system.tools import extrair_texto_pdf, limpar_texto_juridico
from app.worker.tasks import processar_documento_pipeline_task

router = APIRouter(prefix="/agents", tags=["Agent System"])


@router.post(
    "/process-text",
    response_model=ProcessamentoResponse,
    summary="Processar texto juridico via pipeline multiagente",
    description=(
        "Recebe texto bruto de um documento juridico e processa "
        "pelo pipeline: AgenteExtrator → AgenteSupervisor. "
        "Extrai CNJ, CPFs, valores e classifica o tipo de acao."
    ),
)
def processar_texto(dados: DocumentoTextoRequest):
    """Processa texto juridico de forma sincrona (ideal para textos curtos).

    Para documentos grandes ou uploads de PDF, use o endpoint
    POST /agents/upload-pdf que processa via Celery.
    """
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

    # Se solicitou salvar, dispara via Celery (pode precisar do banco)
    if dados.salvar_processo:
        task = processar_documento_pipeline_task.delay(
            texto=dados.texto, salvar_processo=True
        )
        response.processo_criado_id = None  # Sera preenchido async
        response.alertas.append(
            f"Criacao de processo disparada em background. Task ID: {task.id}"
        )

    return response


@router.post(
    "/upload-pdf",
    response_model=ProcessamentoResponse,
    summary="Upload e processamento de PDF juridico",
    description=(
        "Faz upload de um arquivo PDF, extrai o texto e processa "
        "pelo pipeline multiagente. Retorna dados estruturados."
    ),
)
async def upload_pdf(file: UploadFile = File(...)):
    """Recebe um PDF, extrai texto e processa via pipeline multiagente.

    Limitacoes do MVP:
    - Apenas PDFs com texto selecionavel (nao escaneados/imagem)
    - Tamanho maximo recomendado: 10MB
    - Para PDFs escaneados, sera necessario OCR (Tesseract) no futuro
    """
    # Validar tipo de arquivo
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos PDF sao aceitos.",
        )

    # Ler conteudo
    conteudo = await file.read()

    if len(conteudo) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo muito grande. Maximo: 10MB.",
        )

    # Extrair texto do PDF
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

    # Limpar texto
    texto_limpo = limpar_texto_juridico(texto_bruto)

    # Processar via pipeline
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
