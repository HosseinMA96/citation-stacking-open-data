"""Build the out-of-sample label file and a cross-check of suppressions_v2.csv (review round 1, R11/R13).

Sources (data/suppression_sources/clarivate_2026/, provenance and sha256 in SOURCES.txt; retrieved 2026-10-31):
  title_suppressions_article_28351398819089.json   Clarivate JCR help article, "Journals Suppressed from 2025 JCR Data
                                                   (2026 release)": title table, self-citation table, stacking table
  suppressed_titles_2024-2007.xlsx                 Clarivate "Suppressed titles 2024-2007" (sheet "by year": JCR title,
                                                   full title, year, type), linked from the same article
Outputs (refuse to overwrite):
  data/suppressions_oos.csv          JCR data years 2024 (xlsx) and 2025 (article), columns as suppressions_v2.csv
  data/suppressions_crosscheck.csv   2015-2023: every (data year, normalized title) in v2 or the xlsx, with its type
                                     in each and a status (both / only_v2 / only_xlsx / type_differs)
Run with base Anaconda Python (openpyxl):  ~/anaconda3/bin/python -I data/build_suppressions_oos.py  (-I: skip ~/.local pandas)
"""
import html as H
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parent
S = D / "suppression_sources" / "clarivate_2026"
OUT, XC = D / "suppressions_oos.csv", D / "suppressions_crosscheck.csv"
COLS = ["jcr_data_year", "release_year", "journal", "jcr_abbrev", "type", "role", "partner_journal",
        "pct_jif_numerator", "pct_exchange_to_jif_years", "pct_self_cites_jif_numerator", "source_file", "note"]
TYPE = {"Self": "self", "Self Citation": "self", "Stacking": "stacking"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())
    return s


def tables(body):
    out = []
    for t in re.findall(r"<table.*?</table>", body, flags=re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", t, flags=re.S):
            cells = [H.unescape(re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            rows.append([re.sub(r"\s+", " ", c).strip() for c in cells])
        out.append(rows)
    return out


def pct(s):
    s = s.strip().rstrip("%")
    return int(s) if s.isdigit() else ""


def main():
    if OUT.exists() or XC.exists():
        sys.exit("output exists; never overwrite")
    x = pd.read_excel(S / "suppressed_titles_2024-2007.xlsx", sheet_name="by year", header=None)
    x = x[pd.to_numeric(x[2], errors="coerce").notna()].copy()
    x.columns = ["abbr", "full", "year", "type"]
    x["year"] = x.year.astype(int)
    rows = [[2024, 2025, r.full, r.abbr, TYPE[r.type], "recipient" if r.type == "Stacking" else "", "", "", "", "",
             "suppression_sources/clarivate_2026/suppressed_titles_2024-2007.xlsx", "xlsx gives title, year and type only"]
            for r in x[x.year == 2024].itertuples()]

    art = json.loads((S / "title_suppressions_article_28351398819089.json").read_text())["article"]
    tt = tables(art["body"])
    titles = next(t for t in tt if t and t[0][:3] == ["JCR Title", "Full Title", "Type"])
    selft = next(t for t in tt if t and t[0][0] == "Full Title" and "Self" in t[0][2])
    stack = next(t for t in tt if t and t[0][:2] == ["Recipient Journal", "Donor Journal"])
    full = {a: f for a, f, _ in titles[1:]}
    selfp = {f: pct(p) for f, _, p, _ in selft[1:]}
    src = "suppression_sources/clarivate_2026/title_suppressions_article_28351398819089.json"
    partners = {}
    for rec, don, pn, pe in stack[1:]:
        partners[rec] = (don, pct(pn), pct(pe))
    for a, f, ty in titles[1:]:
        t = TYPE[ty]
        if t == "self":
            rows.append([2025, 2026, f, a, "self", "", "", "", "", selfp.get(f, ""), src, ""])
        else:
            don, pn, pe = partners[a]
            rows.append([2025, 2026, f, a, "stacking", "recipient", don, pn, pe, "", src,
                         "partner given as JCR abbreviation only"])
    for a, (don, pn, pe) in partners.items():
        rows.append([2025, 2026, "", don, "stacking", "donor", full.get(a, a), pn, pe, "", src,
                     "donor; JCR abbreviation only (full title not in the source)"])
    oos = pd.DataFrame(rows, columns=COLS)
    oos.to_csv(OUT, index=False)

    v2 = pd.read_csv(D / "suppressions_v2.csv")
    v2 = v2[v2.type.isin(["self", "stacking"]) & (v2.role.fillna("recipient") != "donor")]
    a = v2.assign(key=v2.journal.map(norm))[["jcr_data_year", "key", "journal", "type"]].drop_duplicates(["jcr_data_year", "key"])
    b = x[(x.year >= 2015) & (x.year <= 2023)].assign(key=lambda d: d.full.map(norm), type=lambda d: d.type.map(TYPE))
    b = b.rename(columns={"year": "jcr_data_year", "full": "xlsx_title", "type": "xlsx_type"})[["jcr_data_year", "key", "xlsx_title", "xlsx_type"]]
    m = a.merge(b, on=["jcr_data_year", "key"], how="outer")
    m["status"] = m.apply(lambda r: "only_xlsx" if pd.isna(r.journal) else "only_v2" if pd.isna(r.xlsx_title)
                          else "type_differs" if r.type != r.xlsx_type else "both", axis=1)
    m.sort_values(["jcr_data_year", "status", "key"]).to_csv(XC, index=False)
    print(oos.groupby(["jcr_data_year", "type", "role"], dropna=False).size().to_string())
    print(m.groupby(["jcr_data_year", "status"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
