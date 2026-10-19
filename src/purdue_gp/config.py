import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MPS_TO_MPH = 2.23694


def load_config(path=None):
    cfg = json.load(open(path or ROOT / "config.json"))
    cfg["root"] = ROOT
    return cfg
