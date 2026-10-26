"""How to plug any proprietary or local LLM into EnergyChain."""
from energychain import CallableTextModel, EnergyChain


def my_llm(system: str, user: str, context: str) -> str:
    # Replace with a provider SDK or local LLM call; a genuine LLM is not bundled.
    return f"Prompt: {user}; available data: {context}"

chain = EnergyChain.demo()
p = chain.principal("developer", allowed_sites={"demo-site"})
agent = chain.agent(CallableTextModel(my_llm))
print(agent.run("What is my charge?", principal=p, site_id="demo-site",
                tool_name="get_battery_state", tool_arguments={"asset_id": "demo-battery"}).answer)
