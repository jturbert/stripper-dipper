#!/bin/bash
# Run once to install dependencies and set up Playwright browsers.
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "Installing Playwright browsers (Chromium)..."
playwright install chromium

echo ""
echo "Setup complete. Run the tool with:"
echo "  python main.py <product-url>"
