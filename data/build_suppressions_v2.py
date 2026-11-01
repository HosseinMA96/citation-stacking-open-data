"""Build data/suppressions_v2.csv: Clarivate JCR title suppressions for JCR data years 2015-2023, from primary
Clarivate material (archived) wherever possible. suppressions.csv (v1, 2026-10-28) is kept unchanged.

Sources (all in data/suppression_sources/, provenance in wayback/SOURCES.txt):
  2015-2017  Clarivate "Suppressed Titles 2007-2017" spreadsheet (archived xlsx): journal, year, type; no %s, no partners
  2018       Clarivate JCR help "Title Suppressions" page, archived 2019-09-04 (2019 release): tables parsed
  2019       Clarivate "Title Suppressions" page as PDF, hosted by Retraction Watch (2020 release): transcribed below
  2020       Clarivate list (c) 2021 v3.1, copy hosted by CGMH library (2021 release): rows of suppressions.csv v1
  2021-2023  Clarivate JCR help "Title Suppressions" page, archived 2022-09-03 / 2023-09-30 / 2024-09-19: tables parsed
Stacking tables in the 2023 and 2024 releases give JCR abbreviations; full titles come from the page's own title
table, or (donors not in it, marked * by Clarivate) are written out by hand and flagged in `note`.

Usage:  python data/build_suppressions_v2.py      (writes data/suppressions_v2.csv; refuses to overwrite)
"""
import csv
import re
import sys
import zipfile
import html as H
from html.parser import HTMLParser
from pathlib import Path

D = Path(__file__).resolve().parent
S = D / "suppression_sources"
W = S / "wayback"
OUT = D / "suppressions_v2.csv"
COLS = ["jcr_data_year", "release_year", "journal", "jcr_abbrev", "type", "role", "partner_journal",
        "pct_jif_numerator", "pct_exchange_to_jif_years", "pct_self_cites_jif_numerator", "source_file", "note"]
URL = {  # archived source URLs (also in wayback/SOURCES.txt)
    "xlsx": "https://web.archive.org/web/2019/https://help.incites.clarivate.com/incitesLiveJCR/8687-TRS/version/6/part/8/data/Suppressed%20titles%202017-2007%20IMS.xlsx",
}


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.row = None; self.cell = None; self.depth = 0

    def handle_starttag(self, t, a):
        if t == "table": self.depth += 1; self.tables.append([])
        if t == "tr" and self.depth: self.row = []
        if t in ("td", "th") and self.row is not None: self.cell = []

    def handle_endtag(self, t):
        if t in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", " ".join(self.cell)).strip()); self.cell = None
        if t == "tr" and self.row is not None: self.tables[-1].append(self.row); self.row = None
        if t == "table": self.depth -= 1

    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)


def pct(s):
    return int(s.strip().rstrip("%")) if s and s.strip().rstrip("%").isdigit() else ""


def from_help_page(fname, year, extra_full=None):
    p = Tables(); p.feed((W / fname).read_text(encoding="utf-8", errors="ignore"))
    rows, full = [], {}
    titles = next(t for t in p.tables if t and t[0][:2] == ["JCR Title", "Full Title"])
    for r in titles[1:]:
        full[r[0]] = r[1]
    full.update(extra_full or {})
    selfp = {}
    for t in p.tables:
        if t and t[0][0] == "Full Title" and "Self" in t[0][2]:
            for r in t[1:]:
                selfp[r[0]] = pct(r[2])
    pairs = next((t for t in p.tables if t and t[0][:2] == ["Recipient Journal", "Donor Journal"]), [])
    named = set()
    titles_full = sorted(full.values(), key=len, reverse=True)
    types = {r[1]: r[2].lower() for r in titles[1:]}
    for r in pairs[1:]:
        rec = full.get(r[0], r[0])
        abbr = r[0] if r[0] in full else ""
        if r[1] in full:
            donors = [full[r[1]]]
        else:   # one cell may list several donors by full title (2019 release, Bone Research)
            rest, donors = r[1], []
            for t in titles_full:
                if t in rest:
                    donors.append(t); rest = rest.replace(t, " ")
            if rest.strip() or not donors:
                donors = [r[1]]
        note = ""
        if r[1].endswith("*") or (r[1] not in full and r[1] not in titles_full and len(donors) == 1):
            note = "donor full title written from JCR abbreviation (Clarivate marks * = donor not in suppression list)"
        typ = "stacking"
        if types.get(rec, "") == "expression of concern":
            typ, note = "stacking (expression of concern)", "listed in the stacking table but given an Expression of Concern, not suppressed"
        for d in donors:
            rows.append([year, year + 1, rec, abbr, typ, "recipient", d, pct(r[2]), pct(r[3]), "", fname, note])
            named |= {rec, d}
    for abbr, ft in full.items():
        if abbr not in [r[0] for r in titles[1:]]:
            continue
        typ = [r[2] for r in titles[1:] if r[0] == abbr][0].lower()
        if typ == "self":
            rows.append([year, year + 1, ft, abbr, "self", "", "", "", "", selfp.get(ft, ""), fname, ""])
        elif typ == "stacking":
            role = "recipient" if any(x[2] == ft and x[5] == "recipient" for x in rows) else "donor"
            if role == "donor":
                partners = "; ".join(sorted({x[2] for x in rows if x[6] == ft and x[5] == "recipient"}))
                rows.append([year, year + 1, ft, abbr, "stacking", "donor", partners, "", "", "", fname, ""])
        elif typ != "expression of concern":   # EoC titles appear as stacking (expression of concern) rows above
            rows.append([year, year + 1, ft, abbr, typ, "", "", "", "", "", fname, "not a stacking or self suppression"])
    # Suppression warnings (2022 release: journal self-stacking), listed after the tables
    for t in p.tables:
        if t and len(t[0]) == 1 and t[0][0].isupper() and len(t) > 1 and all(len(r) == 1 for r in t):
            for r in t:
                rows.append([year, year + 1, r[0].title(), "", "warning_self_stacking", "", "", "", "", "", fname,
                             "suppression warning, not a suppression; excluded from tests"])
    return rows


