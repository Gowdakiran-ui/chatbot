"""One-off helper (not a test) used to build golden_queries_{chanakya,crisis}.jsonl —
hand-picked (query, expected_chunk_ids) pairs, each verified against the real,
verified-good "_v1" collection before being kept. Not run as part of the suite; re-run
manually if the golden set ever needs regenerating.

Usage: python preprocessing/tests/_generate_golden_queries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from db.crisis_qdrant_client import get_client as xget
from db.embedding import embed_query
from db.qdrant_client import get_client as cget

OUT_DIR = Path(__file__).resolve().parent

# --- Chanakya candidates: (query, [acceptable chunk ids]) ---------------------------
CHANAKYA_CANDIDATES: list[tuple[str, list[str]]] = [
    ("what did the Arthashastra say about the Superintendent of Horses", ["arthashastra_book_ii_chapter_xxx_001"]),
    ("Arthashastra chapter on the Superintendent of Agriculture", ["arthashastra_book_ii_005"]),
    ("famine versus pestilence which is worse for a kingdom", ["arthashastra_book_viii_chapter_iv_002"]),
    ("what makes someone a real friend in times of danger and sickness", ["chanakya_neeti_chapter_6_verse_6_14_001"]),
    ("Chanakya Niti verse about grieving over the past or worrying about the future", ["chanakya_neeti_chapter_3_verse_3_10_001"]),
    ("is virtue more important than wealth according to Chanakya Niti", ["chanakya_neeti_chapter_3_verse_3_33_001"]),
    ("Chanakya Niti verse about purity, a loyal wife and a benevolent king", ["chanakya_neeti_chapter_3_verse_3_35_001"]),
    ("how listening to discourses helps one gain knowledge and righteousness", ["chanakya_neeti_chapter_2_verse_2_43_001"]),
    ("the story of the businessman and Mr Chheda who saved his life and business", ["7_secrets_of_leadership_segment_160_001"]),
    ("Judge AS Aguiar enquiry into police action against gangsters", ["7_secrets_of_leadership_segment_41_001"]),
    ("difference between external discipline imposed by teachers and internal discipline", ["7_secrets_of_leadership_segment_178_001"]),
    ("a businessman should plan ten years ahead a politician one generation ahead", ["7_secrets_of_leadership_segment_167_001"]),
    ("Manthan training center seating capacity and cost", ["7_secrets_of_leadership_segment_168_001"]),
    ("why giving a gift is a powerful way to influence someone per Arthashastra", ["corporate_chanakya_segment_45_001"]),
    ("learning from the younger generation about modern technology", ["corporate_chanakya_segment_41_001"]),
    ("what is meant by ITB in the box in sales pipeline", ["corporate_chanakya_segment_35_001"]),
    ("Ben Stein quote about getting what you want out of life", ["corporate_chanakya_segment_57_001"]),
    ("recruitment advertisement caption I found a purpose to live for", ["corporate_chanakya_segment_26_001"]),
    ("Chandragupta playing king among a group of boys as a child", ["chanakya_info_segment_8_001"]),
    ("Chanakya ordered Shakata-dasa's murder using a spy named Siddharthaka", ["chanakya_info_segment_17_001"]),
    ("Chanakya was born with canine teeth as a mark of royalty", ["chanakya_info_segment_3_001"]),
    ("Chanakya played by Tarun Khanna in a historical TV series", ["chanakya_info_segment_24_001"]),
    ("Chanakya's birthplace Chanaka village Golla vishaya district", ["chanakya_info_segment_7_001"]),
    ("king should avoid causes of impoverishment greed and disaffection among people", ["arthashastra_book_vii_chapter_v_005"]),
    ("rules for pricing conch shells diamonds pearls and corals", ["arthashastra_book_ii_chapter_xxii_002"]),
    ("who is the greatest tell me O Vipra riddle verse", ["chanakya_neeti_chapter_9_verse_9_7_001"]),
    ("Arthashastra chapter on treaty formation and impolicy dangers", ["arthashastra_book_ix_chapter_v_001"]),
    ("document your ideas and share them with others if skilled in war", ["7_secrets_of_leadership_segment_190_001"]),
    ("what does ill luck mean even with world class systems installed", ["7_secrets_of_leadership_segment_116_001"]),
    ("mentor said I do not understand anything in the Arthashastra even though trying my best", ["corporate_chanakya_segment_3_001"]),
]

# --- Crisis candidates: (query, [acceptable chunk ids]) ------------------------------
CRISIS_CANDIDATES: list[tuple[str, list[str]]] = [
    ("Nirav Modi Punjab National Bank fraud case summary", ["india_case_003_summary"]),
    ("Facebook Cambridge Analytica data misuse political manipulation scandal", ["europe_case_016_summary"]),
    ("Exxon Valdez oil spill Alaska environmental disaster", ["america_case_030_summary"]),
    ("Wells Fargo unauthorized fake accounts sales culture scandal", ["america_case_005_summary"]),
    ("Equifax data breach cybersecurity failure", ["america_case_004_summary"]),
    ("Yahoo data breach multi-year concealment nondisclosure", ["america_case_015_summary"]),
    ("Marriott Starwood data breach M&A due diligence failure", ["europe_case_015_summary"]),
    ("Volkswagen Dieselgate emissions regulatory fraud", ["europe_case_001_summary"]),
    ("Boeing product safety mass casualty design defect", ["america_case_006_summary"]),
    ("WeWork governance failure founder self dealing valuation collapse", ["america_case_024_summary"]),
    ("Wirecard accounting fraud corporate collapse", ["europe_case_003_summary"]),
    ("Parmalat accounting fraud Europe's Enron", ["europe_case_011_summary"]),
    ("Kingfisher Airlines Vijay Mallya loan default fugitive economic offence", ["india_case_005_summary"]),
    ("Uber workplace culture sexual harassment leadership crisis", ["america_case_025_summary"]),
    ("United Airlines viral customer mistreatment incident", ["america_case_003_summary"]),
    ("H&M racial insensitivity advertising social media backlash", ["europe_case_006_summary"]),
    ("DHFL NBFC collapse fund diversion financial fraud", ["india_case_009_summary"]),
    ("ABG Shipyard largest bank loan fraud in India", ["india_case_014_summary"]),
    ("Fortis Healthcare promoter fund diversion governance collapse", ["india_case_017_summary"]),
    ("National Stock Exchange India insider preferential access scandal", ["india_case_019_summary"]),
    ("Danske Bank Estonian branch money laundering scandal", ["europe_case_002_summary"]),
    ("Credit Suisse risk management financial scandal", ["europe_case_013_summary"]),
    ("Siemens systemic bribery corruption scandal", ["europe_case_005_summary"]),
    ("Takata airbag defect regulatory concealment mass recall", ["america_case_012_summary"]),
    ("Thomas Cook corporate collapse insolvency mass consumer impact", ["europe_case_008_summary"]),
]


def _verify(client, collection: str, query: str, expected_ids: list[str], top_k: int = 5) -> tuple[bool, list[str]]:
    vector = embed_query(query)
    results = client.query_points(collection_name=collection, query=vector, limit=top_k).points
    got_ids = [r.payload.get("id") for r in results]
    hit = any(eid in got_ids for eid in expected_ids)
    return hit, got_ids


def build_set(client, collection: str, candidates: list[tuple[str, list[str]]]) -> list[dict]:
    kept = []
    for query, expected_ids in candidates:
        hit, got_ids = _verify(client, collection, query, expected_ids)
        status = "KEEP" if hit else "DROP"
        print(f"[{status}] {query!r} -> expected in {expected_ids}, got top-5 {got_ids}")
        if hit:
            kept.append({"query": query, "expected_chunk_ids": expected_ids})
    return kept


def main() -> None:
    c = cget()
    x = xget()

    print("=== Chanakya ===")
    chanakya_set = build_set(c, "chanakya_kb", CHANAKYA_CANDIDATES)
    print(f"\nKept {len(chanakya_set)}/{len(CHANAKYA_CANDIDATES)}")

    print("\n=== Crisis ===")
    crisis_set = build_set(x, "crisis_kb", CRISIS_CANDIDATES)
    print(f"\nKept {len(crisis_set)}/{len(CRISIS_CANDIDATES)}")

    with open(OUT_DIR / "golden_queries_chanakya.jsonl", "w", encoding="utf-8") as f:
        for row in chanakya_set:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(OUT_DIR / "golden_queries_crisis.jsonl", "w", encoding="utf-8") as f:
        for row in crisis_set:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(chanakya_set)} chanakya + {len(crisis_set)} crisis golden queries.")


if __name__ == "__main__":
    main()
