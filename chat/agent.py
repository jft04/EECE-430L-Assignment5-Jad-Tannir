import json
import os
import time

from google import genai
from google.genai import errors

from .tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """You are an inventory assistant for a small hardware warehouse.

You help the user check and update stock and prices by calling the tools available to you.

Rules:
- Always use a tool to answer questions about stock or prices. Never guess or rely on memory.
- For any question about cost, totals or VAT, call calculate_cost. Never do the arithmetic yourself.
- When answering a cost question, show the unit price, subtotal, VAT amount and total.
- If a tool returns an error, explain the problem to the user in plain language.
- Before deleting an item entirely, make sure that is what the user meant.
- Keep your answers short and factual.
- Do not answer any question unrelated to the inventory task.
"""

MAX_STEPS = 5

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def create_with_retry(**kwargs):
    """Call the API, retrying a few times on temporary 503 (overloaded) errors."""
    for attempt in range(3):
        try:
            return client.interactions.create(**kwargs)
        except errors.APIError as e:
            if e.code == 503 and attempt < 2:
                time.sleep(2 ** attempt)  # wait 1s, then 2s
                continue
            if e.code == 429:
                raise RuntimeError(
                    "Gemini rate limit reached (free tier allows 20 requests per day). "
                    "Please try again later or enable billing on your API key."
                ) from e
            raise


def clean_tool_name(raw_name):
    """The model sometimes returns 'default_api:list_items' instead of 'list_items'."""
    return raw_name.split(":")[-1]


def run_agent(user_message, previous_interaction_id=None, verbose=False):
    """Send a message to the agent and run tools until it produces an answer."""

    interaction = create_with_retry(
        model=MODEL,
        input=user_message,
        tools=TOOL_DECLARATIONS,
        system_instruction=SYSTEM_PROMPT,
        previous_interaction_id=previous_interaction_id,
    )

    for _ in range(MAX_STEPS):
        calls = [s for s in interaction.steps if s.type == "function_call"]

        if not calls:
            return interaction.output_text, interaction.id

        results = []
        for call in calls:
            name = clean_tool_name(call.name)
            function = TOOL_FUNCTIONS.get(name)

            if function is None:
                output = {"error": f"Unknown tool '{call.name}'."}
            else:
                output = function(**call.arguments)

            if verbose:
                print(f"  -> {name}({call.arguments}) = {output}")

            results.append({
                "type": "function_result",
                "name": name,
                "call_id": call.id,
                "result": [{"type": "text", "text": json.dumps(output)}],
            })

        interaction = create_with_retry(
            model=MODEL,
            input=results,
            tools=TOOL_DECLARATIONS,
            system_instruction=SYSTEM_PROMPT,
            previous_interaction_id=interaction.id,
        )

    return "I got stuck working on that. Please try rephrasing.", interaction.id