from typing import Dict, Any, Optional
from src.ats.base import BaseATSConnector
from src.ats.workday import WorkdayConnector
from src.ats.oracle_hcm import OracleHCMConnector
from src.ats.ashby import AshbyConnector
from src.ats.france_travail import FranceTravailConnector
from src.ats.greenhouse import GreenhouseConnector
from src.ats.smartrecruiters import SmartRecruitersConnector
from src.ats.lever import LeverConnector
from src.ats.cea import CEAConnector
from src.ats.inria import InriaConnector


CONNECTORS = {
    "workday": WorkdayConnector,
    "oracle_hcm": OracleHCMConnector,
    "ashby": AshbyConnector,
    "france_travail": FranceTravailConnector,
    "greenhouse": GreenhouseConnector,
    "smartrecruiters": SmartRecruitersConnector,
    "lever": LeverConnector,
    "cea": CEAConnector,
    "inria": InriaConnector,
}


def get_connector(config: Dict[str, Any]) -> Optional[BaseATSConnector]:
    """Factory to instantiate the appropriate ATS connector."""
    ats_type = config.get("ats", "").lower()
    connector_cls = CONNECTORS.get(ats_type)
    if not connector_cls:
        print(f"[Warning] Unknown ATS type '{ats_type}' for company '{config.get('name')}'.")
        return None
    return connector_cls(config)
