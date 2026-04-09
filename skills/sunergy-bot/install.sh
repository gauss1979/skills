#!/bin/bash
#===============================================
# sunergy-bot 技能安装脚本 v1.0.0
# 适用系统: Linux / macOS / Windows (WSL)
# 安装方式:
#   bash <(curl -fsSL https://raw.githubusercontent.com/gauss1979/skills/v1.0.0/skills/sunergy-bot/install.sh)
#===============================================
set -e

VERSION="v1.0.0"
SKILL_NAME="sunergy-bot"
SKILL_DIR="$HOME/.openclaw/workspace/skills/${SKILL_NAME}"
TOKEN_DIR="$HOME/.sunergy-bot"
PYTHON_CMD="${PYTHON_CMD:-python3}"

# GitHub 分发地址
BASE_URL="https://github.com/gauss1979/skills/archive/refs/tags/${VERSION}.tar.gz"
DIST_LABEL="skills-${VERSION}"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }

echo ""
echo "========================================"
echo "  sunergy-bot 安装脚本 ${VERSION}"
echo "  Sunergy 能源管理 · 图表与数据分析"
echo "========================================"
echo ""

# ---- 0. 判定运行方式 ----
RUNNING_VIA_CURL=false
if [ -z "$INSTALLER_DIR" ]; then
    RUNNING_VIA_CURL=true
    INSTALLER_DIR=$(mktemp -d)
    info "通过管道下载模式运行，建立临时目录: $INSTALLER_DIR"
    TAR_PATH="$INSTALLER_DIR/${DIST_LABEL}.tar.gz"
    info "下载分发包..."
    if ! curl -fsSL "$BASE_URL" -o "$TAR_PATH"; then
        error "下载失败，请检查网络"
        rm -rf "$INSTALLER_DIR"
        exit 1
    fi
    info "解压分发包..."
    if ! tar -xzf "$TAR_PATH" -C "$INSTALLER_DIR"; then
        error "解压失败"
        rm -rf "$INSTALLER_DIR"
        exit 1
    fi
    rm -f "$TAR_PATH"
fi

DIST_DIR="$INSTALLER_DIR/${DIST_LABEL}/sunergy-bot"

# ---- 1. 检测 Python ----
info "检测 Python 环境..."
if ! command -v $PYTHON_CMD &>/dev/null; then
    error "未找到 python3，请先安装 Python 3.6+"
    [ "$RUNNING_VIA_CURL" = true ] && rm -rf "$INSTALLER_DIR"
    exit 1
fi
PY_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
info "Python 版本: $PY_VERSION"

# ---- 2. 创建目录 ----
info "创建技能目录: $SKILL_DIR"
mkdir -p "$SKILL_DIR/scripts"
mkdir -p "$TOKEN_DIR"

# ---- 3. 复制技能文件 ----
info "安装技能文件..."
cp "$DIST_DIR/SKILL.md"        "$SKILL_DIR/SKILL.md"
cp "$DIST_DIR/package.json"     "$SKILL_DIR/package.json"
cp -r "$DIST_DIR/scripts/"*      "$SKILL_DIR/scripts/"
chmod +x "$SKILL_DIR/scripts/"*.py
success "技能文件已安装"

# ---- 4. matplotlib 检查 ----
info "检查 matplotlib..."
if $PYTHON_CMD -c "import matplotlib" 2>/dev/null; then
    success "matplotlib 已安装（图表功能可用）"
else
    warn "matplotlib 未安装，图表功能将不可用。"
    warn "如需图表，执行: pip install matplotlib"
fi

# ---- 5. pandas 检查（用于数据处理）----
info "检查 pandas..."
if $PYTHON_CMD -c "import pandas" 2>/dev/null; then
    success "pandas 已安装"
else
    warn "pandas 未安装，收益分析功能可能受影响。"
    warn "如需完整功能，执行: pip install pandas"
fi

# ---- 6. 清理临时目录（管道模式）----
if [ "$RUNNING_VIA_CURL" = true ]; then
    rm -rf "$INSTALLER_DIR"
    info "临时文件已清理"
fi

# ---- 7. Token 配置引导 ----
echo ""
echo "========================================"
echo "  Token 配置"
echo "========================================"
configure_token=0
if [ -f "$TOKEN_DIR/token" ] && [ -s "$TOKEN_DIR/token" ]; then
    info "已存在 Token 文件: $TOKEN_DIR/token"
    read -p "是否重新配置 Token？[y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        configure_token=1
    fi
else
    configure_token=1
fi

if [ "$configure_token" = "1" ]; then
    echo ""
    read -p "请输入 Sunergy Bearer Token（留空则使用内置默认Token）: " INPUT_TOKEN
    if [ -n "$INPUT_TOKEN" ]; then
        echo "$INPUT_TOKEN" > "$TOKEN_DIR/token"
        chmod 600 "$TOKEN_DIR/token"
        success "Token 已保存到 $TOKEN_DIR/token"
    else
        info "使用内置默认 Token"
    fi
fi

# ---- 8. 完成 ----
echo ""
echo "========================================"
success "安装完成!"
echo "========================================"
echo ""
echo "  技能目录: $SKILL_DIR"
echo "  Token 目录: $TOKEN_DIR"
echo ""
echo "  常用命令:"
echo "    python3 $SKILL_DIR/scripts/report_all.py                    # 全站概览报告"
echo "    python3 $SKILL_DIR/scripts/chart_power.py <站点ID> 2026-04-08   # 日功率图表"
echo "    python3 $SKILL_DIR/scripts/chart_month.py <站点ID> 2026-04      # 月统计图表"
echo "    python3 $SKILL_DIR/scripts/chart_earnings.py <站点ID> week       # 收益图表"
echo ""
echo "  技能说明: $SKILL_DIR/SKILL.md"
echo ""
