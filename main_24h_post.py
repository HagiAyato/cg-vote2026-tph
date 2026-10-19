import csv
import time
from datetime import datetime
from importlib import import_module
from pathlib import Path

from selenium.common.exceptions import WebDriverException


# ============================================================
# 設定
# ============================================================

# 入力CSV
INPUT_CSV = Path("idioms.csv")

# 出力先
OUTPUT_DIR = Path("data/24h_post")

# Yahoo!リアルタイム検索の24時間ポスト数取得関数
get_post_count = import_module(
    "src.24h_post_count"
).get_post_count

# 検索キーワード
SEARCH_QUERY_TEMPLATE = (
    "#シンデレラガール総選挙2026 {idol} に投票しました！"
)

# リクエスト間隔（秒）
# Yahoo側への負荷を抑えるため、少し間隔を空ける
REQUEST_INTERVAL_SECONDS = 0.1


# ============================================================
# CSV読み込み
# ============================================================

def load_idols(csv_path: Path) -> list[str]:
    """idioms.csvからアイドル名を読み込む。"""
    idols = []

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or "idol" not in reader.fieldnames:
            raise ValueError(
                f"{csv_path} に 'idol' 列がありません。"
            )

        for row in reader:
            idol = (row.get("idol") or "").strip()

            if idol:
                idols.append(idol)

    return idols


# ============================================================
# 結果CSV出力
# ============================================================

def write_results(
    output_path: Path,
    results: list[dict],
) -> None:
    """24時間のポスト数をCSVに出力する。"""
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "idol_name",
        "post_count",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)


# ============================================================
# メイン処理
# ============================================================

def main() -> None:
    """各アイドルの24時間以内のポスト数を取得する。"""
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"入力ファイルが見つかりません: {INPUT_CSV}"
        )

    idols = load_idols(INPUT_CSV)

    if not idols:
        raise ValueError(
            "idioms.csv にアイドル名がありません。"
        )

    print(f"アイドル数: {len(idols)}")
    print()

    results = []

    for index, idol in enumerate(idols, start=1):
        query = SEARCH_QUERY_TEMPLATE.format(idol=idol)

        print(
            f"[{index}/{len(idols)}] "
            f"{idol} を検索中..."
        )

        try:
            post_count = get_post_count(query)
            print(f"  24時間のポスト数: {post_count}")

        except (WebDriverException, ValueError) as exc:
            print(f"  エラー: {exc}")
            post_count = 0

        results.append(
            {
                "idol_name": idol,
                "post_count": post_count,
            }
        )

        if index < len(idols):
            time.sleep(REQUEST_INTERVAL_SECONDS)

    today = datetime.now().strftime("%Y%m%d")
    output_path = OUTPUT_DIR / f"result_{today}.csv"

    write_results(
        output_path,
        results,
    )

    print()
    print("処理完了")
    print(f"出力先: {output_path}")


if __name__ == "__main__":
    main()