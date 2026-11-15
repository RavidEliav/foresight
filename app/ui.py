"""Shared UI helpers: environment badge, passcode check, friendly errors."""

from __future__ import annotations

import hmac

import streamlit as st

from foresight.settings import Settings

ENV_COLORS = {"main": "green", "dev": "orange", "local": "gray"}


def environment_badge(settings: Settings) -> None:
    env = settings.environment
    st.sidebar.markdown(f":{ENV_COLORS.get(env, 'blue')}-badge[Environment: {env}]")


def passcode_ok(settings: Settings, entered: str) -> bool:
    if not settings.run_passcode:
        return False
    return hmac.compare_digest(entered.encode(), settings.run_passcode.encode())


def friendly_error(message: str) -> None:
    st.error(message, icon=":material/error:")


def coming_soon(phase: str) -> None:
    st.info(f"This page is built in {phase}.", icon=":material/construction:")
