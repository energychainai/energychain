"""Fully offline document retrieval with no model account or API key."""
from pathlib import Path
from tempfile import TemporaryDirectory
from energychain import EnergyKnowledgeBase, Principal, Permission

with TemporaryDirectory() as folder:
    root = Path(folder)
    manual = root / "battery.txt"
    manual.write_text("Nominal battery 12 kWh. Maximum current 40 A.", encoding="utf-8")
    person = Principal("developer", frozenset({"site-1"}),
                       frozenset({Permission.READ, Permission.PREPARE}))
    index = EnergyKnowledgeBase(root / "knowledge.sqlite", tenant_id="demo", allowed_root=root)
    index.ingest_file(manual, site_id="site-1", principal=person)
    for hit in index.search("battery current", site_id="site-1", principal=person):
        print(hit.citation, hit.energy_facts, hit.text)
