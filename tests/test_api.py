import pytest


def anotar(client, cliente="Zé", valor="12.50", descricao="2 brahmas"):
    resp = client.post(
        "/api/fiados", json={"cliente": cliente, "valor": valor, "descricao": descricao}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_pagina_inicial(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Caderninho do Fiado" in resp.text


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["db"] is True


def test_health_sem_banco(client, repo, monkeypatch):
    monkeypatch.setattr(repo, "ping", lambda: False)
    assert client.get("/api/health").status_code == 503


def test_anotar_e_listar(client):
    fiado = anotar(client)
    assert fiado["cliente"] == "Zé"
    assert fiado["pago_em"] is None
    assert [f["id"] for f in client.get("/api/fiados").json()] == [fiado["id"]]


@pytest.mark.parametrize(
    "payload",
    [
        {"cliente": "Zé", "valor": "-5"},
        {"cliente": "Zé", "valor": "0"},
        {"cliente": "Zé", "valor": "1.999"},
        {"cliente": "   ", "valor": "5"},
        {"valor": "5"},
    ],
)
def test_anotar_invalido(client, payload):
    assert client.post("/api/fiados", json=payload).status_code == 422


def test_pagar(client):
    fiado = anotar(client)
    resp = client.post(f"/api/fiados/{fiado['id']}/pagar")
    assert resp.status_code == 200
    assert resp.json()["pago_em"] is not None
    assert client.get("/api/fiados?pendentes=true").json() == []


def test_pagar_duas_vezes(client):
    fiado = anotar(client)
    client.post(f"/api/fiados/{fiado['id']}/pagar")
    assert client.post(f"/api/fiados/{fiado['id']}/pagar").status_code == 409


def test_pagar_inexistente(client):
    assert client.post("/api/fiados/999/pagar").status_code == 404


def test_ranking_soma_so_pendentes(client):
    anotar(client, "Zé", "10.00")
    anotar(client, "Zé", "5.50")
    pago = anotar(client, "Tião", "100.00")
    anotar(client, "Tião", "3.00")
    client.post(f"/api/fiados/{pago['id']}/pagar")

    ranking = client.get("/api/ranking").json()

    assert [(d["cliente"], d["total"], d["quantidade"]) for d in ranking] == [
        ("Zé", "15.50", 2),
        ("Tião", "3.00", 1),
    ]


def test_rota_de_debug_desligada_por_padrao(client):
    assert client.get("/api/debug/erro").status_code == 404
