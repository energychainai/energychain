"""EnergyChain — composable developer infrastructure for intelligent energy apps."""
from .client import EnergyChain
from .models import (AssetKind, Capability, Metric, EnergySite, EnergyAsset, EnergyReading,
                     EnergyEvent, EnergyPlan, Tariff)
from .security import Permission, Principal, SafetyPolicy, Approval
from .intelligence import (RuntimeEstimate, estimate_battery_runtime, estimate_energy_cost,
                           simple_average_forecast, detect_outliers)
from .agents import EnergyAgent, AgentResponse, TextModel, CallableTextModel
from .connectors import EnergyConnector, ConnectorRegistry, HybridSiteSimulator, CSVConnector
from .memory import EnergyMemory, InMemoryEnergyMemory, SQLiteEnergyMemory, MemoryNote
from .tools import ToolRegistry, ToolSpec
from .workflows import EnergyWorkflow, WorkflowStep, WorkflowResult

from .fleets import Fleet, FleetManager, FleetSnapshot, FleetFailure
from .models import (EnergyConstraint, EnergyActionSpec, EnergyRelationship,
                     EnergyTopology, RelationshipKind, require_fresh)
from .actions import ActionService, PreparedAction, ActionOutcome
from .approval import SignedApprovalAuthority
from .planning import (EnergyBalance, PlanningSlot, FlexibleLoad, AdvisoryLoadPlan,
                       energy_balance, estimate_pv_power, optimize_load_schedule)
from .memory import EnergyEpisode, InMemoryEpisodeStore, SQLiteEpisodeStore, EnergyContextBuilder
from .agents import BoundedEnergyAgent, BoundedAgentResult, ToolChoice
from .skills import EnergySkill, EnergySkillRegistry
from .telemetry import TelemetryIngestor, EnergyEventBus, IngestionReceipt
from .checkpoints import SQLiteWorkflowCheckpoints
from .integrations import HomeAssistantConnector, HAEntityMapping, OpenMeteoIrradiance

from .evaluation import ForecastEvaluation, BacktestResult, evaluate_forecast, chronological_mean_backtest
__version__ = "0.2.0"
__all__ = ["EnergyChain", "AssetKind", "Capability", "Metric", "EnergySite", "EnergyAsset",
           "EnergyReading", "EnergyEvent", "EnergyPlan", "Tariff", "Permission", "Principal",
           "SafetyPolicy", "Approval", "RuntimeEstimate", "estimate_battery_runtime",
           "estimate_energy_cost", "simple_average_forecast", "detect_outliers", "EnergyAgent",
           "AgentResponse", "TextModel", "CallableTextModel", "EnergyConnector",
           "ConnectorRegistry", "HybridSiteSimulator", "CSVConnector", "EnergyMemory", "InMemoryEnergyMemory",
           "SQLiteEnergyMemory", "MemoryNote", "ToolRegistry", "ToolSpec", "EnergyWorkflow",
           "WorkflowStep", "WorkflowResult"]

__all__ += ["Fleet", "FleetManager", "FleetSnapshot", "FleetFailure", "EnergyConstraint",
            "EnergyActionSpec", "EnergyRelationship", "EnergyTopology", "RelationshipKind",
            "require_fresh", "ActionService", "PreparedAction", "ActionOutcome",
            "SignedApprovalAuthority", "EnergyBalance", "PlanningSlot", "FlexibleLoad",
            "AdvisoryLoadPlan", "energy_balance", "estimate_pv_power", "optimize_load_schedule",
            "EnergyEpisode", "InMemoryEpisodeStore", "SQLiteEpisodeStore", "EnergyContextBuilder",
            "BoundedEnergyAgent", "BoundedAgentResult", "ToolChoice", "EnergySkill",
            "EnergySkillRegistry", "TelemetryIngestor", "EnergyEventBus", "IngestionReceipt",
            "SQLiteWorkflowCheckpoints", "HomeAssistantConnector", "HAEntityMapping",
            "OpenMeteoIrradiance"]
__all__ += ["ForecastEvaluation", "BacktestResult", "evaluate_forecast", "chronological_mean_backtest"]
