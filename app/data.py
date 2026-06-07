from __future__ import annotations

from copy import deepcopy
from typing import Any


CUSTOMERS: dict[str, dict[str, Any]] = {
    "12345678909": {
        "name": "Rogerio Silva",
        "email": "rogerio.silva@example.com",
        "orders": [
            {
                "id": "PED-1001",
                "item": "Smartphone Aurora X",
                "status": "Em transporte",
                "total": "R$ 2.499,90",
                "carrier": "Correios",
                "tracking_code": "BR123456789BR",
                "tracking_history": [
                    "Pedido aprovado",
                    "Nota fiscal emitida",
                    "Objeto postado",
                    "Em rota para o centro de distribuicao",
                ],
            },
            {
                "id": "PED-1002",
                "item": "Fone NoiseBlock Pro",
                "status": "Em separacao",
                "total": "R$ 399,90",
                "carrier": "Transportadora Flash",
                "tracking_code": "FLA-984512",
                "tracking_history": [
                    "Pedido aprovado",
                    "Pagamento confirmado",
                    "Produto em separacao no estoque",
                ],
            },
            {
                "id": "PED-1003",
                "item": "Cafeteira Smart Brew",
                "status": "Entregue",
                "total": "R$ 689,90",
                "carrier": "Loggi",
                "tracking_code": "LGG-778120",
                "tracking_history": [
                    "Pedido aprovado",
                    "Saiu para entrega",
                    "Entregue ao destinatario",
                ],
            },
        ],
    },
    "98765432100": {
        "name": "Marina Costa",
        "email": "marina.costa@example.com",
        "orders": [
            {
                "id": "PED-2001",
                "item": "Notebook Atlas 14",
                "status": "Aguardando pagamento",
                "total": "R$ 4.799,90",
                "carrier": "Ainda nao despachado",
                "tracking_code": "Indisponivel",
                "tracking_history": ["Pedido criado", "Aguardando confirmacao de pagamento"],
            }
        ],
    },
}


def load_customers() -> dict[str, dict[str, Any]]:
    """Return isolated in-memory data for the application or tests."""
    return deepcopy(CUSTOMERS)
