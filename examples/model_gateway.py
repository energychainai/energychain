"""Use a provider account with appropriate permissions and billing."""
from energychain import ModelGateway

gateway = ModelGateway("openai", "gpt-4o-mini")
result = gateway.complete(
    system="Extract stated values; do not authorize device controls.",
    user="Return rated energy as JSON.",
    context="Unverified specification: rated battery energy 10 kWh.",
    json_schema={
        "type": "object",
        "properties": {"energy_kwh": {"type": "number"}},
        "required": ["energy_kwh"],
        "additionalProperties": False,
    },
)
print(result.json_value, result.usage)
