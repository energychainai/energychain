"""Opt-in LIVE ModelGateway smoke test for EnergyIntelligence.

Examples:
  python scripts/verify_intelligence_provider.py --provider openai-compatible \
    --model openai/gpt-oss-20b --base-url https://api.groq.com/openai/v1 \
    --key-env GROQ_API_KEY

  python scripts/verify_intelligence_provider.py --provider openai \
    --model <a-model-available-to-your-account> --key-env OPENAI_API_KEY

No default provider, API key, or billing assumptions. Secrets are never printed.
"""
from __future__ import annotations

import argparse
import os
import sys

from energychain import EnergyChain, ModelGateway
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, format_console
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=ModelGateway.providers())
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--key-env", required=True,
                        help="Name of environment variable holding a private API key.")
    parser.add_argument("--check-planner", action="store_true",
                        help="Also test the model-proposed strict JSON tool plan.")
    args = parser.parse_args()

    key = os.environ.get(args.key_env)
    if not key and args.provider != "ollama":
        parser.error("Specified credential environment variable is not set.")
    try:
        gateway = ModelGateway(
            args.provider, args.model, base_url=args.base_url,
            api_key=key, timeout=30, max_retries=0,
        )
        sdk = EnergyChain.demo()
        user = sdk.principal("provider-smoke", allowed_sites={"demo-site"})
        engine = sdk.intelligence(model=gateway)
        plan = IntelligencePlan("model-smoke", 1, (
            ToolStep("load", "get_asset_state",
                     {"asset_id": "demo-load", "metric": "power_w"}),
        ))
        result = engine.run(
            task="Explain the synthetic office-load reading without inventing equipment data.",
            principal=user, site_id="demo-site", plan=plan,
            synthesize=True,
        )
        print(format_console(result))
        if result.interpretation_status != "generated_unverified":
            raise RuntimeError("Model synthesis failed")
        if args.check_planner:
            planned = engine.run(
                task="Read the current POWER_W value for asset demo-load using get_asset_state.",
                principal=user, site_id="demo-site",
                allowed_tools={"get_asset_state"},
                inputs={"asset_id": "demo-load"},
                synthesize=True,
            )
            print(format_console(planned))
            if planned.status != "completed" or not planned.evidence:
                raise RuntimeError("Planner did not execute verified energy tools")
        print("PASS: optional injected provider interoperated with EnergyIntelligence.")
        return 0
    except Exception as exc:
        print("FAIL: optional live model test; error class: " + type(exc).__name__,
              file=sys.stderr)
        # Never print exception strings or provider HTTP response bodies.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
