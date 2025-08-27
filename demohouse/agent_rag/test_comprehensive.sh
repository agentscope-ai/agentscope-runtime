#!/bin/bash

# Comprehensive Test Script for AgentScope Runtime RAG Demo
# Tests all core functionality including login, upload, question answering, and deletion

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test file paths
TEST_DIR="/tmp/agentscope_test"
COOKIE_FILE="$TEST_DIR/cookies.txt"
UPLOAD_FILE="$TEST_DIR/test_document.txt"

# Create test directory and files
mkdir -p "$TEST_DIR"

# Create a test document
cat > "$UPLOAD_FILE" << 'EOF'
Welcome to the Era of Experience
Authors: David Silver, Richard S. Sutton

Abstract
In this paper, we present a comprehensive overview of reinforcement learning from the perspective of experience-based learning. We discuss the fundamental principles that underlie the acquisition of knowledge through interaction with an environment, and explore how these principles can be applied to develop intelligent agents capable of learning from their own experiences.

Introduction
The era of experience marks a significant shift in how we approach artificial intelligence. Rather than relying solely on pre-programmed knowledge, modern AI systems are increasingly designed to learn from their interactions with the world around them. This paradigm shift has profound implications for the development of truly intelligent systems.

Key Concepts
1. Experience-based learning
2. Reinforcement signals
3. Policy optimization
4. Value function approximation

Conclusion
The era of experience represents a fundamental change in how we think about artificial intelligence. By embracing experience-based learning, we can develop more adaptive and robust AI systems that continue to improve over time.
EOF

echo -e "${BLUE}=== AgentScope Runtime RAG Demo - Comprehensive Test ===${NC}"
echo

# Function to check if servers are running
check_servers() {
    echo -e "${YELLOW}Checking if servers are running...${NC}"
    
    # Check agent server (on port 8080 based on actual deployment)
    echo -e "${BLUE}Checking agent server on port 8080...${NC}"
    if curl -s -f http://localhost:8080/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Agent Server is running${NC}"
    else
        echo -e "${RED}❌ Agent Server is not running on port 8080${NC}"
        echo "Please start the agent server with: python agent_server.py"
        return 1
    fi
    
    # Check web server
    echo -e "${BLUE}Checking web server on port 5100...${NC}"
    if curl -s -f http://localhost:5100/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Web Server is running${NC}"
    else
        echo -e "${RED}❌ Web Server is not running on port 5100${NC}"
        echo "Please start the web server with: python web_server.py"
        # Debug: Show what's actually on port 5100
        echo -e "${YELLOW}Debug: Checking what's actually on port 5100${NC}"
        curl -s http://localhost:5100/health || echo "No response from port 5100"
        return 1
    fi
    
    echo
    return 0
}

# Function to perform login
login() {
    echo -e "${YELLOW}Performing login...${NC}"
    
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:5100/api/login \
        -H "Content-Type: application/json" \
        -d '{"username": "testuser1", "password": "testpass1"}' \
        -c "$COOKIE_FILE")
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ Login successful${NC}"
        return 0
    else
        echo -e "${RED}❌ Login failed with HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
}

# Function to create conversation
create_conversation() {
    echo -e "${YELLOW}Creating conversation...${NC}"
    
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:5100/api/conversations \
        -H "Content-Type: application/json" \
        -b "$COOKIE_FILE" \
        -d '{"title": "Test Conversation"}')
    
    http_code="${response: -3}"
    CONVERSATION_ID=$(echo "$response" | sed '$d' | jq -r '.id' 2>/dev/null)
    
    if [ "$http_code" = "201" ] && [ -n "$CONVERSATION_ID" ] && [ "$CONVERSATION_ID" != "null" ]; then
        echo -e "${GREEN}✅ Conversation created with ID: $CONVERSATION_ID${NC}"
        echo "$CONVERSATION_ID" > "$TEST_DIR/conversation_id.txt"
        return 0
    else
        echo -e "${RED}❌ Failed to create conversation. HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
}

# Function to upload file
upload_file() {
    echo -e "${YELLOW}Uploading test document...${NC}"
    
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:5100/api/upload \
        -b "$COOKIE_FILE" \
        -F "file=@$UPLOAD_FILE")
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "201" ]; then
        echo -e "${GREEN}✅ File uploaded successfully${NC}"
        FILE_ID=$(echo "$response" | sed '$d' | jq -r '.filename' 2>/dev/null)
        echo "$FILE_ID" > "$TEST_DIR/file_id.txt"
        return 0
    else
        echo -e "${RED}❌ File upload failed with HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
}

