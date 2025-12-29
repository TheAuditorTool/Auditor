"""Build hooks for packaging tasks."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _ensure_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return

    package = ModuleType(name)
    package.__file__ = str(path / "__init__.py")
    package.__path__ = [str(path)]
    package.__package__ = name
    package.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = [str(path)]
    sys.modules[name] = package


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create spec for {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SchemaCodegenHook(BuildHookInterface):
    """Ensure schema-generated files are current during packaging."""

    def initialize(self, version, build_data):
        root = Path(self.root)
        codegen_path = root / "theauditor" / "indexer" / "schemas" / "codegen.py"
        logging_path = root / "theauditor" / "utils" / "logging.py"

        if not codegen_path.exists():
            print(f"WARNING: Could not find codegen script at {codegen_path}")
            return

        if not logging_path.exists():
            print(f"WARNING: Could not find logging module at {logging_path}")
            return

        _ensure_package("theauditor", root / "theauditor")
        _ensure_package("theauditor.indexer", root / "theauditor" / "indexer")
        _ensure_package("theauditor.indexer.schemas", root / "theauditor" / "indexer" / "schemas")
        _ensure_package("theauditor.utils", root / "theauditor" / "utils")

        sys.modules["theauditor"].indexer = sys.modules["theauditor.indexer"]
        sys.modules["theauditor"].utils = sys.modules["theauditor.utils"]
        sys.modules["theauditor.indexer"].schemas = sys.modules["theauditor.indexer.schemas"]

        logging_module = _load_module("theauditor.utils.logging", logging_path)
        sys.modules["theauditor.utils"].logging = logging_module

        codegen_module = _load_module("theauditor.indexer.schemas.codegen", codegen_path)
        output_dir = root / "theauditor" / "indexer" / "schemas"

        if hasattr(codegen_module, "SchemaCodeGenerator"):
            codegen_module.SchemaCodeGenerator.write_generated_code(output_dir)
        else:
            print(f"Error: SchemaCodeGenerator not found in {codegen_path}")
            print(f"Available attributes: {dir(codegen_module)}")
