"""Load the playbook and risk policy YAML files."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
STATE_DIR = Path(os.environ.get("TRADER_STATE_DIR", ROOT / "state"))


@dataclass(frozen=True)
class Config:
    playbook: dict[str, Any]
    policy: dict[str, Any]

    @property
    def sleeves(self) -> dict[str, dict[str, Any]]:
        return self.playbook["sleeves"]

    def sleeve_enabled(self, sleeve: str) -> bool:
        return bool(self.sleeves[sleeve].get("enabled", True))

    def crypto_symbols(self) -> list[str]:
        return list(self.sleeves["D"]["symbols"]) if self.sleeve_enabled("D") else []

    def stock_universe(self) -> list[str]:
        return list(self.sleeves["C"]["universe"])

    def etf_symbols(self) -> list[str]:
        a, b = self.sleeves["A"], self.sleeves["B"]
        syms = list(a["assets"]) + [a["cash"]] + list(b["symbols"])
        if a.get("gem_blend"):
            syms += list(a["gem"].values())
        syms += list(self.playbook["regime"]["canaries"]) + [self.playbook["regime"]["benchmark"]]
        return _unique(syms)

    def allowlist(self) -> list[str]:
        return _unique(self.etf_symbols() + self.stock_universe() + self.crypto_symbols())

    def data_symbols(self) -> list[str]:
        """Everything fetched each run: the allowlist plus data-only symbols (never traded)."""
        extra = list(self.playbook["regime"].get("credit", [])) + list(self.playbook.get("data", {}).get("extra_symbols", []))
        return _unique(self.allowlist() + extra)

    def asset_class(self, symbol: str) -> str:
        if "/" in symbol:
            return "crypto"
        if symbol in self.etf_symbols() or symbol in self.playbook.get("data", {}).get("extra_symbols", []) \
                or symbol in self.playbook["regime"].get("credit", []):
            return "etf"
        return "stock"

    def sector_of(self, symbol: str) -> str | None:
        """C-9 sector group of a sleeve C stock, or None."""
        for group, members in self.sleeves["C"].get("sectors", {}).items():
            if symbol in members:
                return group
        return None

    def is_equity_like(self, symbol: str) -> bool:
        """RISK-6: equity-like ETFs and every single stock."""
        return self.asset_class(symbol) == "stock" or symbol in self.policy["portfolio"].get("equity_like_symbols", [])

    def sleeve_weight_cap(self, sleeve: str, promoted: list[str] | tuple = ()) -> float:
        """RISK-8: a sleeve that has not passed gate M-10 is capped at its default weight (A is exempt)."""
        s = self.sleeves[sleeve]
        if sleeve == "A" or sleeve in promoted:
            return float(s["max"])
        return float(min(s["max"], s["default"]))

    def risk_pct(self, sleeve: str) -> float:
        """RISK-2: 1R for one sleeve, never above the hard cap."""
        pt = self.policy["per_trade"]
        r = pt.get("risk_pct_by_sleeve", {}).get(sleeve, pt["risk_pct_default"])
        return float(min(r, pt["risk_pct_hard_cap"]))


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    with open(config_dir / "playbook.yaml") as f:
        playbook = yaml.safe_load(f)
    with open(config_dir / "risk_policy.yaml") as f:
        policy = yaml.safe_load(f)
    model = os.environ.get("CLAUDE_MODEL")
    if model:
        playbook["claude"]["model"] = model
    return Config(playbook=playbook, policy=policy)
