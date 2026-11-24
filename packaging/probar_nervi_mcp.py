# SPDX-License-Identifier: GPL-3.0-or-later
"""Prueba de humo de ``nervi-mcp`` empaquetado, como lo usaría una app de IA.

Uso: ``python packaging/probar_nervi_mcp.py dist/Nervi/nervi-mcp``. Lo lanza sin
argumentos (modo ventana, sin ventana abierta), le habla por stdio con JSON-RPC y
comprueba que responda ``initialize`` y ``tools/list`` y que, sin ventana, explique
cómo conectarla.
"""

import json
import subprocess
import sys


def main(comando: list[str]) -> None:
    proceso = subprocess.Popen(
        comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    def enviar(mensaje: dict) -> None:
        proceso.stdin.write(json.dumps(mensaje) + "\n")
        proceso.stdin.flush()

    def rpc(id_: int, metodo: str, params: dict | None = None) -> dict:
        enviar({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}})
        while True:
            linea = proceso.stdout.readline()
            if not linea:
                raise SystemExit("nervi-mcp no respondió: " + proceso.stderr.read())
            respuesta = json.loads(linea)
            if respuesta.get("id") == id_:
                return respuesta

    cliente = {"name": "prueba-de-humo", "version": "0"}
    inicio = rpc(
        1,
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": cliente},
    )
    assert inicio["result"]["serverInfo"]["name"] == "nervi", inicio
    enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
    nombres = [t["name"] for t in rpc(2, "tools/list")["result"]["tools"]]
    assert "leer_nudo" in nombres and "proponer_modelo" in nombres, nombres
    sin_ventana = rpc(3, "tools/call", {"name": "resumen_proyecto", "arguments": {}})["result"]
    assert sin_ventana["isError"], sin_ventana
    assert "Conectar con mi IA" in sin_ventana["content"][0]["text"], sin_ventana
    proceso.stdin.close()
    proceso.wait(timeout=10)
    print(f"nervi-mcp responde: {len(nombres)} herramientas")


if __name__ == "__main__":
    main(sys.argv[1:])
