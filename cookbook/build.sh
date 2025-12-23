#!/bin/bash

# Multiple versions to build
VERSIONS=("preview" "v1.0.3" "v1.0.2" "v1.0.1" "v1.0.0" "v0.2.0")
OUTPUT_DIR="_build"

# ANSI color codes for better display
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Function to display usage instructions
usage() {
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}                           JUPYTER BOOK BUILDER${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${YELLOW}Usage:${NC} $0 [-p]"
  echo -e "${YELLOW}Options:${NC}"
  echo -e "  ${GREEN}-p${NC}   Preview the book after building"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  exit 1
}

# Function to print step headers
print_step() {
  echo -e "\n${CYAN}▶${NC} ${BLUE}$1${NC}"
  echo -e "${CYAN}─────────────────────────────────────────────────────────────────────────────────${NC}"
}

# Function to print success message
print_success() {
  echo -e "${GREEN}✓${NC} $1"
}

# Function to print error message
print_error() {
  echo -e "${RED}✗${NC} $1" >&2
}

# Function to print info message
print_info() {
  echo -e "${YELLOW}ℹ${NC} $1"
}

# Function to print warning message
print_warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

# Check for the -p flag
PREVIEW=false
while getopts ":p" opt; do
  case ${opt} in
    p )
      PREVIEW=true
      ;;
    \? )
      print_error "Invalid option: -$OPTARG"
      usage
      ;;
  esac
done

# Header
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}                           JUPYTER BOOK BUILDER${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if we're in a Jupyter Book directory
if [ ! -f "_config.yml" ] && [ ! -f "_toc.yml" ]; then
  print_warning "This doesn't appear to be a Jupyter Book directory"
  print_info "Make sure you're in the root directory of your Jupyter Book project"
fi

# Clean previous builds
print_step "Cleaning previous builds"
if jupyter-book clean . >/dev/null 2>&1; then
  print_success "Previous builds cleaned successfully"
else
  print_error "Failed to clean previous builds"
  exit 1
fi

INITIAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)
print_step "Current branch: $INITIAL_BRANCH"

# Build the Jupyter Book
for version in "${VERSIONS[@]}"; do
    print_step "Building version: $version"

    if [ "$version" != "preview" ]; then
        if git checkout "$version"; then
            print_success "Switched to $version"
        else
            print_error "Failed to checkout $version"
            git checkout "$INITIAL_BRANCH" 2>/dev/null
            git stash pop 2>/dev/null || true
            exit 1
        fi
    fi

    if jupyter-book build . --path-output $OUTPUT_DIR/$version; then
      print_success "Jupyter Book built successfully"
      if [ "$version" != "preview" ]; then
          print_step "Moving $version HTML to preview directory"

          if mv $OUTPUT_DIR/$version/_build/html $OUTPUT_DIR/preview/_build/html/$version; then
                print_success "Successfully moved $version to preview dir"
          else
              print_error "Failed to move $version to preview"
              git checkout "$INITIAL_BRANCH" 2>/dev/null
              git stash pop 2>/dev/null || true
              exit 1
          fi
      else
          print_step "Stash uncommitted changes."
          git stash
      fi
    else
      print_error "Failed to build Jupyter Book"
      git checkout "$INITIAL_BRANCH" 2>/dev/null
      git stash pop 2>/dev/null || true
      exit 1
    fi
done

# Switch back to initial branch
print_step "Switching back to initial branch: $INITIAL_BRANCH"
if git checkout "$INITIAL_BRANCH"; then
    print_success "Successfully switched back to $INITIAL_BRANCH"
    git stash pop 2>/dev/null || true
else
    print_error "Failed to switch back to $INITIAL_BRANCH"
    exit 1
fi

# Check if preview is requested
if [ "$PREVIEW" = true ]; then
  print_step "Starting preview server"
  # Check if $OUTPUT_DIR/preview/_build/html directory exists
  if [ ! -d "$OUTPUT_DIR/preview/_build/html" ]; then
    print_error "Build directory not found. Please ensure the build completed successfully."
    exit 1
  fi

  # Check if port 8000 is already in use
  if command -v lsof >/dev/null 2>&1 && lsof -i :8000 >/dev/null 2>&1; then
    print_warning "Port 8000 is already in use"
    print_info "Trying to find an available port..."
    PORT=8001
    while lsof -i :$PORT >/dev/null 2>&1 && [ $PORT -lt 9000 ]; do
      PORT=$((PORT + 1))
    done
    print_info "Using port $PORT instead"
  else
    PORT=8000
  fi

  print_success "Preview server starting..."
  print_info "Open your browser and visit: ${GREEN}http://localhost:$PORT${NC}"
  print_info "Press ${RED}Ctrl+C${NC} to stop the server"
  echo -e "${CYAN}─────────────────────────────────────────────────────────────────────────────────${NC}\n"
  # Start a simple HTTP server in the $OUTPUT_DIR/preview/_build/html directory
  python -m http.server --directory $OUTPUT_DIR/preview/_build/html $PORT
else
  print_step "Build Summary"
  print_success "Build completed successfully!"
  print_info "To build and preview the book, run: ${GREEN}$0 -p${NC}"
  print_info "Build output available in: ${BLUE}$OUTPUT_DIR/preview/_build/html/${NC}"
  # Show file size if possible
  if command -v du >/dev/null 2>&1; then
    BUILD_SIZE=$(du -sh $OUTPUT_DIR/preview/_build/html 2>/dev/null | cut -f1)
    [ -n "$BUILD_SIZE" ] && print_info "Total build size: $BUILD_SIZE"
  fi
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi