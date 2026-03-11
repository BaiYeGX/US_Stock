from __future__ import annotations

import logging

from app.alerts.renderer import render_json, render_text
from app.alerts.schemas import AlertPlan

logger = logging.getLogger(__name__)


def dispatch(plan: AlertPlan, output_text: bool = True, output_json: bool = True) -> None:
    if output_text:
        logger.info("\n%s", render_text(plan))
    if output_json:
        logger.info("%s", render_json(plan))
