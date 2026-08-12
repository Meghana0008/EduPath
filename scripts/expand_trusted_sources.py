from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "trusted_sources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {d.get("url") for d in data}
    extras = [
        {
            "name": "Digital Gujarat",
            "url": "https://www.digitalgujarat.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Gujarat state scholarship services.",
        },
        {
            "name": "MYSY Gujarat",
            "url": "https://mysy.guj.nic.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Mukhyamantri Yuva Swavalamban Yojana.",
        },
        {
            "name": "MahaDBT Maharashtra",
            "url": "https://mahadbt.maharashtra.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Maharashtra state scholarship DBT portal.",
        },
        {
            "name": "e-Grantz Kerala",
            "url": "https://www.egrantz.kerala.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Kerala post-matric scholarships.",
        },
        {
            "name": "Telangana ePASS",
            "url": "https://telanganaepass.cgg.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Telangana ePASS scholarships.",
        },
        {
            "name": "Jnanabhumi Andhra Pradesh",
            "url": "https://jnanabhumi.ap.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "AP scholarship services.",
        },
        {
            "name": "SSP Karnataka",
            "url": "https://ssp.postmatric.karnataka.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Karnataka state scholarship portal.",
        },
        {
            "name": "UP Scholarship",
            "url": "https://scholarship.up.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Uttar Pradesh scholarship portal.",
        },
        {
            "name": "MP Scholarship Portal",
            "url": "https://scholarshipportal.mp.nic.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "Madhya Pradesh scholarship portal.",
        },
        {
            "name": "OASIS West Bengal",
            "url": "https://oasis.gov.in/",
            "type": "government",
            "country": "IN",
            "enabled": True,
            "notes": "West Bengal OASIS scholarships.",
        },
    ]
    for row in extras:
        if row["url"] not in existing:
            data.append(row)
            existing.add(row["url"])
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("trusted sources", len(data))


if __name__ == "__main__":
    main()
