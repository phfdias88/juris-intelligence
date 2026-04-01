"""Testes do motor de Litigation Finance (Pricing)."""

import pytest


def test_calcular_pricing_basico(client):
    resp = client.post("/api/v1/finance/calculate-pricing", json={
        "valor_pedido": 500000,
        "probabilidade_ganho": 0.65,
        "tempo_estimado_meses": 36,
        "taxa_retorno_anual_alvo": 0.20,
        "custas_estimadas": 30000,
    })
    assert resp.status_code == 200
    body = resp.json()

    # EV = (500000 * 0.65) - 30000 = 295000
    assert body["valor_esperado"] == 295000.0

    # PV = 295000 / (1.20)^3 = 170717.59
    assert abs(body["preco_maximo_compra"] - 170717.59) < 1

    assert body["lucro_projetado"] > 0
    assert body["nivel_risco"] == "MEDIO"
    assert body["margem_seguranca"] > 0
    assert "parametros" in body


def test_pricing_risco_baixo(client):
    resp = client.post("/api/v1/finance/calculate-pricing", json={
        "valor_pedido": 200000,
        "probabilidade_ganho": 0.85,
        "tempo_estimado_meses": 12,
        "taxa_retorno_anual_alvo": 0.15,
        "custas_estimadas": 10000,
    })
    assert resp.status_code == 200
    assert resp.json()["nivel_risco"] == "BAIXO"


def test_pricing_risco_alto(client):
    resp = client.post("/api/v1/finance/calculate-pricing", json={
        "valor_pedido": 100000,
        "probabilidade_ganho": 0.25,
        "tempo_estimado_meses": 48,
        "taxa_retorno_anual_alvo": 0.30,
        "custas_estimadas": 5000,
    })
    assert resp.status_code == 200
    assert resp.json()["nivel_risco"] == "ALTO"


def test_pricing_processo_inviavel(client):
    """Custas superam o retorno esperado — deve retornar 400."""
    resp = client.post("/api/v1/finance/calculate-pricing", json={
        "valor_pedido": 50000,
        "probabilidade_ganho": 0.10,
        "tempo_estimado_meses": 24,
        "taxa_retorno_anual_alvo": 0.20,
        "custas_estimadas": 40000,
    })
    assert resp.status_code == 400
    assert "inviavel" in resp.json()["detail"].lower()


def test_pricing_validacao_campos(client):
    """Valor negativo ou probabilidade fora do range."""
    resp = client.post("/api/v1/finance/calculate-pricing", json={
        "valor_pedido": -100,
        "probabilidade_ganho": 0.5,
        "tempo_estimado_meses": 12,
        "taxa_retorno_anual_alvo": 0.20,
        "custas_estimadas": 0,
    })
    assert resp.status_code == 422
