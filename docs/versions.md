# Documentation versions

Select the documentation version that matches your installed EnergyChain package.
Check it with:

```bash
python -c "import energychain; print(energychain.__version__)"
```

| Documentation | Release scope |
| --- | --- |
| [v0.4.0](https://energychain.app/docs/0.4.0/) | Current alpha: EnergyIntelligence plans, dependent tool outputs, evidence, replay and event integration |
| [v0.3.0](https://energychain.app/docs/0.3.0/) | Model Gateway and Document Intelligence, plus the v0.2 SDK |
| [v0.2.0](https://energychain.app/docs/0.2.0/) | Fleets, episodic memory, read-only integrations, bounded planning, approvals and checkpoints |
| [v0.1.0](https://energychain.app/docs/0.1.0/) | Core models, simulator/CSV connectors, tools, memory, explicit agents and sequential workflows |

The selector preserves the current topic when the destination release contains
it. A topic introduced later displays an availability notice instead of showing
newer APIs under an older version. Search covers only the selected version.
Unversioned `/docs/` links open the current release; versioned links remain pinned.

Archived pages describe the corresponding tagged source. Their installation
commands are pinned to that release, and source links identify its exact commit.
The v0.3.0 README's mistaken v0.2.0 installation pin is corrected in the rendered
archive. Historical development and publication statements are retained only in
their historical context, rather than asserted as current project status.

Every release is an MIT-licensed, Python 3.10+ alpha with physical dispatch
disabled by default. Selecting an older version is not a recommendation to use
it for equipment control. See [upgrading](upgrading.md) for migration guidance.