# Function to list knowledge base files
list_files() {
    echo -e "${YELLOW}Listing knowledge base files...${NC}"
    
    response=$(curl -s -w "%{http_code}" -X GET http://localhost:5100/api/knowledge-files \
        -b "$COOKIE_FILE")
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ Knowledge base files retrieved${NC}"
        echo "$response" | sed '$d' | jq '.' 2>/dev/null || echo "No files found"
        return 0
    else
        echo -e "${RED}❌ Failed to list knowledge base files. HTTP code: $http_code${NC}"
        return 1
    fi
}

# Function to ask question about uploaded document
ask_question() {
    local question="$1"
    local test_name="$2"
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    echo -e "${BLUE}Question: $question${NC}"
    
    # Create a new conversation for each question to avoid AgentScope Runtime bug
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:5100/api/conversations \
        -H "Content-Type: application/json" \
        -b "$COOKIE_FILE" \
        -d '{"title": "Test Conversation"}')
    
    http_code="${response: -3}"
    CONVERSATION_ID=$(echo "$response" | sed '$d' | jq -r '.id' 2>/dev/null)
    
    if [ "$http_code" != "201" ] || [ -z "$CONVERSATION_ID" ] || [ "$CONVERSATION_ID" = "null" ]; then
        echo -e "${RED}❌ Failed to create conversation for question. HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
    
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:5100/api/conversations/$CONVERSATION_ID/messages \
        -H "Content-Type: application/json" \
        -b "$COOKIE_FILE" \
        -d "{\"text\": \"$question\", \"sender\": \"user\"}")
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "201" ]; then
        # Get the AI response
        ai_response=$(echo "$response" | sed '$d' | jq -r '.text' 2>/dev/null)
        echo -e "${GREEN}✅ Question processed${NC}"
        echo -e "${BLUE}AI Response:${NC}"
        echo "$ai_response"
        echo
        return 0
    else
        echo -e "${RED}❌ Failed to process question. HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
}

# Function to delete file
delete_file() {
    echo -e "${YELLOW}Deleting test document...${NC}"
    
    # First, get the file ID from the knowledge base
    response=$(curl -s -X GET http://localhost:5100/api/knowledge-files \
        -b "$COOKIE_FILE")
    
    # Extract file ID (assuming we want to delete the first file)
    FILE_ID=$(echo "$response" | jq -r '.[0].id' 2>/dev/null)
    
    if [ -z "$FILE_ID" ] || [ "$FILE_ID" = "null" ]; then
        echo -e "${RED}❌ No file ID found to delete${NC}"
        return 1
    fi
    
    response=$(curl -s -w "%{http_code}" -X DELETE http://localhost:5100/api/knowledge-files/$FILE_ID \
        -b "$COOKIE_FILE")
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ File deleted successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ File deletion failed with HTTP code: $http_code${NC}"
        echo "Response: $(echo "$response" | sed '$d')"
        return 1
    fi
}

# Function to clean up
cleanup() {
    echo -e "${YELLOW}Cleaning up test files...${NC}"
    rm -rf "$TEST_DIR"
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Main test execution
main() {
    # Check if servers are running
    if ! check_servers; then
        exit 1
    fi
    
    # Perform login
    if ! login; then
        cleanup
        exit 1
    fi
    
    # Create conversation
    if ! create_conversation; then
        cleanup
        exit 1
    fi
    
    echo
    echo -e "${BLUE}=== Test 1: Upload Document ===${NC}"
    
    # Upload file
    if ! upload_file; then
        cleanup
        exit 1
    fi
    
    # List files
    list_files
    
    echo
    echo -e "${BLUE}=== Test 2: Question Answering with Document ===${NC}"
    
    # Ask questions about the uploaded document
    ask_question "What is this document about?" "General topic identification"
    ask_question "Who are the authors of this paper?" "Author identification"
    ask_question "What are the key concepts discussed in this paper?" "Key concepts extraction"
    
    echo
    echo -e "${BLUE}=== Test 3: Document Deletion ===${NC}"
    
    # Delete file
    if ! delete_file; then
        cleanup
        exit 1
    fi
    
    # List files again to confirm deletion
    list_files
    
    echo
    echo -e "${BLUE}=== Test 4: Question Answering after Deletion ===${NC}"
    
    # Ask the same questions after deletion - should not find content
    ask_question "What is this document about?" "General topic identification (after deletion)"
    ask_question "Who are the authors of this paper?" "Author identification (after deletion)"
    
    echo
    echo -e "${GREEN}=== All Tests Completed ===${NC}"
    
    # Final cleanup
    cleanup
    
    echo -e "${GREEN}✅ Comprehensive test completed successfully!${NC}"
}

# Run main function
main