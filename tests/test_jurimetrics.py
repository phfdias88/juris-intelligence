"""Testes do dominio de Jurimetria Preditiva."""

import pytest


@pytest.fixture()
def processo_id(client, cnj_unico):
    """Cria um processo e retorna o ID."""
    resp = client.post("/api/v1/processos/", json={
        "numero_cnj": cnj_unico,
        "tribunal": "TJSP",
        "valor_causa": 200000,
        "tipo_acao": "trabalhista",
        "juiz_responsavel": "Ana Santos",
    })
    return resp.json()["id"]


def test_predizer_pedido(client, processo_id):
    resp = client.post("/api/v1/jurimetrics/predict", json={
        "processo_id": processo_id,
        "tipo_pedido": "horas_extras",
        "valor_pedido": 50000,
        "juiz_responsavel": "Ana Santos",
    })
    assert resp.status_code == 201
    body = resp.json()

    assert 0 < body["probabilidade_deferimento"] <= 1
    assert body["nivel_confianca"] == "ALTO"
    assert body["valor_estimado"] is not None
    assert "fundamentacao_ia" in body


def test_predizer_pedido_sem_juiz(client, processo_id):
    resp = client.post("/api/v1/jurimetrics/predict", json={
        "processo_id": processo_id,
        "tipo_pedido": "danos_morais",
        "valor_pedido": 30000,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert 0 < body["probabilidade_deferimento"] <= 1


def test_predizer_pedido_processo_inexistente(client):
    resp = client.post("/api/v1/jurimetrics/predict", json={
        "processo_id": 99999,
        "tipo_pedido": "danos_morais",
        "valor_pedido": 10000,
    })
    assert resp.status_code == 404


def test_score_consolidado(client, processo_id):
    client.post("/api/v1/jurimetrics/predict", json={
        "processo_id": processo_id,
        "tipo_pedido": "horas_extras",
        "valor_pedido": 50000,
    })
    client.post("/api/v1/jurimetrics/predict", json={
        "processo_id": processo_id,
        "tipo_pedido": "danos_morais",
        "valor_pedido": 30000,
    })

    resp = client.get(f"/api/v1/jurimetrics/processos/{processo_id}/score")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_pedidos"] >= 2
    assert 0 < body["probabilidade_ganho_consolidada"] <= 1
    assert body["nivel_risco_geral"] in ("BAIXO", "MEDIO", "ALTO")
    assert len(body["pedidos"]) >= 2


def test_score_consolidado_sem_pedidos(client, cnj_unico):
    resp = client.post("/api/v1/processos/", json={
        "numero_cnj": cnj_unico,
        "tribunal": "TJRJ",
        "valor_causa": 100000,
    })
    pid = resp.json()["id"]

    resp = client.get(f"/api/v1/jurimetrics/processos/{pid}/score")
    assert resp.status_code == 200
    assert resp.json()["total_pedidos"] == 0
    assert resp.json()["nivel_risco_geral"] == "INDETERMINADO"
