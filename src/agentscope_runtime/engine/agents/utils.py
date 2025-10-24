# -*- coding: utf-8 -*-
import inspect
import logging

logger = logging.getLogger(__name__)


def build_agent(builder_cls, params):
    """
    Filters out unsupported parameters based on the __init__ signature of
    builder_cls
    and instantiates the class.

    Args:
        builder_cls (type): The class to instantiate.
        params (dict): Dictionary of parameters to pass to the constructor.

    Returns:
        object: An instance of builder_cls.
    """
    try:
        # Get the signature of the __init__ method
        sig = inspect.signature(builder_cls.__init__)
        allowed_params = set(sig.parameters.keys())
        # Remove 'self' from the list of allowed parameters
        allowed_params.discard("self")
    except (TypeError, ValueError):
        # If signature cannot be inspected, allow all given params
        allowed_params = set(params.keys())

    filtered_params = {}  # Parameters that are accepted by the constructor
    unsupported = []  # Parameters that are not accepted

    # Separate supported and unsupported parameters
    for k, v in params.items():
        if k in allowed_params:
            filtered_params[k] = v
        else:
            unsupported.append(f"{k}={v!r}")

    # Log a warning if there are unsupported parameters
    if unsupported:
        unsupported_str = ", ".join(unsupported)
        logger.warning(
            f"The following parameters are not supported by "
            f"{builder_cls.__name__} and have been ignored: "
            f"{unsupported_str}. If you require these parameters, "
            f"please update the `__init__` method of "
            f"{builder_cls.__name__} to accept and handle them.",
        )

    # Instantiate the class with only supported parameters
    return builder_cls(**filtered_params)
