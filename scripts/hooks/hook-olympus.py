"""Olympus loads planners from directory names; its optional old SMAC exits on import.

Ship the small runtime sources for directory discovery, but freeze only planners
used by our Atlas adapter. Do not import every optional optimizer during analysis.
"""
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("olympus", include_py_files=True, excludes=["**/__pycache__/**", "**/__OLD*/**", "**/__BACKUP*", "**/.scratch/**"])
hiddenimports = [
    "olympus.campaigns.campaign", "olympus.campaigns.observations", "olympus.campaigns.param_space",
    "olympus.planners.abstract_planner", "olympus.planners.custom_planner", "olympus.planners.planner",
    "olympus.planners.planner_random_search", "olympus.planners.planner_sobol",
    "olympus.planners.planner_latin_hypercube",
    "olympus.scalarizers.abstract_scalarizer", "olympus.scalarizers.scalarizer",
    "olympus.objects.abstract_object", "olympus.objects.object_parameter",
    "olympus.objects.object_parameter_vector", "olympus.objects.object_config",
]