def main():
    if OUT.exists():
        sys.exit(f"{OUT} exists; never overwrite (write v3)")
    rows = []
    # 2015-2017 from the xlsx
    z = zipfile.ZipFile(W / "suppressed_2007_2017.xlsx")
    ss = [H.unescape(re.sub(r"<[^>]+>", "", m)) for m in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), flags=re.S)]
    for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode(), flags=re.S):
        d = {}
        for c in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', r, flags=re.S):
            v = re.search(r"<v>(.*?)</v>", c.group(3)); v = v.group(1) if v else ""
            d[c.group(1)] = (ss[int(v)] if 't="s"' in c.group(2) else v).strip()
        if d.get("D", "").isdigit() and 2015 <= int(d["D"]) <= 2017:
            typ = d.get("E", "").lower()
            rows.append([int(d["D"]), int(d["D"]) + 1, d["C"], d["B"], typ, "", "", "", "", "", "wayback/suppressed_2007_2017.xlsx",
                         "spreadsheet gives journal, year and type only (no partners, no %)"])
    # 2018 (2019 release)
    rows += from_help_page("incites_20190904.html", 2018)
    # 2019 (2020 release): transcribed from rw_2020release_title_suppress.pdf pp. 2-4 (self table; all 33 are Self)
    self_2019 = [("Acta Cardiologica Sinica", 60), ("Adicciones", 33), ("Aerosol and Air Quality Research", 39),
                 ("Aging Male", 32), ("American Journal of Pharmaceutical Education", 34), ("Body Image", 50),
                 ("Business Ethics", 52), ("Cellulose Chemistry and Technology", 40),
                 ("CNS & Neurological Disorders-Drug Targets", 34), ("Cognitive Computation", 28),
                 ("Cognitive Neurodynamics", 35), ("Cognitive Neuropsychology", 28), ("Current Genetics", 41),
                 ("Environmental Engineering and Management Journal", 61), ("Fish & Shellfish Immunology", 42),
                 ("Food and Agricultural Immunology", 38), ("Forensic Science International-Genetics", 45),
                 ("GeroScience", 39), ("IEEE Transactions on Applied Superconductivity", 48), ("Industria Textila", 58),
                 ("International Journal of Medicinal Mushrooms", 53),
                 ("International Journal of Systematic and Evolutionary Microbiology", 41),
                 ("Journal of Biomolecular Structure & Dynamics", 40),
                 ("Journal of Environmental and Engineering Geophysics", 71),
                 ("Journal of the Experimental Analysis of Behavior", 36), ("Journal of Human Evolution", 26),
                 ("Journal of Medical Biochemistry", 56), ("Marine Biotechnology", 26), ("Microbes and Environments", 26),
                 ("Pakistan Journal of Zoology", 51), ("Rejuvenation Research", 31), ("Xenotransplantation", 37),
                 ("Zootaxa", 43)]
    for j, p in self_2019:
        rows.append([2019, 2020, j, "", "self", "", "", "", "", p, "suppression_sources/rw_2020release_title_suppress.pdf", ""])
    # 2020 (2021 release): v1 rows (transcribed 2026-10-28 from cgmh_2020JCR_suppressed.pdf, re-checked 2026-10-31)
    with open(D / "suppressions.csv") as f:
        for r in csv.DictReader(f):
            if r["jcr_data_year"] == "2020":
                role = "donor" if r["role"].startswith("suppressed") else r["role"]
                rows.append([2020, 2021, r["journal"], "", r["type"], role, r["partner_journal"], r["pct_jif_numerator"],
                             r["pct_exchange_to_jif_years"], r["pct_self_cites_jif_numerator"],
                             "suppression_sources/cgmh_2020JCR_suppressed.pdf", ""])
    # 2021-2023 (2022-2024 releases)
    rows += from_help_page("jcrhelp_20220903.html", 2021)
    rows += from_help_page("jcrhelp_20230930.html", 2022,
                           {"CARDIOMETRY*": "Cardiometry", "INT J EARLY CHILD SP*": "International Journal of Early Childhood Special Education"})
    rows += from_help_page("jcrhelp_20240919.html", 2023, {"OPTIK": "Optik"})
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f); w.writerow(COLS); w.writerows(rows)
    import collections
    print(sorted(collections.Counter((r[0], r[4], r[5]) for r in rows).items()))
    print(len(rows), "rows ->", OUT)


if __name__ == "__main__":
    main()
