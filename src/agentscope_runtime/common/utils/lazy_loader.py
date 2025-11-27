# -*- coding: utf-8 -*-
import importlib


def install_lazy_loader(globals_dict, lazy_map):
    """
    Install __getattr__ and __all__ for lazy loading of module members.

    Args:
        globals_dict: The globals() of the current module.
                      Pass the globals() from the module where this is called.
        lazy_map: dict[name, module_path]
                  OR dict[name, dict(module=..., hint=...)]
                  The hint is an optional message for missing dependencies.
    """
    __all__ = list(lazy_map.keys())

    def __getattr__(name):
        if name in lazy_map:
            entry = lazy_map[name]
            module_path, hint = None, None

            # Support two configuration formats
            if isinstance(entry, str):
                module_path = entry
            elif isinstance(entry, dict):
                module_path = entry["module"]
                hint = entry.get("hint")

            try:
                module = importlib.import_module(
                    module_path,
                    globals_dict["__name__"],
                )
            except ImportError as e:
                msg = f"Failed to import {name}. Possible missing dependency."
                if hint:
                    msg += f" Please install dependency: {hint}"
                else:
                    msg += (
                        " Please install dependency:  pip install "
                        "agentscope-runtime[ext]"
                    )
                raise ImportError(msg) from e

            obj = getattr(module, name)
            # Cache in globals to avoid reloading
            globals_dict[name] = obj
            return obj

        raise AttributeError(
            f"module {globals_dict['__name__']} has no attribute {name}",
        )

    # Modify the globals of the calling module
    globals_dict["__all__"] = __all__
    globals_dict["__getattr__"] = __getattr__
