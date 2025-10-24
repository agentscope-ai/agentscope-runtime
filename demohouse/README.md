# Agentscope Runtime Demohouse

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/language-Python-blue)


<img src="assets/logo.svg" alt="Agent Scope Logo" width="150">

Welcome to the Demohouse repository! This collection provides ready-to-use demo projects built on top of various technologies, designed to accelerate your development process. These demos cover a range of common use cases and complexities, from simple chatbots to complex agent workflows.

## ✨ Getting Started

Follow these steps to set up and run the sample agents:

1.  **Prerequisites:**
    *   **Install Agentscope Runtime:** Ensure you have Agentscope Runtime installed and configured. Follow the Python instructions.
    *   **Set Up Environment Variables:** Each agent example relies on a `.env`
        file for configuration (like API keys). This keeps secrets out of the code.
        *   You will need to create a `.env` file in each agent's directory you
            wish to run (usually by copying the provided `.env.template`).


2.  **Explore the Agents:**

    *   Browse the subdirectories. Each contains a specific sample agent with its own
    `README.md`.

3.  **Run an Agent:**
    *   Choose an agent.
    *   Navigate into that agent's specific directory (e.g., `cd chatbot`).
    *   Follow the instructions in *that agent's* `README.md` file for specific
        setup (like installing dependencies via `npm install`) and running
        the agent.
    *   Browse the folders in this repository. Each agent and tool have its own
        `README.md` file with detailed instructions.

## 🌳 Repository Structure
```bash
.
├── browser_use                  # A demo of using browser in sandbox
│   ├── frontend
│   ├── backend
│   ├── README.md                # Specific agent-specific instructions
├── chatbot                      # A demo of chatbot with conversation management.
│   ├── frontend
│   ├── backend
│   ├── README.md                # Specific agent-specific instructions
├── qwen_langgraph_search        # A deep research project with qwen and langgraph
│   ├── src
│   ├── README.md                # Specific agent-specific instructions
└── README.md                    # This file (Repository overview)
```

| project                               | description   | features                                                            |
|---------------------------------------|----|---------------------------------------------------------------------|
| [browser_user](browser_use/README.md) | a demo of using browser in sandbox | ``sandbox`` , ``agentscopt``, ``browser``                           |
| [qwen_langgraph_search](qwen_langgraph_search/README.md)              | a deep research project with qwen and langgraph | ``qwen`` , ``langgraph``,``websearch``                                |
| [chatbot](chatbot/README.md)          | a demo of chatbot with conversation management. | ``agent``,``local_deployment`` , ``multi-user``, ``session_manage`` |

## ℹ️ Getting help

If you have any questions or if you found any problems with this repository, please report through [GitHub issues].

## 🤝 Contributing

We welcome contributions from the community! Whether it's bug reports, feature requests, documentation improvements, or code contributions, please see our [**Contributing Guidelines**] to get started.

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## Disclaimers

This project is intended for demonstration purposes only. It is not intended for use in a production environment.
