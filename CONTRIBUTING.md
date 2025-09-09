# How to Contribute

Thanks for your interest in the AgentScope Runtime project.

AgentScope Runtime is an open-source project focused on agent deployment and secure tool execution with a friendly community of developers eager to help new contributors. We welcome contributions of all types, from code improvements to documentation.

## Community

A good first step to getting involved in the AgentScope Runtime project is to participate in our discussions and join us in our different communication channels. Here are several ways to connect with us:

- **GitHub Discussions**: Ask questions and share experiences (use **English**)
- **Discord**: Join our [Discord channel](https://discord.gg/eYMpfnkG8h) for real-time discussions
- **DingTalk**: Chinese users can join our [DingTalk Group](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)


## Reporting Issues

### Bugs

If you find a bug in AgentScope Runtime, first test against the latest version to ensure your issue hasn't already been fixed. If not, search our issues list on GitHub to see if a similar issue has already been opened.

If you confirm that the bug hasn't already been reported, file a bug issue before writing any code. When submitting an issue, please include:

- Clear problem description
- Steps to reproduce
- Code/error messages
- Environment details (OS, Python version)
- Affected components (Engine, Sandbox, or both)

### Security Issues

If you discover a security issue in AgentScope Runtime, please report it to us through the [Alibaba Security Response Center (ASRC)](https://security.alibaba.com/).

## Requesting Features

If you find yourself wishing for a feature that doesn't exist in AgentScope Runtime, please open a feature request issue on GitHub to describe:

- The feature and its purpose
- How it should work
- Security considerations (if applicable)

## Improving Documentation

Please see [CONTRIBUTE_TO_COOKBOOK](https://runtime.agentscope.io/en/README.html).

## Contributing Code

If you would like to contribute a new feature or a bug fix to AgentScope Runtime, please first discuss your idea on a GitHub issue. If there isn't an issue for it, create one. There may be someone already working on it, or it may have particular complexities (especially security considerations for sandbox features) that you should be aware of before starting to code.

### Install pre-commit

AgentScope Runtime uses pre-commit to ensure code quality and security standards. Before contributing, install pre-commit by typing:

```bash
pip install pre-commit
```

Install the pre-commit hooks with:

```bash
pre-commit install
```

### Fork and Create a Branch

Fork the main AgentScope Runtime code and clone it to your local machine. See the GitHub help page for help.

Create a branch with a descriptive name.

```bash
git checkout -b feature/your-feature-name
```

### Make Your Changes

- Write clear, well-commented code
- Follow existing code style
- Add tests for new features/fixes
- Update documentation as needed

### Test Your Changes

Run the test suite to ensure your changes don't break existing functionality:

```bash
pytest
```

### Submit Your Changes

1. Commit your changes with a clear message:

```bash
git commit -m "Add: brief description of your changes"
```

2. Push to your fork:

```bash
git push origin feature/your-feature-name
```

3. Create a Pull Request (PR) from your branch to the main repository with a **clear description**

### Code Review Process

- All PRs require review from maintainers
- Address any feedback or requested changes
- Once approved, your PR will be merged

Thank you for contributing to AgentScope Runtime!