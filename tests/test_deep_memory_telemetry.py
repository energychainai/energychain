from datetime import datetime, timedelta, timezone
import pytest
from energychain import (EnergyChain, EnergyEpisode, InMemoryEpisodeStore,
                         SQLiteEpisodeStore, EnergyReading,
                         Metric, EnergyEvent)
from energychain.exceptions import PermissionDenied, ValidationError, StaleReading
from energychain.models import utcnow


def test_episodes_site_scope_search_and_persistence(tmp_path):
    stamp=datetime(2026,10,26,12,tzinfo=timezone.utc)
    for store in (InMemoryEpisodeStore(), SQLiteEpisodeStore(tmp_path/"episodes.sqlite")):
        store.add(EnergyEpisode("outage","site-a","outage","Solar was lost",stamp,
                                ("solar",),"recovered",("event-1",)))
        store.add(EnergyEpisode("outage","site-b","outage","Solar was lost",stamp))
        assert len(store.recall("site-a","solar"))==1
        assert len(store.recall("site-b","recovered"))==0
        assert len(store.recall("site-b"))==1
        store.delete_site("site-b")
        assert store.recall("site-b")==[]
        if isinstance(store, SQLiteEpisodeStore):
            store.close()
            reopened=SQLiteEpisodeStore(tmp_path/"episodes.sqlite")
            assert reopened.recall("site-a")[0].evidence==("event-1",)
            reopened.close()


def test_context_builder_does_not_leak_sites():
    chain=EnergyChain.demo()
    chain.episodes.add(EnergyEpisode("a","demo-site","event","Low battery"))
    chain.episodes.add(EnergyEpisode("a","other-site","event","Private note"))
    chain.memory.set_preference("other-site","secret","do-not-expose")
    data=chain.context.build("demo-site",query="battery")
    assert len(data.episodes)==1 and "secret" not in data.preferences
    with pytest.raises(ValidationError):
        chain.context.build("demo-site",metric="power_w")


def test_telemetry_rejects_cross_site_and_deduplicates():
    chain=EnergyChain.demo()
    now=utcnow()
    reading=EnergyReading("demo-solar",Metric.POWER_W,250,now,"test",quality="measured")
    first=chain.telemetry.ingest("demo-site",reading,source_event_id="id-1")
    second=chain.telemetry.ingest("demo-site",reading,source_event_id="id-1")
    assert first.accepted and second.duplicate
    with pytest.raises(PermissionDenied):
        chain.telemetry.ingest("other-site",reading,source_event_id="id-2")
    old=EnergyReading("demo-solar",Metric.POWER_W,250,now-timedelta(days=100),"test")
    with pytest.raises(StaleReading):
        chain.telemetry.ingest("demo-site",old,source_event_id="id-3")


def test_event_bus_is_bounded_and_handles_bad_subscriber():
    chain=EnergyChain.demo()
    bad=chain.events.subscribe(lambda e:1/0)
    hits=[]
    good=chain.events.subscribe(hits.append)
    event=EnergyEvent("id","demo-site","warning","Battery low")
    assert chain.events.publish(event)==1
    assert hits==[event]
    chain.events.unsubscribe(good)
    assert chain.events.publish(event)==0
    assert len(chain.events.recent("demo-site"))==2
