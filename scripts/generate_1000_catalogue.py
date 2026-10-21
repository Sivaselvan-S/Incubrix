"""Script to generate a 1,000-destination benchmark CSV dataset for catalogue import testing."""

import csv
from pathlib import Path

PLATFORMS = [
    ("discourse", "forum", "technology"),
    ("lemmy", "community", "opensource"),
    ("ghost", "article", "engineering"),
    ("devto", "article", "software"),
    ("slack", "chat", "devops"),
    ("hashnode", "article", "cloud"),
    ("mrss_feed", "feed", "multimedia"),
    ("webhook_hmac", "bridge", "general"),
]


def generate_benchmark_csv(target_file: Path, total_rows: int = 1000) -> None:
    """Generates a realistic 1,000-row CSV destination catalogue with edge-case duplicates."""
    target_file.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "name",
        "url",
        "platform_key",
        "surface",
        "category",
        "language",
        "frequency_cap_days",
        "self_promo_allowed",
        "disclosure_required",
    ]

    with target_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for i in range(1, total_rows + 1):
            plat_key, surface, cat = PLATFORMS[(i - 1) % len(PLATFORMS)]
            name = f"{plat_key.capitalize()} Community Hub {i:04d}"
            base_url = f"https://destination-{i:04d}.{plat_key}.example.org"

            # Inject intentional duplicates and tracking parameters on 5% of rows
            if i % 20 == 0:
                # Same URL as i - 1 with www and utm tracking
                prev_i = i - 1
                prev_plat = PLATFORMS[(prev_i - 1) % len(PLATFORMS)][0]
                url = f"https://www.destination-{prev_i:04d}.{prev_plat}.example.org/?utm_source=twitter&ref=share"
            else:
                url = base_url

            freq_days = (i % 7) + 1
            self_promo = "true" if (i % 3 != 0) else "false"
            disclosure = "true" if (i % 4 == 0) else "false"

            writer.writerow([
                name,
                url,
                plat_key,
                surface,
                cat,
                "en",
                freq_days,
                self_promo,
                disclosure,
            ])


if __name__ == "__main__":
    out_path = Path("data") / "destinations_1000.csv"
    generate_benchmark_csv(out_path, 1000)
    print(f"Generated 1,000-row benchmark dataset at {out_path}")
