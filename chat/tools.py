from decimal import Decimal, ROUND_HALF_UP

from .models import Item

CENTS = Decimal("0.01")


def check_stock(name):
    """Look up how many of an item we have."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    return {"name": item.name, "quantity": item.quantity, "price": float(item.price)}


def list_items():
    """Return every item in the inventory."""
    items = Item.objects.all()
    return {
        "items": [
            {"name": i.name, "quantity": i.quantity, "price": float(i.price)}
            for i in items
        ]
    }


def add_item(name, quantity, price=None):
    """Create a new item, or add to an existing one's stock. Optionally set its unit price."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is not None:
        item.quantity += quantity
        if price is not None:
            item.price = Decimal(str(price))
        item.save()
        return {"name": item.name, "quantity": item.quantity, "price": float(item.price), "created": False}
    item = Item.objects.create(
        name=name,
        quantity=quantity,
        price=Decimal(str(price)) if price is not None else Decimal("0"),
    )
    return {"name": item.name, "quantity": item.quantity, "price": float(item.price), "created": True}


def set_price(name, price):
    """Set or change the unit price of an existing item."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    if price < 0:
        return {"error": "Price cannot be negative."}
    item.price = Decimal(str(price))
    item.save()
    return {"name": item.name, "price": float(item.price)}


def calculate_cost(name, quantity, vat_percent=0):
    """Work out the cost of some units of an item, with optional VAT added on top."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    if item.price <= 0:
        return {"error": f"'{item.name}' has no price set yet. Set a price first."}
    if quantity <= 0:
        return {"error": "Quantity must be positive."}

    unit_price = item.price
    subtotal = (unit_price * quantity).quantize(CENTS, ROUND_HALF_UP)
    vat_amount = (subtotal * Decimal(str(vat_percent)) / 100).quantize(CENTS, ROUND_HALF_UP)
    total = subtotal + vat_amount
    return {
        "name": item.name,
        "quantity": quantity,
        "unit_price": float(unit_price),
        "subtotal": float(subtotal),
        "vat_percent": vat_percent,
        "vat_amount": float(vat_amount),
        "total": float(total),
    }


def remove_stock(name, quantity):
    """Take a quantity out of stock."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    if quantity > item.quantity:
        return {
            "error": f"Cannot remove {quantity}. Only {item.quantity} in stock.",
            "name": item.name,
            "quantity": item.quantity,
        }
    item.quantity -= quantity
    item.save()
    return {"name": item.name, "quantity": item.quantity}


def delete_item(name):
    """Remove an item from the inventory entirely."""
    item = Item.objects.filter(name__iexact=name).first()
    if item is None:
        return {"error": f"No item named '{name}' exists in the inventory."}
    item.delete()
    return {"deleted": name}


TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "check_stock",
        "description": "Look up the current quantity and unit price of a single item in the inventory. Use this whenever the user asks whether something is in stock, how many there are, or what it costs per unit.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "list_items",
        "description": "Return every item in the inventory with its quantity and unit price. Use this when the user asks what is in stock generally, or asks for a list, rather than about one specific item.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "add_item",
        "description": "Add stock to the inventory. If the item does not exist it is created; if it already exists the quantity is added to the existing total. Use this for restocking and for new deliveries.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units to add. Must be positive.",
                },
                "price": {
                    "type": "number",
                    "description": "Optional unit price of the item, e.g. 2.50. Only include if the user gives a price.",
                },
            },
            "required": ["name", "quantity"],
        },
    },
    {
        "type": "function",
        "name": "set_price",
        "description": "Set or change the unit price of an item that already exists. Use this when the user wants to update a price without changing stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Chocolate bar'.",
                },
                "price": {
                    "type": "number",
                    "description": "The new unit price, e.g. 2.50. Must not be negative.",
                },
            },
            "required": ["name", "price"],
        },
    },
    {
        "type": "function",
        "name": "calculate_cost",
        "description": "Calculate the cost of a number of units of an item, optionally adding VAT/tax. ALWAYS use this for any question about cost, price totals or VAT. Never do the arithmetic yourself.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Chocolate bar'.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units the user wants priced. Must be positive.",
                },
                "vat_percent": {
                    "type": "number",
                    "description": "VAT/tax percentage to add, e.g. 10 for 10%. Use 0 if the user mentions no VAT.",
                },
            },
            "required": ["name", "quantity"],
        },
    },
    {
        "type": "function",
        "name": "remove_stock",
        "description": "Reduce the quantity of an existing item. Use this when items are sold, shipped or used. This does NOT delete the item; it only lowers the number.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the item, e.g. 'Hammer'.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units to remove. Must be positive.",
                },
            },
            "required": ["name", "quantity"],
        },
    },
    {
        "type": "function",
        "name": "delete_item",
        "description": "Permanently remove an item and its record from the inventory entirely. This is destructive. Only use it when the user clearly wants the item gone, not when they want to reduce its quantity.",
        "parameters": {
            "type": "object",
            "properties": {

                "name": {
                    "type": "string",
                    "description": "The name of the item to delete.",
                },
            },
            "required": ["name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "check_stock": check_stock,
    "list_items": list_items,
    "add_item": add_item,
    "set_price": set_price,
    "calculate_cost": calculate_cost,
    "remove_stock": remove_stock,
    "delete_item": delete_item,
}