import os
import requests
import subprocess
import json

# GitHub Action 中的工作目录
OUTPUT_DIR = "rule-set"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 三条广告规则源（合并为 adblock.txt）
adblock_urls = [
    "https://raw.githubusercontent.com/jackszb/json-txt-2/main/domains.txt",
]

# 输出文件名改为 adblock
raw_file_path = os.path.join(OUTPUT_DIR, "adblock.txt")
srs_file_path = os.path.join(OUTPUT_DIR, "adblock.srs")

# 路由分流规则链接
routing_domain = {
    "direct": {
        "apple-cn": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-apple@cn.srs",
        "apple-pki-cn": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-apple-pki@cn.srs",
        "apple-dev-cn": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-apple-dev@cn.srs",
        "cctv": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cctv.srs",
        "bilibili": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-bilibili.srs",
        "wechat": "https://raw.githubusercontent.com/jackszb/sing-box-abc/main/wechat.srs",
        "geosite-private": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-private.srs",
        "geosite-cn": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
    },
    "proxy": {
        "github": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-github.srs",
        "openai": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-openai.srs",
        "youtube": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-youtube.srs",
        "geosite-geolocation-!cn": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-geolocation-!cn.srs",
    },
}

# 路由分流IP规则链接
routing_ip = {
    "direct": {
        "geoip-cn": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "geoip-private": "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/private.srs",
    },
    "proxy": {
        "telegram": "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/telegram.srs",
        "netflix": "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/netflix.srs",
        "google": "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/google.srs",
        "twitter": "https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/twitter.srs",
    },
}

# 下载广告规则 → 合并为 adblock.txt
def download_filter():
    print("Downloading and merging adblock rules...")

    all_lines = set()

    for u in adblock_urls:
        r = requests.get(u)
        r.raise_for_status()
        for line in r.text.splitlines():
            line = line.strip()
            if line:
                all_lines.add(line)

    # 合并并写入 adblock.txt
    with open(raw_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_lines)) + "\n")

    print("Merged adblock.txt generated.")


# 使用 sing-box 转换规则为 SRS 格式
def convert_with_sing_box():
    print("Converting adblock.txt with sing-box...")
    result = subprocess.run(
        [
            "sing-box",
            "rule-set",
            "convert",
            "--type",
            "adguard",
            "--output",
            srs_file_path,
            raw_file_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("sing-box conversion failed")
    print("adblock.srs generated.")


# 提交更改到 Git
def git_commit_changes():
    # 检查 Git 状态，查看是否有未提交的更改
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
    )
    if result.stdout:
        print("Unstaged changes detected. Committing changes...")
        # 暂存所有更改
        subprocess.run(["git", "add", "."])
        # 提交更改
        subprocess.run(['git', 'commit', '-m', 'Auto commit changes after rule update'])


def decompile_srs_to_json(srs_path, json_path):
    result = subprocess.run(
        ["sing-box", "rule-set", "decompile", srs_path, "-o", json_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def compile_json_to_srs(json_path, srs_path):
    result = subprocess.run(
        ["sing-box", "rule-set", "compile", json_path, "-o", srs_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def process_routing_rule(name, url):
    compiled_srs = os.path.join(OUTPUT_DIR, f"{name}.srs")
    json_path = os.path.join(OUTPUT_DIR, f"{name}.json")

    print(f"Downloading routing rule {name} from {url}...")
    response = requests.get(url)
    response.raise_for_status()

    # 保存 .srs
    with open(compiled_srs, "wb") as f:
        f.write(response.content)

    decompile_srs_to_json(compiled_srs, json_path)
    print(f"{name} routing rule processed.")


# 合并所有 routing JSON
def merge_routing_json(output_file, input_prefixes):
    merged_version = None
    merged_rules = {}

    for prefix in input_prefixes:
        for file in os.listdir(OUTPUT_DIR):
            if file.endswith(".json") and file.startswith(prefix):
                path = os.path.join(OUTPUT_DIR, file)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if merged_version is None:
                        merged_version = data.get("version")

                    rules = data.get("rules", [])
                    for rule in rules:
                        for key, value in rule.items():
                            if not value:
                                continue

                            if key not in merged_rules:
                                merged_rules[key] = set()

                            if isinstance(value, list):
                                merged_rules[key].update(value)
                            else:
                                merged_rules[key].add(value)

    final = {
        "version": merged_version if merged_version else 1,
        "rules": [{k: sorted(list(v)) for k, v in merged_rules.items()}],
    }

    with open(os.path.join(OUTPUT_DIR, output_file), "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 清空目录
    for file in os.listdir(OUTPUT_DIR):
        os.remove(os.path.join(OUTPUT_DIR, file))

    # 生成 adblock.srs
    download_filter()
    convert_with_sing_box()

    # 处理 domain rules
    for name, url in routing_domain["direct"].items():
        process_routing_rule(name, url)

    for name, url in routing_domain["proxy"].items():
        process_routing_rule(name, url)

    # 处理 IP rules
    for name, url in routing_ip["direct"].items():
        process_routing_rule(name, url)

    for name, url in routing_ip["proxy"].items():
        process_routing_rule(name, url)

    # 合并 direct domain
    merge_routing_json("merged-domain-direct.json", list(routing_domain["direct"].keys()))
    compile_json_to_srs(
        os.path.join(OUTPUT_DIR, "merged-domain-direct.json"),
        os.path.join(OUTPUT_DIR, "merged-domain-direct.srs"),
    )

    # 合并 proxy domain
    merge_routing_json("merged-domain-proxy.json", list(routing_domain["proxy"].keys()))
    compile_json_to_srs(
        os.path.join(OUTPUT_DIR, "merged-domain-proxy.json"),
        os.path.join(OUTPUT_DIR, "merged-domain-proxy.srs"),
    )

    # 合并 direct IP
    merge_routing_json("merged-ip-direct.json", list(routing_ip["direct"].keys()))
    compile_json_to_srs(
        os.path.join(OUTPUT_DIR, "merged-ip-direct.json"),
        os.path.join(OUTPUT_DIR, "merged-ip-direct.srs"),
    )

    # 合并 proxy IP
    merge_routing_json("merged-ip-proxy.json", list(routing_ip["proxy"].keys()))
    compile_json_to_srs(
        os.path.join(OUTPUT_DIR, "merged-ip-proxy.json"),
        os.path.join(OUTPUT_DIR, "merged-ip-proxy.srs"),
    )

    # 最终只保留 5 个文件
    KEEP = {
        "adblock.srs",
        "merged-domain-direct.srs",
        "merged-domain-proxy.srs",
        "merged-ip-direct.srs",
        "merged-ip-proxy.srs",
    }

    for file in os.listdir(OUTPUT_DIR):
        if file not in KEEP:
            os.remove(os.path.join(OUTPUT_DIR, file))

    print("All done. Final SRS files generated.")

    # 提交更改到 Git
    git_commit_changes()
