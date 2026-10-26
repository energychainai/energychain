import pytest
from energychain import (EnergySite, EnergyAsset, AssetKind, Capability,
                         EnergyActionSpec, EnergyConstraint, SignedApprovalAuthority,
                         Principal, Permission, SafetyPolicy, ToolRegistry, ToolSpec,
                         Approval, EnergyRelationship, EnergyTopology, RelationshipKind)
from energychain.connectors import EnergyConnector
from energychain.exceptions import (ApprovalRequired,
                                    ValidationError, UnsupportedCapability, ToolError)


class ToyPhysicalConnector(EnergyConnector):
    """Test-only, no physical network/actuator."""
    def __init__(self):
        self.site = EnergySite("test-site", "Test")
        self.asset = EnergyAsset("heater", "test-site", "Heater", AssetKind.LOAD,
                                 frozenset({Capability.READ, Capability.EXECUTE}))
        self.calls = 0
    def sites(self):
        return [self.site]
    def assets(self, site_id):
        return [self.asset] if site_id == self.site.id else []
    def read(self, asset_id, metric):
        raise UnsupportedCapability("no sensor")
    def history(self, asset_id, metric, start, end):
        return []
    def execute(self, asset_id, command, parameters):
        self.calls += 1
        return {"accepted": True}  # NOT proof of physical execution


def test_signed_approval_bound_to_arguments_and_single_use():
    authority=SignedApprovalAuthority(b"2"*32)
    policy=SafetyPolicy(approval_authority=authority)
    registry=ToolRegistry(policy=policy)
    registry.register(ToolSpec("operate", "Test-only", Permission.EXECUTE,
                               lambda *, site_id, kw: kw))
    user=Principal("u",frozenset({"a"}),frozenset({Permission.EXECUTE}))
    tok=authority.issue(user,"a","operate",{"kw":3})
    with pytest.raises(ApprovalRequired):
        registry.invoke("operate",user,"a",arguments={"kw":4},approval=tok)
    assert registry.invoke("operate",user,"a",arguments={"kw":3},approval=tok)==3
    with pytest.raises(ApprovalRequired):
        registry.invoke("operate",user,"a",arguments={"kw":3},approval=tok)


def test_forged_simple_approval_is_denied():
    tools=ToolRegistry()
    tools.register(ToolSpec("activate","test",Permission.EXECUTE,lambda *,site_id:"should not happen"))
    user=Principal("person",frozenset({"s"}),frozenset({Permission.EXECUTE}))
    with pytest.raises(ApprovalRequired):
        tools.invoke("activate",user,"s",approval=Approval("person","s","activate",True))
    tools.register(ToolSpec("read", "test", Permission.READ, lambda *, site_id: site_id))
    viewer = Principal("person", frozenset({"s"}), frozenset({Permission.READ}))
    with pytest.raises(ToolError):
        tools.invoke("read", viewer, "s", arguments={"principal":"injected"})


def test_action_service_default_off_and_protected_dispatch():
    from energychain import ActionService
    from energychain.connectors import ConnectorRegistry
    reg=ConnectorRegistry()
    adapter=ToyPhysicalConnector()
    reg.register("toy",adapter)
    authority=SignedApprovalAuthority(b"3"*32)
    policy=SafetyPolicy(approval_authority=authority)
    service=ActionService(reg,policy=policy)
    service.declare(EnergyActionSpec("heater","set_power",(EnergyConstraint("power_w",0,1000,"W"),)))
    user=Principal("owner",frozenset({"test-site"}),frozenset({Permission.PREPARE,Permission.EXECUTE}))
    with pytest.raises(ValidationError):
        service.prepare(user,"test-site","heater","set_power",{"power_w":2000})
    plan=service.prepare(user,"test-site","heater","set_power",{"power_w":250})
    with pytest.raises(TypeError):
        plan.parameters["power_w"]=300
    with pytest.raises(UnsupportedCapability):
        service.dispatch(plan.id,user)
    assert adapter.calls == 0
    active=ActionService(reg,policy=policy,enable_physical_dispatch=True)
    active.declare(EnergyActionSpec("heater","set_power",(EnergyConstraint("power_w",0,1000,"W"),)))
    proposed=active.prepare(user,"test-site","heater","set_power",{"power_w":300})
    signature=authority.issue(user,"test-site",f"dispatch:set_power:{proposed.id}",
                              {"asset":"heater","power_w":300})
    result=active.dispatch(proposed.id,user,approval=signature)
    assert adapter.calls==1 and result.status=="unverified" and not result.confirmed
    with pytest.raises(ValidationError):
        active.dispatch(proposed.id,user,approval=signature)


def test_topology_and_constraints_fail_closed():
    a=EnergyAsset("a","site","A",AssetKind.SOLAR)
    b=EnergyAsset("b","site","B",AssetKind.LOAD)
    top=EnergyTopology("site",(EnergyRelationship("site","a","b",RelationshipKind.FEEDS),))
    top.validate([a,b])
    with pytest.raises(ValidationError):
        top.validate([a])
    assert not EnergyConstraint("reserve",20,90,"%").check(True)
