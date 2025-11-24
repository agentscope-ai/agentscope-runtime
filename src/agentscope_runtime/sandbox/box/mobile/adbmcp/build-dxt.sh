#!/usr/bin/env bash

set -euo pipefail

# Build the project first
echo "Building project..."
npm run build

# Update manifest.json with version from package.json
echo "Updating manifest version..."
VERSION=$(node -p "require('./package.json').version")
sed "s/{{VERSION}}/$VERSION/g" manifest.json > manifest.json.tmp
mv manifest.json.tmp manifest.json

# Remove devDependencies
echo "Removing devDependencies and types from node_modules..."
rm -rf node_modules
npm ci --omit=dev --audit false --fund false
find node_modules -name "*.ts" -type f -delete 2>/dev/null || true

# Create the DXT package
echo "Creating DXT package..."
rm -rf computer-use-mcp.dxt
# --no-dir-entries: https://github.com/anthropics/dxt/issues/18#issuecomment-3021467806
zip --recurse-paths --no-dir-entries \
  computer-use-mcp.dxt \
  manifest.json \
  icon.png \
  dist/ \
  node_modules/ \
  package.json \
  README.md \
  LICENSE

# Restore the template version
echo "Restoring manifest template..."
sed "s/$VERSION/{{VERSION}}/g" manifest.json > manifest.json.tmp
mv manifest.json.tmp manifest.json

# Restore full node_modules
echo "Restoring node_modules..."
npm ci --audit false --fund false

echo
echo "DXT package created: computer-use-mcp.dxt ($(du -h computer-use-mcp.dxt | cut -f1))"