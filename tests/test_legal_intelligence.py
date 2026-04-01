"""Testes do dominio de Inteligencia Legal (Depoimentos + Contradicoes)."""

import pytest


@pytest.fixture()
def processo_id(client, cnj_unico):
    resp = client.post("/api/v1/processos/", json={
        "numero_cnj": cnj_unico,
        "tribunal": "TJSP",
        "valor_causa": 100000,
    })
    return resp.json()["id"]


def test_registrar_depoimento(client, processo_id):
    resp = client.post(f"/api/v1/legal/processos/{processo_id}/depoimentos", json={
        "processo_id": processo_id,
        "testemunha_nome": "Carlos Silva",
        "texto_depoimento": "Eu estava presente no local e vi claramente o que aconteceu naquele dia.",
    })
    assert resp.status_code == 202
    body = resp.json()

    assert body["testemunha_nome"] == "Carlos Silva"
    # Em modo eager, a task roda sincronamente — status deve ser concluido
    assert body["status_analise"] in ("concluido", "pendente")
    assert body["celery_task_id"] is not None


def test_detectar_contradicoes(client, processo_id):
    # Primeiro depoimento
    client.post(f"/api/v1/legal/processos/{processo_id}/depoimentos", json={
        "processo_id": processo_id,
        "testemunha_nome": "Testemunha A",
        "texto_depoimento": "Eu estava presente no momento dos fatos e vi claramente que o produto estava com defeito.",
    })

    # Segundo — contradiz o primeiro
    resp = client.post(f"/api/v1/legal/processos/{processo_id}/depoimentos", json={
        "processo_id": processo_id,
        "testemunha_nome": "Testemunha B",
        "texto_depoimento": "Acho que nao estava presente naquele momento. Nao consegui ver nada. Talvez o produto estivesse bom.",
    })
    assert resp.status_code == 202
    body = resp.json()

    # Consultar resultado via GET (pode ter processado eager)
    dep_resp = client.get(f"/api/v1/legal/depoimentos/{body['id']}")
    assert dep_resp.status_code == 200


def test_listar_depoimentos(client, processo_id):
    client.post(f"/api/v1/legal/processos/{processo_id}/depoimentos", json={
        "processo_id": processo_id,
        "testemunha_nome": "Ana",
        "texto_depoimento": "Depoimento de teste com conteudo suficiente para analise completa.",
    })

    resp = client.get(f"/api/v1/legal/processos/{processo_id}/depoimentos")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_buscar_depoimento_por_id(client, processo_id):
    criado = client.post(f"/api/v1/legal/processos/{processo_id}/depoimentos", json={
        "processo_id": processo_id,
        "testemunha_nome": "Maria",
        "texto_depoimento": "Eu confirmo que presenciei os fatos conforme relatado pelo autor da acao.",
    }).json()

    resp = client.get(f"/api/v1/legal/depoimentos/{criado['id']}")
    assert resp.status_code == 200
    assert resp.json()["testemunha_nome"] == "Maria"


def test_depoimento_processo_inexistente(client):
    resp = client.post("/api/v1/legal/processos/99999/depoimentos", json={
        "processo_id": 99999,
        "testemunha_nome": "Ninguem",
        "texto_depoimento": "Este depoimento nao deveria ser aceito pois o processo nao existe.",
    })
    assert resp.status_code == 404
