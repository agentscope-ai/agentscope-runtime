# -*- coding: utf-8 -*-
from enum import Enum, EnumMeta


class DynamicEnumMeta(EnumMeta):
    def __new__(
        metacls,
        cls,
        bases,
        classdict,
        **kwds,
    ):  # pylint: disable=bad-mcs-classmethod-argument
        enum_class = super().__new__(metacls, cls, bases, classdict, **kwds)
        for member in enum_class:
            member.builtin = True
        return enum_class


class DynamicEnum(Enum, metaclass=DynamicEnumMeta):
    def __init__(self, value):  # pylint: disable=unused-argument
        self.builtin = True

    @classmethod
    def add_member(cls, name: str, value=None):
        if name in cls.__members__:
            raise ValueError(f"Member '{name}' already exists.")

        if value is None:
            value = name.lower()

        # Add new member
        new_member = cls._create_pseudo_member(name, value)
        new_member.builtin = False
        cls._member_map_[name] = new_member
        cls._value2member_map_[value] = new_member
        # Update ordered members
        cls._member_names_.append(name)

    @classmethod
    def _create_pseudo_member(cls, name, value):
        temp = object.__new__(cls)
        temp._value_ = value
        temp._name_ = name
        temp.__objclass__ = cls
        return temp

    @classmethod
    def get_builtin_members(cls):
        return [member for member in cls if getattr(member, "builtin", False)]

    @classmethod
    def get_dynamic_members(cls):
        return [
            member for member in cls if not getattr(member, "builtin", False)
        ]

    def is_builtin(self):
        return getattr(self, "builtin", False)


class SandboxType(DynamicEnum):
    """Sandbox type enumeration"""

    DUMMY = "dummy"
    BASE = "base"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    APPWORLD = "appworld"
    BFCL = "bfcl"
    WEBSHOP = "webshop"
