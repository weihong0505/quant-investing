# -*- coding: utf-8 -*-
"""
Obsidian + Local REST API + Wiki 一键配置脚本
用法: 安装完 Obsidian 后双击运行此脚本
"""
import os
import sys
import json
import subprocess
import time

WIKI_PATH = r"G:\股市探究\quant-investing\wiki"
OBSIDIAN_DIR = os.path.join(WIKI_PATH, ".obsidian")
PLUGIN_DIR = os.path.join(OBSIDIAN_DIR, "plugins", "local-rest-api")

print("=" * 60)
print("  Obsidian + Local REST API 一键配置")
print("=" * 60)

# Step 1: 检查 Obsidian 是否安装
print("\n[1/5] 检查 Obsidian 安装...")
obsidian_path = None
for p in [
    r"C:\Users\asus\AppData\Local\Programs\obsidian\Obsidian.exe",
    r"C:\Users\asus\AppData\Local\Obsidian\Obsidian.exe",
]:
    if os.path.exists(p):
        obsidian_path = p
        break

if not obsidian_path:
    # Try to find it
    result = subprocess.run(
        ['where', 'obsidian'], capture_output=True, text=True
    )
    if result.returncode == 0:
        obsidian_path = result.stdout.strip().split('\n')[0]

if obsidian_path:
    print(f"  ✅ 找到 Obsidian: {obsidian_path}")
else:
    print("  ❌ 未找到 Obsidian，请先安装")
    print("  下载地址: https://obsidian.md/download")
    input("  安装完成后按回车继续...")
    # Re-check
    for p in [
        r"C:\Users\asus\AppData\Local\Programs\obsidian\Obsidian.exe",
        r"C:\Users\asus\AppData\Local\Obsidian\Obsidian.exe",
    ]:
        if os.path.exists(p):
            obsidian_path = p
            break

# Step 2: 创建 .obsidian 配置
print("\n[2/5] 配置 Obsidian vault...")
os.makedirs(OBSIDIAN_DIR, exist_ok=True)

# app.json
app_config = {
    "baseFontSize": 16,
    "theme": "obsidian",
    "translucency": False,
    "showLineNumber": True,
    "strictLineBreaks": False,
}
with open(os.path.join(OBSIDIAN_DIR, "app.json"), "w", encoding="utf-8") as f:
    json.dump(app_config, f, indent=2)
print("  ✅ app.json 已写入")

# Step 3: 安装 Local REST API 插件
print("\n[3/5] 安装 Local REST API 插件...")
os.makedirs(PLUGIN_DIR, exist_ok=True)

# 检查插件文件是否已存在
plugin_files = ["main.js", "manifest.json", "styles.css"]
all_exist = all(os.path.exists(os.path.join(PLUGIN_DIR, f)) for f in plugin_files)

if not all_exist:
    print("  下载插件文件...")
    try:
        import requests
        s = requests.Session()
        s.proxies = {"http": None, "https": None}
        base = "https://github.com/coddingtonbear/obsidian-local-rest-api/releases/latest/download"
        for f in plugin_files:
            url = f"{base}/{f}"
            out = os.path.join(PLUGIN_DIR, f)
            r = s.get(url, timeout=30)
            if r.status_code == 200:
                with open(out, "wb") as fh:
                    fh.write(r.content)
                print(f"    {f} ✅")
            else:
                print(f"    {f} ❌ HTTP {r.status_code}")
    except Exception as e:
        print(f"  ⚠️ 下载失败: {e}")
        print("  请手动下载: https://github.com/coddingtonbear/obsidian-local-rest-api/releases")
else:
    print("  ✅ 插件文件已存在")

# 启用插件
community_plugins = os.path.join(OBSIDIAN_DIR, "community-plugins.json")
if os.path.exists(community_plugins):
    with open(community_plugins, "r", encoding="utf-8") as f:
        plugins = json.load(f)
else:
    plugins = []

if "local-rest-api" not in plugins:
    plugins.append("local-rest-api")
    with open(community_plugins, "w", encoding="utf-8") as f:
        json.dump(plugins, f)
    print("  ✅ 插件已启用")
else:
    print("  ✅ 插件已启用")

# Step 4: 启动 Obsidian 打开 Wiki vault
print("\n[4/5] 启动 Obsidian...")
if obsidian_path:
    print(f"  打开 vault: {WIKI_PATH}")
    subprocess.Popen([obsidian_path, WIKI_PATH])
    print("  ✅ Obsidian 已启动")
    print("  ⏳ 等待10秒让插件加载...")
    time.sleep(10)
else:
    print("  ⚠️ 未找到 Obsidian，请手动打开")
    print(f"  打开后选择 Open vault → {WIKI_PATH}")

# Step 5: 获取 API Key
print("\n[5/5] 获取 API Key...")
print("  请在 Obsidian 中：")
print("  1. 点击左下角设置图标（或 Ctrl+,）")
print("  2. 左侧找到 'Local REST API'")
print("  3. 复制 API Key")
print("  4. 粘贴到下方：")

api_key = input("\n  API Key: ").strip()
if api_key:
    # 保存到 vault 之外（2026-09-18 改：密钥不入库，见 FMS 反模式）
    env_dir = r"G:\deeeseek\secrets"
    os.makedirs(env_dir, exist_ok=True)
    env_file = os.path.join(env_dir, "quant-investing-wiki.env")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"OBSIDIAN_API_KEY={api_key}\n")
        f.write(f"OBSIDIAN_API_URL=http://localhost:27123\n")
    print(f"  ✅ API Key 已保存到 {env_file}（vault 之外，不入库）")

    # 测试连接
    print("\n  测试 API 连接...")
    try:
        import requests
        r = requests.get(
            "http://localhost:27123/vault/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if r.status_code == 200:
            print("  ✅ API 连接成功！")
            data = r.json()
            print(f"  找到 {len(data.get('files', []))} 个文件")
        else:
            print(f"  ⚠️ API 返回 {r.status_code}")
    except Exception as e:
        print(f"  ⚠️ 连接失败: {e}")
        print("  请确保 Obsidian 已启动且插件已启用")
else:
    print("  ⏭️ 跳过（可稍后配置）")

print("\n" + "=" * 60)
print("  配置完成！")
print("=" * 60)
print(f"\n  Wiki 目录: {WIKI_PATH}")
print(f"  Obsidian: {obsidian_path or '未找到'}")
print(f"  API 插件: Local REST API")
print(f"\n  后续使用：")
print(f"  - Obsidian 中打开 wiki/ 即可浏览知识图谱")
print(f"  - Hermes Agent 可通过 API 实时读写 Wiki")
print(f"  - 在 Obsidian 中编辑的笔记，Hermes 也能感知")
