#!/bin/bash
#===============================================
# amber-electric 技能安装脚本
# 适用系统: Linux / macOS / Windows (WSL)
# 安装方式: bash <(curl -fsSL <URL>) 或手动下载运行
#===============================================
set -e

SKILL_NAME="amber-electric"
SKILL_DIR="$HOME/.openclaw/workspace/skills/${SKILL_NAME}"
INSTALLER_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }

echo ""
echo "========================================"
echo "  amber-electric 安装脚本"
echo "  Amber Electric · 澳大利亚能源API"
echo "========================================"
echo ""

# ---- 1. 检测 Python ----
info "检测 Python 环境..."
if ! command -v $PYTHON_CMD &>/dev/null; then
    error "未找到 python3，请先安装 Python 3.6+"
    exit 1
fi
PY_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
info "Python 版本: $PY_VERSION"

# ---- 2. 创建技能目录 ----
info "创建技能目录: $SKILL_DIR"
mkdir -p "$SKILL_DIR/scripts"
mkdir -p "$HOME/.amber"

# ---- 3. 复制技能文件 ----
info "安装技能文件..."
cp "$INSTALLER_DIR/SKILL.md"        "$SKILL_DIR/SKILL.md"
cp "$INSTALLER_DIR/_meta.json"      "$SKILL_DIR/_meta.json"
cp "$INSTALLER_DIR/scripts/amber.py" "$SKILL_DIR/scripts/amber.py"
chmod +x "$SKILL_DIR/scripts/amber.py"
success "技能文件已安装"

# ---- 4. 软链接到 PATH（可选）----
BIN_LINK="$HOME/.local/bin/amber.py"
if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$SKILL_DIR/scripts/amber.py" "$BIN_LINK" 2>/dev/null || true
    info "已创建软链接: $BIN_LINK（可选）"
fi

# ---- 5. matplotlib 提示 ----
info "检查 matplotlib..."
if $PYTHON_CMD -c "import matplotlib" 2>/dev/null; then
    success "matplotlib 已安装（图表功能可用）"
else
    warn "matplotlib 未安装，图表功能将不可用。"
    warn "如需图表，执行: pip install matplotlib"
fi

# ---- 6. Token 配置引导 ----
echo ""
echo "========================================"
echo "  Token 配置"
echo "========================================"
if [ -f "$HOME/.amber/token" ] && [ -s "$HOME/.amber/token" ]; then
    CURRENT_TOKEN=$(cat "$HOME/.amber/token")
    info "已存在 Token: ${CURRENT_TOKEN:0:8}...${CURRENT_TOKEN: -4}"
    read -p "是否重新配置 Token？[y/N]: " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        info "跳过 Token 配置"
    else
        configure_token=1
    fi
else
    configure_token=1
fi

if [ "$configure_token" = "1" ]; then
    echo ""
    echo -e "请前往 ${YELLOW}https://www.amber.com.au/developers${NC} 获取 Token"
    echo "Token 格式: psk_xxx"
    read -p "请输入你的 Amber Token（或直接回车稍后配置）: " INPUT_TOKEN
    if [ -n "$INPUT_TOKEN" ]; then
        $PYTHON_CMD "$SKILL_DIR/scripts/amber.py" login "$INPUT_TOKEN"
    else
        info "Token 配置已跳过，可稍后运行: amber.py login <TOKEN>"
    fi
fi

# ---- 7. 完成 ----
echo ""
echo "========================================"
success "安装完成!"
echo "========================================"
echo ""
echo "  技能目录: $SKILL_DIR"
echo "  Token 文件: $HOME/.amber/token"
echo ""
echo "  常用命令:"
echo "    amber.py list                        # 查看所有站点"
echo "    amber.py price                       # 当前电价"
echo "    amber.py forecast 4                   # 未来4小时预测"
echo "    amber.py usage 昨天                   # 昨天用量"
echo "    amber.py login <token>               # 配置/测试 Token"
echo ""
echo "  技能说明: $SKILL_DIR/SKILL.md"
echo ""
