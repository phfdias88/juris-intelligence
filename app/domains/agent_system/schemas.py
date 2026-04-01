"""
Schemas do dominio Agent System.

Define contratos para upload de documentos e respostas
do pipeline multiagente.
"""

from pydantic import BaseModel, Field


class DocumentoTextoRequest(BaseModel):
    """Entrada para processar texto juridico via pipeline multiagente."""
    texto: str = Field(
        ...,
        min_length=20,
        description="Texto bruto do documento juridico (copiado de PDF ou digitado).",
    )
    salvar_processo: bool = Field(
        default=False,
        description="Se True, cria automaticamente um Processo no banco com os dados extraidos.",
    )


class DadosExtraidosResponse(BaseModel):
    """Dados estruturados extraidos pelo AgenteExtrator."""
    numero_cnj: str | None = None
    cpfs_encontrados: list[str] = []
    cnpjs_encontrados: list[str] = []
    valores_monetarios: list[float] = []
    nomes_partes: list[str] = []
    tribunal: str | None = None
    vara: str | None = None
    tipo_acao: str | None = None
    data_distribuicao: str | None = None
    confianca: float = 0.0


class ProcessamentoResponse(BaseModel):
    """Resposta completa do pipeline multiagente."""
    aprovado: bool
    score_qualidade: float
    observacoes_supervisor: str
    alertas: list[str] = []
    dados_extraidos: DadosExtraidosResponse | None = None
    processo_criado_id: int | None = Field(
        default=None,
        description="ID do processo criado (se salvar_processo=True).",
    )


class UploadResponse(BaseModel):
    """Resposta do upload de PDF com task_id para rastreamento."""
    mensagem: str
    task_id: str
    status: str = "enviado"
