"""Testes do Agent System (pipeline multiagente)."""

import pytest


DOCUMENTO_JURIDICO = (
    "PODER JUDICIARIO - TJSP\n\n"
    "Processo n. 7654321-00.2025.8.26.0100\n\n"
    "AUTOR: Pedro Santos, CPF 987.654.321-00\n"
    "REU: Tech Solutions SA, CNPJ 98.765.432/0001-10\n\n"
    "ACAO DE INDENIZACAO\n\n"
    "Valor da causa: R$ 180.000,00\n"
    "Data de distribuicao: 20/06/2025\n\n"
    "Trata-se de relacao de consumo envolvendo defeito no servico prestado. "
    "O valor pago foi de R$ 35.000,00."
)


def test_processar_texto_completo(client):
    resp = client.post("/api/v1/agents/process-text", json={
        "texto": DOCUMENTO_JURIDICO,
        "salvar_processo": False,
    })
    assert resp.status_code == 200
    body = resp.json()

    assert body["aprovado"] is True
    assert body["score_qualidade"] >= 0.6
    assert body["dados_extraidos"] is not None

    dados = body["dados_extraidos"]
    assert dados["numero_cnj"] == "7654321-00.2025.8.26.0100"
    assert "987.654.321-00" in dados["cpfs_encontrados"]
    assert "98.765.432/0001-10" in dados["cnpjs_encontrados"]
    assert dados["tribunal"] == "TJSP"
    assert dados["tipo_acao"] == "consumidor"
    assert len(dados["valores_monetarios"]) >= 2


def test_processar_texto_curto(client):
    resp = client.post("/api/v1/agents/process-text", json={
        "texto": "Texto curto demais para extracao.",
        "salvar_processo": False,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["aprovado"] is False
    assert body["score_qualidade"] == 0.0


def test_processar_texto_com_salvamento(client):
    resp = client.post("/api/v1/agents/process-text", json={
        "texto": DOCUMENTO_JURIDICO,
        "salvar_processo": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["aprovado"] is True
    # Processo criado de forma sincrona — retorna o ID
    assert body["processo_criado_id"] is not None
    assert any("Processo criado" in a for a in body["alertas"])


def test_agente_extrator_isolado():
    """Testa o AgenteExtrator diretamente (sem HTTP)."""
    from app.domains.agent_system.agents import AgenteExtrator

    extrator = AgenteExtrator()
    resultado = extrator.executar(DOCUMENTO_JURIDICO)

    assert resultado.numero_cnj == "7654321-00.2025.8.26.0100"
    assert len(resultado.cpfs_encontrados) >= 1
    assert len(resultado.cnpjs_encontrados) >= 1
    assert len(resultado.valores_monetarios) >= 2
    assert resultado.tribunal == "TJSP"
    assert resultado.confianca >= 0.8


def test_agente_analista_isolado():
    """Testa o AgenteAnalistaLogico diretamente."""
    from app.domains.agent_system.agents import AgenteAnalistaLogico

    analista = AgenteAnalistaLogico()

    # Depoimento com incertezas
    resultado = analista.executar(
        "Acho que talvez eu tenha visto algo, nao me lembro direito.",
        textos_anteriores=[],
    )
    assert len(resultado.incertezas) >= 2
    assert resultado.score_confiabilidade < 0.9

    # Depoimento com contradicao
    resultado2 = analista.executar(
        "Eu nao estava presente e nao consegui ver nada.",
        textos_anteriores=[
            {"nome": "Testemunha A", "texto": "Eu estava presente e vi claramente o ocorrido."}
        ],
    )
    assert len(resultado2.contradicoes) >= 1


def test_supervisor_isolado():
    """Testa o AgenteSupervisor com pipeline completo."""
    from app.domains.agent_system.agents import AgenteSupervisor

    supervisor = AgenteSupervisor()
    resultado = supervisor.processar_documento(DOCUMENTO_JURIDICO)

    assert resultado.aprovado is True
    assert resultado.score_qualidade >= 0.6
    assert resultado.dados_extraidos is not None
    assert resultado.dados_extraidos.numero_cnj is not None
