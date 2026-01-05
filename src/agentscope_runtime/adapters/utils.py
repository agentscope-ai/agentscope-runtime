# -*- coding: utf-8 -*-
def _update_obj_attrs(obj, **attrs):
    for key, value in attrs.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
    return obj
