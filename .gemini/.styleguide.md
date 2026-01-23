# AgentScope Runtime Code Review Guide

You should conduct a strict code review. Each requirement is labeled with priority:
- **[MUST]** must be satisfied or PR will be rejected
- **[SHOULD]** strongly recommend
- **[MAY]** optional suggestion

## 1. Code Quality

### [MUST] Lazy Loading
- Optional dependencies should be imported at the point of use (lazy loading), to avoid centralized imports at the top of the file.
  - This applies to libraries not in the core `dependencies` of `pyproject.toml`, such as those in the `[project.optional-dependencies]` sections.
- For base class imports, use factory pattern:
```python
def get_xxx_cls() -> "MyClass":
    from xxx import BaseClass
    class MyClass(BaseClass): ...
    return MyClass
```

### [SHOULD] Code Conciseness

After understanding the code intent, check if it can be optimized:

- Avoid unnecessary temporary variables
- Merge duplicate code blocks
- Prioritize reusing existing utility functions

## 2. [MUST] Code Security

- Prohibit hardcoding API keys/tokens/passwords
- Use environment variables or configuration files for management
- Check for debug information and temporary credentials
- Check for injection attack risks (SQL/command/code injection, etc.)

## 3. [MUST] Testing & Dependencies

- New features must include unit tests
- New dependencies need to be added to the corresponding section in `pyproject.toml`
- Dependencies for non-core scenarios should not be added to the minimal dependency list

## 4. Code Standards

### [MUST] Comment Standards

- **Use English**
- All classes/methods must have complete docstrings, strictly following the template:

```python
def func(a: str, b: int | None = None) -> str:
    """{description}

    Args:
        a (`str`):
            The argument a
        b (`int | None`, optional):
            The argument b

    Returns:
        `str`:
            The return str
    """
```

- Use reStructuredText syntax for special content:

```python
class MyClass:
    """xxx

    `Example link <https://xxx>`_

    .. note:: Example note

    .. tip:: Example tip

    .. important:: Example important info

    .. code-block:: python

        def hello_world():
            print("Hello world!")

    """
```

### [MUST] Pre-commit Checks

- **Strict review**: In most cases, code should be modified rather than skipping checks
- **File-level check skipping is prohibited**
- Only allowed skip: agent class system prompt parameters (to avoid `\n` formatting issues)

------

## 5. Git Standards

### [MUST] PR Title

- Follow Conventional Commits
- Must use prefixes: `feat`, `fix`, `docs`, `ci`, `refactor`, `test`, etc.
- Format: `feat(scope): description`
- Example: `feat(memory): add redis cache support`
