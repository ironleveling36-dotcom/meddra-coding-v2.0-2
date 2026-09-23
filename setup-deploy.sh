#!/bin/bash
# Setup script for GitHub + Render deployment
# Usage: bash setup-deploy.sh

set -e

echo "🚀 MedDRA Coding Assistant — GitHub + Render Setup"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git not installed. Please install Git first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git installed${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not installed. Please install Python 3.10+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 installed$(python3 --version 2>&1 | cut -d' ' -f2)${NC}"

echo ""
echo -e "${BLUE}🔧 Step 1: Initialize Git Repository${NC}"

# Check if already a git repo
if [ -d ".git" ]; then
    echo -e "${YELLOW}⚠️  Already a git repository${NC}"
else
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
fi

# Set git config
read -p "Enter your GitHub username: " github_username
read -p "Enter your repository name [meddra-coding-assistant]: " repo_name
repo_name=${repo_name:-meddra-coding-assistant}

echo ""
echo -e "${BLUE}📝 Step 2: Create .gitignore and essential files${NC}"

# .gitignore already created, check
if [ -f ".gitignore" ]; then
    echo -e "${GREEN}✓ .gitignore exists${NC}"
else
    cp /path/to/.gitignore . 2>/dev/null || echo "Create .gitignore manually if needed"
fi

# Create render.yaml if not exists
if [ ! -f "render.yaml" ]; then
    cat > render.yaml << 'EOF'
services:
  - type: web
    name: meddra-coding
    env: python
    buildCommand: pip install -r requirements.txt && python scripts/build_index.py
    startCommand: gunicorn -w 4 -b 0.0.0.0:$PORT app.main:app
    healthCheckPath: /health
    autoDeploy: true
    branch: main
EOF
    echo -e "${GREEN}✓ render.yaml created${NC}"
else
    echo -e "${GREEN}✓ render.yaml exists${NC}"
fi

# Create GitHub workflows directory if needed
mkdir -p .github/workflows 2>/dev/null || true

echo ""
echo -e "${BLUE}📦 Step 3: Verify Python dependencies${NC}"

if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}✓ requirements.txt found${NC}"
    echo "  Dependencies:"
    grep -E "^[a-zA-Z]" requirements.txt | head -5 | sed 's/^/    - /'
    echo "    ... (and more)"
else
    echo -e "${YELLOW}⚠️  requirements.txt not found${NC}"
    echo "   Please ensure requirements.txt exists in project root"
fi

echo ""
echo -e "${BLUE}📁 Step 4: Verify project structure${NC}"

dirs=("app" "data" "static" "scripts")
for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓ $dir/ exists${NC}"
    else
        echo -e "${YELLOW}⚠️  $dir/ not found${NC}"
    fi
done

echo ""
echo -e "${BLUE}🔑 Step 5: Configure Git remote${NC}"

git_url="https://github.com/${github_username}/${repo_name}.git"
echo "Repository URL: $git_url"

# Check if remote already exists
if git remote get-url origin &>/dev/null; then
    current_url=$(git remote get-url origin)
    if [ "$current_url" != "$git_url" ]; then
        echo -e "${YELLOW}⚠️  Existing remote found. Updating...${NC}"
        git remote remove origin
        git remote add origin "$git_url"
        echo -e "${GREEN}✓ Remote updated${NC}"
    else
        echo -e "${GREEN}✓ Remote already configured${NC}"
    fi
else
    git remote add origin "$git_url"
    echo -e "${GREEN}✓ Remote configured${NC}"
fi

echo ""
echo -e "${BLUE}💾 Step 6: Initial commit${NC}"

if [ -z "$(git status --short)" ]; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
else
    git add -A
    git commit -m "Initial commit: MedDRA Coding Assistant v2.0 with SenseNova AI"
    echo -e "${GREEN}✓ Changes committed${NC}"
fi

echo ""
echo -e "${BLUE}🚀 Step 7: Set main branch${NC}"

if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
    git branch -M main
    echo -e "${GREEN}✓ Switched to main branch${NC}"
else
    echo -e "${GREEN}✓ Already on main branch${NC}"
fi

echo ""
echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo ""
echo "1️⃣  CREATE GITHUB REPOSITORY"
echo "   → Go to: https://github.com/new"
echo "   → Repository name: $repo_name"
echo "   → Description: AI-powered MedDRA search with SenseNova integration"
echo "   → Choose: Public (recommended) or Private"
echo "   → Click: Create repository"
echo ""

echo "2️⃣  PUSH TO GITHUB (run after creating repository):"
echo "   \$ git push -u origin main"
echo ""

echo "3️⃣  CONNECT RENDER"
echo "   → Go to: https://render.com"
echo "   → Sign up with GitHub"
echo "   → Dashboard → New Web Service"
echo "   → Select repository: $repo_name"
echo "   → Configure with render.yaml settings"
echo "   → Add Environment Variables:"
echo "      - AI_API_KEY (SenseNova key)"
echo "      - AI_ENABLED=true"
echo "      - AI_API_BASE_URL=https://api.hcnsec.cn/v1"
echo "      - AI_MODEL=sensenova-6.8-flash-lite"
echo ""

echo "4️⃣  DEPLOY"
echo "   → Render automatically deploys on git push"
echo "   → Check: Service → Logs"
echo ""

echo "5️⃣  ACCESS"
echo "   → Your service URL: https://meddra-coding-xxxx.onrender.com"
echo ""

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "For more details, see GITHUB_RENDER_GUIDE.md"
echo ""

# Optional: Push to GitHub
read -p "Push to GitHub now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing to GitHub..."
    git push -u origin main 2>&1 || {
        echo -e "${RED}❌ Push failed. Make sure repository exists on GitHub first.${NC}"
        echo "   Create at: https://github.com/new"
        exit 1
    }
    echo -e "${GREEN}✓ Pushed to GitHub${NC}"
    echo "Visit: https://github.com/$github_username/$repo_name"
fi
