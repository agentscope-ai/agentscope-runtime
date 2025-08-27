#!/bin/bash

# AgentScope Runtime RAG Demo - Start Script
# This script starts the agent server, web server, and frontend

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to kill processes on a specific port
kill_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}Killing processes on port $port...${NC}"
        lsof -Pi :$port -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
    fi
}

# Check if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Check if colima is installed and running
    if command -v colima &> /dev/null; then
        if colima status &> /dev/null; then
            echo -e "${GREEN}Colima is running${NC}"
            # Set Docker host for Colima
            export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
            echo -e "${BLUE}Docker host set to: $DOCKER_HOST${NC}"
        else
            echo -e "${YELLOW}Starting Colima...${NC}"
            colima start
            # Set Docker host for Colima
            export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
            echo -e "${BLUE}Docker host set to: $DOCKER_HOST${NC}"
        fi
    fi
fi

# Navigate to the project directory (already in the correct directory)
PROJECT_DIR="$(pwd)"
echo -e "${BLUE}Working in directory: $PROJECT_DIR${NC}"

# Load environment variables from .env file
ENV_FILE="backend/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Loading environment variables from $ENV_FILE...${NC}"
    # Use source to load the .env file properly
    set -a
    source "$ENV_FILE"
    set +a
else
    echo -e "${YELLOW}Warning: .env file not found at $ENV_FILE${NC}"
fi

# Check if required environment variables are set
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
    echo -e "${RED}Error: DASHSCOPE_API_KEY environment variable is not set${NC}"
    echo "Please set it in the backend/.env file or export it manually"
    exit 1
fi

# Kill any existing processes on the required ports
echo -e "${BLUE}Checking for processes on required ports...${NC}"
kill_port 8080  # Agent server
kill_port 5100  # Web server
kill_port 3000  # Frontend

# Activate virtual environment
if [ -f "backend/venv/bin/activate" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source backend/venv/bin/activate
else
    echo -e "${YELLOW}Warning: Virtual environment not found, using system Python${NC}"
fi

echo -e "${BLUE}Starting AgentScope Runtime RAG Demo...${NC}"

# Function to clean up background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down all services...${NC}"
    # Kill all background processes
    if [[ -n "$AGENT_PID" ]]; then
        echo -e "${BLUE}Stopping Agent Server (PID: $AGENT_PID)...${NC}"
        kill $AGENT_PID 2>/dev/null
    fi
    if [[ -n "$WEB_PID" ]]; then
        echo -e "${BLUE}Stopping Web Server (PID: $WEB_PID)...${NC}"
        kill $WEB_PID 2>/dev/null
    fi
    if [[ -n "$FRONTEND_PID" ]]; then
        echo -e "${BLUE}Stopping Frontend (PID: $FRONTEND_PID)...${NC}"
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    # Wait for processes to terminate
    if [[ -n "$AGENT_PID" ]]; then
        wait $AGENT_PID 2>/dev/null
    fi
    if [[ -n "$WEB_PID" ]]; then
        wait $WEB_PID 2>/dev/null
    fi
    if [[ -n "$FRONTEND_PID" ]]; then
        wait $FRONTEND_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Trap SIGINT and SIGTERM to clean up
trap cleanup SIGINT SIGTERM

# Start agent server (background)
echo -e "${BLUE}Starting Agent Server on port 8080...${NC}"
cd backend && python3 agent_server.py &
AGENT_PID=$!

# Start web server (background)
echo -e "${BLUE}Starting Web Server on port 5100...${NC}"
cd backend && python3 web_server.py &
WEB_PID=$!

# Start frontend (background)
echo -e "${BLUE}Starting Frontend on port 3000...${NC}"
cd frontend && npm start &
FRONTEND_PID=$!

# Wait for servers to start
sleep 5

# Check if servers are running
if kill -0 $AGENT_PID 2>/dev/null && kill -0 $WEB_PID 2>/dev/null && kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${GREEN}✅ All services started successfully!${NC}"
    echo -e "${GREEN}✅ Agent Server: http://localhost:8080${NC}"
    echo -e "${GREEN}✅ Web Server: http://localhost:5100${NC}"
    echo -e "${GREEN}✅ Frontend: http://localhost:3000${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
else
    echo -e "${RED}❌ Failed to start one or more services${NC}"
    echo -e "${YELLOW}Note: If Docker/Colima issues persist, you may need to:${NC}"
    echo -e "${YELLOW}  1. Ensure Colima is properly installed and running${NC}"
    echo -e "${YELLOW}  2. Manually start services in separate terminals${NC}"
    cleanup
    exit 1
fi

# Wait for background processes
wait $AGENT_PID $WEB_PID $FRONTEND_PID