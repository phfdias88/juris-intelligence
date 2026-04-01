"""Testes do CRUD de Processos."""

import pytest


@pytest.fixture()
def processo_data(cnj_unico):
    return {
        "numero_cnj": cnj_unico,
        "tribunal": "TJSP",
        "vara": "2a Vara Civel",
        "comarca": "Sao Paulo",
        "tipo_acao": "consumidor",
        "valor_causa": 150000,
        "autor": "Joao Silva",
        "reu": "Empresa ABC",
    }


def test_criar_processo(client, processo_data):
    resp = client.post("/api/v1/processos/", json=processo_data)
    assert resp.status_code == 201
    body = resp.json()
    assert body["numero_cnj"] == processo_data["numero_cnj"]
    assert body["status"] == "ativo"
    assert body["id"] >= 1


def test_criar_processo_cnj_duplicado(client, cnj_unico):
    data = {"numero_cnj": cnj_unico, "tribunal": "TJSP", "valor_causa": 100000}
    client.post("/api/v1/processos/", json=data)
    resp = client.post("/api/v1/processos/", json=data)
    assert resp.status_code == 409


def test_listar_processos(client, processo_data):
    client.post("/api/v1/processos/", json=processo_data)
    resp = client.get("/api/v1/processos/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_buscar_processo_por_id(client, processo_data):
    criado = client.post("/api/v1/processos/", json=processo_data).json()
    resp = client.get(f"/api/v1/processos/{criado['id']}")
    assert resp.status_code == 200
    assert resp.json()["numero_cnj"] == processo_data["numero_cnj"]


def test_buscar_processo_inexistente(client):
    resp = client.get("/api/v1/processos/99999")
    assert resp.status_code == 404


def test_atualizar_processo(client, processo_data):
    criado = client.post("/api/v1/processos/", json=processo_data).json()
    resp = client.patch(
        f"/api/v1/processos/{criado['id']}",
        json={"tribunal": "TJRJ", "resumo": "Caso atualizado"},
    )
    assert resp.status_code == 200
    assert resp.json()["tribunal"] == "TJRJ"


def test_deletar_processo(client, processo_data):
    criado = client.post("/api/v1/processos/", json=processo_data).json()
    resp = client.delete(f"/api/v1/processos/{criado['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/processos/{criado['id']}")
    assert resp.status_code == 404
