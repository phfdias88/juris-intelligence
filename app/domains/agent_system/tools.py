"""
Tools (ferramentas) disponiveis para os agentes.

Cada tool e uma funcao utilitaria que os agentes podem usar.
Em producao com LangChain, estas serao registradas como Tools
do framework para que o LLM possa invoca-las dinamicamente.

TODO(LLM): Converter cada funcao em LangChain Tool:
    from langchain.tools import tool

    @tool
    def extrair_texto_pdf(caminho: str) -> str:
        ...
"""

import io
import logging
import re

logger = logging.getLogger(__name__)


def extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """Extrai texto de um arquivo PDF em formato bytes.

    Tenta usar PyPDF2 se disponivel, senao retorna erro informativo.
    Em producao, pode ser complementado com OCR (Tesseract) para
    PDFs escaneados.

    Args:
        conteudo_bytes: Conteudo binario do arquivo PDF.

    Returns:
        Texto extraido do PDF.

    Raises:
        ImportError: Se PyPDF2 nao estiver instalado.
        ValueError: Se o PDF estiver corrompido ou vazio.
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ImportError(
            "PyPDF2 nao instalado. Execute: pip install PyPDF2"
        )

    try:
        reader = PdfReader(io.BytesIO(conteudo_bytes))
    except Exception as e:
        raise ValueError(f"Erro ao ler PDF: {e}")

    if len(reader.pages) == 0:
        raise ValueError("PDF vazio: nenhuma pagina encontrada.")

    texto_completo = []
    for i, page in enumerate(reader.pages):
        texto_pagina = page.extract_text()
        if texto_pagina:
            texto_completo.append(texto_pagina)

    texto_final = "\n".join(texto_completo).strip()

    if not texto_final:
        raise ValueError(
            "Nenhum texto extraido do PDF. O documento pode ser escaneado "
            "(imagem). Considere usar OCR (Tesseract)."
        )

    logger.info(f"PDF processado: {len(reader.pages)} paginas, {len(texto_final)} caracteres.")
    return texto_final


def limpar_texto_juridico(texto: str) -> str:
    """Limpa e normaliza texto extraido de PDFs juridicos.

    Remove artefatos comuns de extracao de PDF como:
    - Quebras de linha no meio de palavras
    - Espacos multiplos
    - Caracteres de controle
    - Numeracao de paginas
    """
    # Remover caracteres de controle
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)

    # Juntar palavras quebradas por hifenizacao de PDF
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)

    # Substituir quebras de linha simples por espaco
    # (manter paragrafos com dupla quebra)
    texto = re.sub(r"(?<!\n)\n(?!\n)", " ", texto)

    # Remover espacos multiplos
    texto = re.sub(r" {2,}", " ", texto)

    # Remover numeracao de pagina isolada
    texto = re.sub(r"\n\s*\d+\s*\n", "\n", texto)

    return texto.strip()
