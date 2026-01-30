#!/bin/bash

# LAIOpt Deployment Script
# This script handles local deployment of the LAIOpt application

set -e  # Exit on error

echo "=========================================="
echo "LAIOpt - AI-Assisted Chip Layout Optimizer"
echo "Deployment Script"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo -e "${RED}Error: Python 3.9 or higher is required. Found: $python_version${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version OK: $python_version${NC}"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Install LAIOpt as package
echo "Installing LAIOpt as package..."
pip install -e .
echo -e "${GREEN}✓ LAIOpt package installed${NC}"
echo ""

# Check if data directory exists
if [ ! -d "laiopt/data" ]; then
    echo "Creating data directory..."
    mkdir -p laiopt/data
    echo -e "${GREEN}✓ Data directory created${NC}"
fi
echo ""

# Run the application
echo "=========================================="
echo "Starting LAIOpt application..."
echo "=========================================="
echo ""
echo "The application will be available at:"
echo -e "${GREEN}http://localhost:8501${NC}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run laiopt/frontend/app.py
