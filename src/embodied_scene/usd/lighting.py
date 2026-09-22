"""Apply an explicitly declared USD environment; never infer preview watt conversion."""
from pxr import Sdf, UsdLux

from embodied_scene.config import load_yaml


def configure_environment(stage, path):
    if not path.is_file():
        return
    spec = load_yaml(path).get("usd", {}).get("environment")
    if spec is None:
        return
    if spec.get("type") != "DomeLight" or spec.get("texture") is not None:
        raise ValueError("Automatic lighting mapping currently requires an untextured DomeLight")
    domes = [UsdLux.DomeLight(p) for p in stage.Traverse() if p.IsA(UsdLux.DomeLight)]
    if len(domes) > 1:
        raise ValueError("Resolve multiple environment domes before lighting mapping")
    dome = domes[0] if domes else UsdLux.DomeLight.Define(stage, "/World/Environment")
    dome.CreateColorAttr(tuple(spec["color"]))
    dome.CreateIntensityAttr(spec["intensity"])
    dome.CreateExposureAttr(spec.get("exposure", 0))
    dome.CreateEnableColorTemperatureAttr(spec.get("enable_color_temperature", False))
    dome.CreateTextureFileAttr(Sdf.AssetPath(""))
