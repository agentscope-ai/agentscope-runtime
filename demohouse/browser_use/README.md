# Browser Use Demo

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/language-Python-blue)
![Node.js](https://img.shields.io/badge/node.js-v23.9.0-green)
![React](https://img.shields.io/badge/react-v19.1.0-green)

This demo showcases how to use browser automation capabilities within the AgentScope Runtime framework. It provides both backend services and a frontend interface to demonstrate browser-based agent interactions. The real-time visualization of browser interactions is powered by [Steel-Browser](https://github.com/steel-dev/steel-browser).

<img src="https://img.alicdn.com/imgextra/i3/O1CN01hTTRvK1MxxyT0lCNm_!!6000000001502-1-tps-656-480.gif" alt="video of browser-use demo" width="800">

## 🌳 Project Structure

```bash
├── backend                         # Backend directory, containing server-side services and logic
│   ├── agentscope_browseruse_agent.py    # Script related to browser usage or agent management
│   ├── async_quart_service.py            # Asynchronous service using Quart to handle backend requests
│   └── prompts.py                        # Module containing prompt messages or interaction logic for the backend
├── frontend                        # Frontend directory, containing client-side code (typically using React)
│   ├── public                      # Public folder for storing static files copied during build
│   │   ├── index.html              # HTML template for the frontend app, acts as the entry HTML file
│   │   └── manifest.json           # Manifest file describing the web app's metadata such as name and icons
│   ├── src                         # Source code folder, containing React components and styles
│   │   ├── App.css                 # Stylesheet for the main app component
│   │   ├── App.tsx                 # TypeScript file for the main app component, the root component of the application
│   │   ├── Browser.scss            # Stylesheet for specific browser-related components or pages using SCSS
│   │   ├── Browser.tsx             # React component file related to browser functionality
│   │   ├── index.css               # Global stylesheet affecting the overall look of the application
│   │   └── index.tsx               # Entry point for the React application to render content into `index.html`
│   ├── package.json                # Project dependencies file, lists all npm dependencies and scripts
│   └── tsconfig.json               # TypeScript configuration file, defines compilation options
└── README.md                       # Project documentation file, provides basic information and usage instructions
```

## 📖 Overview

This demo illustrates how agents can interact with web browsers to perform tasks such as:
- Web navigation
- Form filling
- Data extraction from web pages
- Automated web workflows

The implementation uses AgentScope's capabilities to create browser-based agents that can perform complex web interactions.

## ⚙️ Components

### Backend
- `agentscope_browseruse_agent.py`: Implements the browser-using agent with AgentScope Runtime
- `async_quart_service.py`: Provides asynchronous web service endpoints
- `prompts.py`: Contains prompts used by the agent for browser interactions

### Frontend
- React-based interface for visualizing browser interactions
- TypeScript implementation for type-safe code

## 🌵Architecture

The architecture of the demo is depicted in the following diagram:

```mermaid
graph LR;
    subgraph As["AgentScope Runtime"]
        E[Sandbox]-->E1[Browser sandbox]
        F[Agent Engine]
        F-->|tool call| E
    end
    subgraph Bs["Frontend Service by React"]
        B['React App']
    end
    subgraph Cs["Backend Service by Quart"]
        C['async_quart_service']
            C --> D[AgentscopeBrowseruseAgent]
    end
    A[User] --> |request| Bs
    B --> C[Backend Service by Quart]
    D --> E
    D --> F
```

## 🚀 Getting Started

### Preinstall

Node and Python environments are required.

1. Install [Node.js](https://nodejs.org/en/)
2. Install [Python](https://www.python.org/) (version >= 3.11)
3. Apply a DashScope API key to the `backend/.env` file.

### Install the Front-end Service

#### Install Node Packages

```bash
cd frontend
npm install
npm install -g serve
```

#### Run the Front-end Service
Use your frontend port to serve the frontend service.

NOTE: the `config.yml` file contains the 'frontend' port configuration, which SHOULD BE the SAME with the port here.
```bash
npm run build
serve -s build -p 3000
```

This will open your browser and display the demo page. Alternatively, you can also open it in your browser at http://localhost:3000:

#### (Alternatively) Dev Mode
To run the front-end service in development mode, use the following command:
```bash
npm run start
```

### Install the Back-end Service

#### Install Python Packages

```bash
cd ../backend
pip install -r requirements.txt
```

### Run the Backend Service

```bash
python async_quart_service.py
```

The service will listen on port 9000.

#### (Alternative) Use Redis as session service
1. Install [Redis](https://redis.io/)  and start it
2. modify `config.yml`. Set session-type to redis and set session-redis.url as your redis url. For example, if your redis url is redis://localhost:6379/0, the `config.yml` should be like this:

```yml
backend:
  session-type: redis # session type, support memory, redis (you need install redis)
  session-redis: # config this if you use redis as session store
    url: redis://localhost:6379/0
```

### Usage

1. Open your browser and navigate to http://localhost:3000.
2. Type your question in the input box and click the "Search" button, e.g., "Visit www.chinadaily.com.cn to search for today's hot topics."
3. The response will be displayed in the output box.

## 🛠️ Features

- Browser automation within the AgentScope Runtime framework
- Real-time visualization of browser actions
- Asynchronous processing for better performance
- React-based user interface
- TypeScript support for type safety

## ℹ️ Getting Help

If you have any questions or encounter any problems with this demo, please report them through [GitHub issues]().

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 🍬 Disclaimers

This is not an officially supported product. This project is intended for demonstration purposes only and is not suitable for production use.
