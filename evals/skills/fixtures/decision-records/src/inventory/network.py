from inventory import ui


def fetch_stock(client, sku: str) -> int:
    try:
        return client.get(f"/stock/{sku}")["count"]
    except ConnectionError as error:
        ui.show_error(f"Warehouse unavailable: {error}")
        return 0
