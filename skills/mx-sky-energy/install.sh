#!/bin/bash
#===============================================
# sunergy-energy 技能安装脚本 v1.0.1
# 适用系统: Linux / macOS / Windows (WSL)
# 安装方式:
#   bash <(curl -fsSL https://raw.githubusercontent.com/gauss1979/skills/v1.0.3/skills/mx-sky-energy/install.sh)
#===============================================
set -e

VERSION="v1.0.3"
SKILL_NAME="sunergy-energy"
SKILL_DIR="$HOME/.openclaw/workspace/skills/${SKILL_NAME}"
CRED_DIR="$HOME/.sunergy"
PYTHON_CMD="${PYTHON_CMD:-python3}"

# GitHub 分发地址（指向 v1.0.1 标签，Immutable）
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
echo "  sunergy-energy 安装脚本 ${VERSION}"
echo "  Sunergy 能源管理 · 站点监控与收益分析"
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
        error "下载失败，请检查网络，或前往 https://github.com/gauss1979/skills/releases/${VERSION} 手动下载"
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

DIST_DIR="$INSTALLER_DIR/${DIST_LABEL}/mx-sky-energy"

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
mkdir -p "$CRED_DIR"

# ---- 3. 复制技能文件 ----
info "安装技能文件..."
cp "$DIST_DIR/SKILL.md"             "$SKILL_DIR/SKILL.md"
cp "$DIST_DIR/scripts/mx_sky.py"    "$SKILL_DIR/scripts/mx_sky.py"
chmod +x "$SKILL_DIR/scripts/mx_sky.py"
success "技能文件已安装"

# ---- 4. matplotlib 检查 ----
info "检查 matplotlib..."
if $PYTHON_CMD -c "import matplotlib" 2>/dev/null; then
    success "matplotlib 已安装（图表功能可用）"
else
    warn "matplotlib 未安装，图表功能将不可用。"
    warn "如需图表，执行: pip install matplotlib"
fi

# ---- 5. 清理临时目录（管道模式）----
if [ "$RUNNING_VIA_CURL" = true ]; then
    rm -rf "$INSTALLER_DIR"
    info "临时文件已清理"
fi

# ---- 6. 凭证配置引导 ----
echo ""
echo "========================================"
echo "  凭证配置（Sunergy APP 手机号+密码）"
echo "========================================"
configure_creds=0
if [ -f "$CRED_DIR/credentials" ] && [ -s "$CRED_DIR/credentials" ]; then
    info "已存在凭证文件: $CRED_DIR/credentials"
    read -p "是否重新配置凭证？[y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        configure_creds=1
    fi
else
    configure_creds=1
fi

if [ "$configure_creds" = "1" ]; then
    echo ""
    read -p "请输入 Sunergy 登录手机号: " INPUT_PHONE
    read -sp "请输入 Sunergy 登录密码: " INPUT_PASSWORD
    echo ""
    if [ -n "$INPUT_PHONE" ] && [ -n "$INPUT_PASSWORD" ]; then
        echo "phone=$INPUT_PHONE" > "$CRED_DIR/credentials"
        echo "password=$INPUT_PASSWORD" >> "$CRED_DIR/credentials"
        chmod 600 "$CRED_DIR/credentials"
        success "凭证已保存到 $CRED_DIR/credentials"
    else
        warn "手机号或密码为空，凭证配置已跳过。"
        warn "请手动创建 $CRED_DIR/credentials："
        warn '  echo "phone=你的手机号" > ~/.sunergy/credentials'
        warn '  echo "password=你的密码" >> ~/.sunergy/credentials'
    fi
fi

# ---- 7. 测试登录 ----
if [ -f "$CRED_DIR/credentials" ] && [ -s "$CRED_DIR/credentials" ]; then
    echo ""
    info "正在测试登录..."
    if $PYTHON_CMD "$SKILL_DIR/scripts/mx_sky.py" list &>/dev/null; then
        success "登录成功，技能可正常使用！"
    else
        warn "登录测试失败，请检查凭证是否正确。"
        warn "凭证文件: $CRED_DIR/credentials"
    fi
fi

# ---- 8. 完成 ----
echo ""
echo "========================================"
success "安装完成!"
echo "========================================"
echo ""
echo "  技能目录: $SKILL_DIR"
echo "  凭证目录: $CRED_DIR"
echo ""
echo "  常用命令:"
echo "    python3 $SKILL_DIR/scripts/mx_sky.py list                  # 查看所有站点"
echo "    python3 $SKILL_DIR/scripts/mx_sky.py realtime <站点ID>    # 实时数据"
echo "    python3 $SKILL_DIR/scripts/mx_sky.py bess <站点ID>       # BESS状态"
echo "    python3 $SKILL_DIR/scripts/mx_sky.py report <站点ID>      # 综合报告"
echo ""
echo "  技能说明: $SKILL_DIR/SKILL.md"
echo ""
