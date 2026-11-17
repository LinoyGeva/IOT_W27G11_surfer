"""Load headless bench decoders without launching inspection tools or a GUI."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hr = load("hr_inspection_decoder", "sensor_understanding/garmin_hrm/hr_diagnostic.py")
atlas = load("atlas_inspection_decoder", "sensor_understanding/vakaros_atlas/live_atlas.py")
