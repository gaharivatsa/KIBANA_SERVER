#!/bin/bash

# Kibana Server Setup Script for macOS
# This script automates the setup of the Kibana MCP server on macOS systems

# Set text colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Kibana MCP Server Setup for macOS ===${NC}"
echo -e "${BLUE}This script will set up everything needed to run the Kibana MCP server${NC}"

# Create a function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check and install Python if needed
install_python() {
    echo -e "${YELLOW}Checking for Python...${NC}"
    if ! command_exists python3; then
        echo -e "${YELLOW}Python not found. Installing Python via Homebrew...${NC}"
        
        # Check if Homebrew is installed
        if ! command_exists brew; then
            echo -e "${YELLOW}Homebrew not found. Installing Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            
            # Add Homebrew to PATH based on chip architecture
            if [[ "$(uname -m)" == "arm64" ]]; then
                echo -e "${YELLOW}Adding Homebrew to PATH for Apple Silicon...${NC}"
                eval "$(/opt/homebrew/bin/brew shellenv)"
            else
                echo -e "${YELLOW}Adding Homebrew to PATH for Intel Mac...${NC}"
                eval "$(/usr/local/bin/brew shellenv)"
            fi
        fi
        
        # Install Python
        brew install python
        
        if ! command_exists python3; then
            echo -e "${RED}Failed to install Python. Please install it manually.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}Python is already installed: $(python3 --version)${NC}"
    fi
    
    # Ensure pip is up to date
    echo -e "${YELLOW}Updating pip...${NC}"
    python3 -m pip install --upgrade pip
}

# Create and activate virtual environment
setup_virtualenv() {
    echo -e "${YELLOW}Setting up virtual environment...${NC}"
    
    # Check if KIBANA_E directory already exists
    if [ -d "KIBANA_E" ]; then
        echo -e "${YELLOW}Virtual environment directory already exists.${NC}"
        echo -e "${YELLOW}Activating existing virtual environment...${NC}"
    else
        echo -e "${YELLOW}Creating new virtual environment...${NC}"
        python3 -m venv KIBANA_E
    fi
    
    # Activate the virtual environment
    source KIBANA_E/bin/activate
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" == *"KIBANA_E"* ]]; then
        echo -e "${GREEN}Virtual environment activated successfully.${NC}"
    else
        echo -e "${RED}Failed to activate virtual environment.${NC}"
        exit 1
    fi
}

# Install required packages
install_requirements() {
    echo -e "${YELLOW}Installing required Python packages...${NC}"
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully installed all required packages.${NC}"
    else
        echo -e "${RED}Error installing packages. Please check the error messages above.${NC}"
        exit 1
    fi
}

# Make run script executable
make_run_script_executable() {
    echo -e "${YELLOW}Making run_kibana_mcp.sh executable...${NC}"
    chmod +x run_kibana_mcp.sh
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully made run_kibana_mcp.sh executable.${NC}"
    else
        echo -e "${RED}Error making run_kibana_mcp.sh executable.${NC}"
        exit 1
    fi
}

# Main execution flow
main() {
    # Install prerequisites
    install_python
    
    # Setup the environment
    setup_virtualenv
    install_requirements
    
    # Make run script executable
    make_run_script_executable
    
    echo -e "${GREEN}=== Setup Complete ===${NC}"
    echo -e "${GREEN}To start the server, run: ./run_kibana_mcp.sh${NC}"
}

# Run the main function
main 