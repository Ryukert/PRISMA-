"""
Pruebas del núcleo de SysReview PRISMA.
Ejecutar:   python -m unittest discover -s tests -v     (o simplemente: pytest)
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prisma_core as pc  # noqa: E402
import prisma_presets as pp  # noqa: E402


def make_df(rows):
    frames = []
    for src, items in rows.items():
        df = pd.DataFrame(items)
        for f in pc.FIELDS:
            if f not in df.columns:
                df[f] = "" if f != "year" else None
        df["source"] = src
        frames.append(df[pc.FIELDS + ["source"]])
    return pc.combine_sources(frames)


class TestTermMatching(unittest.TestCase):
    def match(self, term, text, plural=True):
        p = pc.compile_terms([term], plural)
        return p.search(pc.normalize_text(text)) is not None

    def test_whole_word(self):
        self.assertFalse(self.match("ai", "The main result was said"))
        self.assertTrue(self.match("ai", "AI-based tutoring"))
        self.assertFalse(self.match("imu", "A simulation study"))
        self.assertTrue(self.match("imu", "low-cost IMU sensor"))
        self.assertFalse(self.match("rms", "in terms of forms"))
        self.assertFalse(self.match("pv", "upvote"))

    def test_plural_and_y(self):
        self.assertTrue(self.match("bridge", "steel bridges"))
        self.assertTrue(self.match("technology", "emerging technologies"))
        self.assertFalse(self.match("bridge", "steel bridges", plural=False))

    def test_wildcards(self):
        self.assertTrue(self.match("monitor*", "monitoring systems"))
        self.assertTrue(self.match("organi?ation", "organisation"))

    def test_hyphen_and_accents(self):
        self.assertTrue(self.match("low cost sensor", "Low-cost sensors"))
        self.assertTrue(self.match("low-cost sensor", "low cost sensor network"))
        self.assertTrue(self.match("educacion", "Educación superior"))

    def test_parse_terms(self):
        self.assertEqual(pc.parse_terms('IoT, "Internet of Things"; iot\nWSN'), ["iot", "internet of things", "wsn"])


class TestNormalization(unittest.TestCase):
    def test_doi(self):
        self.assertEqual(pc.normalize_doi("https://doi.org/10.1016/J.ENGSTRUCT.2020.1"), "10.1016/j.engstruct.2020.1")
        self.assertEqual(pc.normalize_doi("doi: 10.1109/abc.123."), "10.1109/abc.123")
        self.assertEqual(pc.normalize_doi("nan"), "")
        self.assertEqual(pc.normalize_doi(""), "")

    def test_title_accents(self):
        self.assertEqual(pc.normalize_title("Análisis  de Vibración: ¡Puentes!"), "analisis de vibracion puentes")


class TestDedup(unittest.TestCase):
    def test_doi_prefix_and_empty_dois(self):
        df = make_df({
            "Scopus": [
                {"title": "Wireless monitoring of bridges with MEMS", "doi": "10.1016/abc", "year": 2020, "abstract": "x" * 80},
                {"title": "Completely different paper number one", "doi": "", "year": 2020},
                {"title": "Another unrelated paper number two", "doi": "", "year": 2021},
            ],
            "WoS": [
                {"title": "WIRELESS MONITORING OF BRIDGES WITH MEMS.", "doi": "https://doi.org/10.1016/ABC", "year": 2020},
            ],
        })
        d, st = pc.deduplicate(df)
        self.assertEqual(st["duplicates_total"], 1)
        self.assertEqual(st["duplicates_doi"], 1)
        # Los registros sin DOI no se fusionan entre sí
        self.assertEqual((d["Is_Duplicate"] == "Unique").sum(), 3)
        # Se conserva el más completo (el de Scopus con abstract)
        self.assertEqual(d.loc[d["Is_Duplicate"] == "Duplicate", "Duplicate_Of"].iloc[0], "R00001")

    def test_title_not_merged_when_dois_differ(self):
        df = make_df({"A": [
            {"title": "Structural health monitoring: an editorial", "doi": "10.1016/a"},
            {"title": "Structural health monitoring: an editorial", "doi": "10.1016/b"},
        ]})
        _, st = pc.deduplicate(df)
        self.assertEqual(st["duplicates_total"], 0)

    def test_fuzzy(self):
        df = make_df({"A": [
            {"title": "Vibration based damage detection in concrete bridges using accelerometers"},
            {"title": "Vibration-based damage detection in concrete bridge using accelerometers"},
            {"title": "Machine learning for student dropout prediction in universities"},
        ]})
        _, st = pc.deduplicate(df, fuzzy=True, threshold=92)
        self.assertEqual(st["duplicates_total"], 1)

    def test_fuzzy_respects_numbers_and_years(self):
        df = make_df({"A": [
            {"title": "Damage detection in steel bridges using wireless sensors: Part I", "year": 2020},
            {"title": "Damage detection in steel bridges using wireless sensors: Part II", "year": 2020},
            {"title": "Seismic response of tall concrete buildings under strong motion", "year": 2005},
            {"title": "Seismic response of tall concrete buildings under strong motions", "year": 2021},
        ]})
        _, st = pc.deduplicate(df, fuzzy=True, threshold=90)
        self.assertEqual(st["duplicates_total"], 0)


def screening_fixture():
    df = make_df({"Scopus": [
        {"title": "IoT structural health monitoring of bridges", "abstract": "MEMS accelerometer network",
         "keywords": "SHM; IoT", "year": 2020, "doc_type": "Article"},
        {"title": "Structural health monitoring with IoT", "abstract": "accelerometer", "year": 2010,
         "doc_type": "Article"},
        {"title": "SHM of civil structures with IoT devices", "abstract": "accelerometer bridges", "year": None,
         "doc_type": "Article"},
        {"title": "SHM IoT bridge accelerometer", "abstract": "", "year": 2021, "doc_type": "Article; Proceedings Paper"},
        {"title": "Patient monitoring with IoT", "abstract": "accelerometer", "keywords": "ECG", "year": 2021,
         "doc_type": "Article"},
        {"title": "Structural health monitoring IoT bridges", "abstract": "accelerometer; compared with smart city",
         "year": 2021, "doc_type": "Article"},
        {"title": "Structural health monitoring IoT", "abstract": "accelerometer only", "year": 2021,
         "doc_type": "Article"},
    ]})
    cfg = {
        "year_from": 2016, "year_to": 2026,
        "kw_required": "structural health monitoring, SHM",
        "kw_secondary": "IoT, internet of things",
        "kw_exclude": "patient monitoring, ECG, smart city",
        "doc_exclude": "proceedings paper, review",
        "search_blocks": {"B1": {"label": "x", "terms": "bridge"}, "B2": {"label": "y", "terms": "accelerometer"}},
        "min_blocks": 2, "exclude_mode": "balanced", "missing_year": "review",
    }
    d, _ = pc.deduplicate(df)
    return d, cfg


class TestScreening(unittest.TestCase):
    def test_pipeline_decisions(self):
        d, cfg = screening_fixture()
        out, steps = pc.run_screening(d, cfg)
        dec = out["Auto_Decision"].tolist()
        self.assertEqual(dec[0], pc.INCLUDE)
        self.assertEqual(out["Auto_Stage"].iloc[1], pc.STAGE_YEAR)
        self.assertEqual(dec[2], pc.REVIEW)                       # año faltante → revisión
        self.assertEqual(out["Auto_Stage"].iloc[3], pc.STAGE_DOCTYPE)  # tipo exacto por parte
        self.assertEqual(out["Auto_Stage"].iloc[4], pc.STAGE_REQ)      # no tiene SHM
        self.assertEqual(dec[5], pc.REVIEW)                       # exclusión solo en abstract
        self.assertEqual(out["Auto_Stage"].iloc[6], pc.STAGE_BLOCKS)
        self.assertIn("B1", out["Missing_Blocks"].iloc[6])

    def test_strict_mode(self):
        d, cfg = screening_fixture()
        cfg["exclude_mode"] = "strict"
        out, _ = pc.run_screening(d, cfg)
        self.assertEqual(out["Auto_Stage"].iloc[5], pc.STAGE_EXC)

    def test_near_miss(self):
        d, cfg = screening_fixture()
        cfg["review_near_miss"] = True
        out, _ = pc.run_screening(d, cfg)
        self.assertEqual(out["Auto_Decision"].iloc[6], pc.REVIEW)

    def test_empty_blocks_ignored(self):
        d, cfg = screening_fixture()
        cfg["search_blocks"] = {"B1": {"label": "vacío", "terms": ""}}
        out, _ = pc.run_screening(d, cfg)
        self.assertEqual(out["Auto_Decision"].iloc[6], pc.INCLUDE)

    def test_counts_are_consistent(self):
        d, cfg = screening_fixture()
        out, _ = pc.run_screening(d, cfg)
        rid = out.index[0]
        out.loc[out.index[2], "TA_Decision"] = pc.EXCLUDE
        out.loc[out.index[2], "TA_Reason"] = "Fuera del tema"
        out.loc[rid, "FT_Decision"] = pc.INCLUDE
        out.loc[out.index[4], "TA_Decision"] = pc.INCLUDE     # rescate de un auto-excluido
        out = pc.compute_status(out)
        c = pc.compute_counts(out)
        self.assertEqual(c["identified_total"],
                         c["duplicates_total"] + c["removed_automation"] + c["removed_other"]
                         + c["records_screened"] + c["not_screened"])
        self.assertEqual(c["records_screened"], c["excluded_screening"] + c["pending"] + c["reports_sought"])
        self.assertEqual(c["reports_sought"], c["not_retrieved"] + c["reports_assessed"])
        self.assertEqual(c["reports_assessed"], c["excluded_fulltext"] + c["included"])
        self.assertEqual(c["rescued"], 1)
        self.assertEqual(c["excluded_screening_reasons"], {"Fuera del tema": 1})

    def test_manual_decisions_survive_rescreen(self):
        d, cfg = screening_fixture()
        out, _ = pc.run_screening(d, cfg)
        out.loc[out.index[0], "TA_Decision"] = pc.EXCLUDE
        out2, _ = pc.run_screening(out, cfg)
        self.assertEqual(out2["TA_Decision"].iloc[0], pc.EXCLUDE)
        self.assertEqual(out2["Status"].iloc[0], pc.STATUS_EXC_TA)


class TestKappa(unittest.TestCase):
    def test_kappa(self):
        self.assertAlmostEqual(pc.cohen_kappa(["I", "E", "I", "E"], ["I", "E", "I", "E"]), 1.0)
        k = pc.cohen_kappa(["I", "I", "E", "E", "I"], ["I", "E", "E", "E", "I"])
        self.assertAlmostEqual(k, 0.6154, places=3)
        self.assertEqual(pc.parse_decision("Sí"), pc.INCLUDE)
        self.assertEqual(pc.parse_decision("Excluir"), pc.EXCLUDE)
        self.assertEqual(pc.parse_decision("dudoso"), pc.MAYBE)


class TestQueryParser(unittest.TestCase):
    def test_scopus(self):
        q = ('TITLE-ABS-KEY ( ( "structural health monitoring" OR shm ) AND ( bridge* OR building* ) '
             'AND ( iot OR "wireless sensor network" ) AND NOT ( medical OR patient ) ) '
             'AND PUBYEAR > 2015 AND PUBYEAR < 2027 AND ( LIMIT-TO ( DOCTYPE , "ar" ) )')
        r = pc.parse_search_query(q)
        self.assertEqual(len(r["search_blocks"]), 3)
        self.assertEqual(r["search_blocks"]["B1"]["terms"], "structural health monitoring, shm")
        self.assertIn("bridge*", r["search_blocks"]["B2"]["terms"])
        self.assertEqual(r["kw_exclude"], "medical, patient")
        self.assertEqual((r["year_from"], r["year_to"]), (2016, 2026))
        self.assertEqual(r["doc_include"], "article")      # LIMIT-TO(DOCTYPE,"ar") ahora se aplica

    USER_QUERIES = (
        '"TS=((MEMS OR "micro-electro-mechanical" OR microelectromechanical) AND (accelerometer* OR accelerograph*) '
        'AND ("low-noise" OR "low noise" OR "ultra-low noise" OR "high-resolution" OR ADXL35* OR ADXL1002 OR IIS3DWB '
        'OR SF1500 OR SF1600 OR "Silicon Designs") AND ("structural health monitoring" OR SHM OR "modal identification" '
        'OR "operational modal analysis" OR "ambient vibration" OR "natural frequenc*" OR "dynamic characteri*" OR '
        '"system identification" OR building* OR bridge* OR tower* OR "civil structure*" OR "civil infrastructure" OR '
        '"shake table" OR footbridge* OR heritage))\n'
        'Refine: Publication Years 2012–2026; Document Types: Article, Proceedings Paper; Languages: English, Spanish"'
        '"TITLE-ABS-KEY ( ( mems OR "micro-electro-mechanical" OR microelectromechanical ) AND ( accelerometer* OR '
        'accelerograph* ) AND ( "low-noise" OR "low noise" OR "ultra-low noise" OR "high-resolution" OR adxl35* OR '
        'adxl1002 OR iis3dwb OR sf1500 OR sf1600 OR "Silicon Designs" ) AND ( "structural health monitoring" OR shm OR '
        '"modal identification" OR "operational modal analysis" OR "ambient vibration" OR "natural frequenc*" OR '
        '"dynamic characteri*" OR "system identification" OR building* OR bridge* OR tower* OR "civil structure*" OR '
        '"civil infrastructure" OR "shake table" OR footbridge* OR heritage ) ) AND PUBYEAR > 2011 AND ( LIMIT-TO ( '
        'DOCTYPE , "ar" ) OR LIMIT-TO ( DOCTYPE , "cp" ) ) AND ( LIMIT-TO ( LANGUAGE , "English" ) OR LIMIT-TO ( '
        'LANGUAGE , "Spanish" ) )"'
    )

    def test_user_wos_and_scopus_together(self):
        r = pc.parse_search_query(self.USER_QUERIES)
        self.assertEqual(r["n_queries"], 2)
        self.assertEqual(len(r["search_blocks"]), 4)
        self.assertEqual(r["search_blocks"]["B1"]["terms"], "mems, micro electro mechanical, microelectromechanical")
        self.assertEqual(r["search_blocks"]["B2"]["terms"], "accelerometer*, accelerograph*")
        self.assertIn("adxl35*", r["search_blocks"]["B3"]["terms"])
        self.assertIn("silicon designs", r["search_blocks"]["B3"]["terms"])
        self.assertIn("natural frequenc*", r["search_blocks"]["B4"]["terms"])
        self.assertNotIn("refine", " ".join(b["terms"] for b in r["search_blocks"].values()))
        self.assertEqual((r["year_from"], r["year_to"]), (2012, 2026))
        self.assertEqual(r["doc_include"], "article, conference paper")
        self.assertEqual(r["languages"], "english, spanish")
        self.assertEqual(r["kw_exclude"], "")
        self.assertFalse(any("distinto" in w for w in r["warnings"]), r["warnings"])

    def test_user_queries_screen_records(self):
        r = pc.parse_search_query(self.USER_QUERIES)
        df = make_df({"WoS": [
            {"title": "Low-noise MEMS accelerometer for ambient vibration of a footbridge", "year": 2020,
             "doc_type": "Proceedings Paper", "language": "English"},
            {"title": "Low-noise MEMS accelerometer for ambient vibration of a footbridge (Chinese ed.)", "year": 2021,
             "doc_type": "Article", "language": "Chinese"},
            {"title": "High-resolution MEMS accelerometers in heritage towers", "year": 2019,
             "doc_type": "Review", "language": "Spanish"},
            {"title": "ADXL355 accelerometer network for natural frequencies of bridges", "year": 2010,
             "doc_type": "Article", "language": "English"},
            {"title": "MEMS accelerometers: noise floor study for buildings", "year": 2022,
             "doc_type": "Article", "language": ""},
        ]})
        cfg = {k: r[k] for k in ("search_blocks", "min_blocks", "kw_exclude", "year_from", "year_to",
                                 "doc_include", "doc_exclude", "languages")}
        out, steps = pc.run_screening(pc.deduplicate(df)[0], cfg)
        st = out["Auto_Stage"].tolist()
        self.assertEqual(out["Auto_Decision"].iloc[0], pc.INCLUDE)    # Proceedings Paper ≡ conference paper
        self.assertEqual(st[1], pc.STAGE_LANG)
        self.assertEqual(st[2], pc.STAGE_DOCTYPE)
        self.assertEqual(st[3], pc.STAGE_YEAR)
        self.assertEqual(st[4], pc.STAGE_BLOCKS)                       # sin término de bajo ruido; idioma vacío no excluye
        self.assertEqual(steps["language"], 1)

    def test_canon_lists(self):
        self.assertEqual(pc.canon_list("Article; Proceedings Paper", "doctype"), ["article", "conference paper"])
        self.assertEqual(pc.canon_list("eng; Español", "language"), ["english", "spanish"])
        self.assertEqual(pc.canon_list("Editorial Material", "doctype"), ["editorial"])

    def test_wos_inline_filters(self):
        r = pc.parse_search_query('TS=(mems AND accelerometer*) AND DT=(Article OR Proceedings Paper) AND LA=(English)')
        self.assertEqual(r["doc_include"], "article, conference paper")
        self.assertEqual(r["languages"], "english")
        self.assertEqual(len(r["search_blocks"]), 2)

    def test_wos(self):
        r = pc.parse_search_query('TS=("machine learning" OR "deep learning") AND TS=(education OR student*) AND PY=(2018-2025)')
        self.assertEqual(len(r["search_blocks"]), 2)
        self.assertEqual((r["year_from"], r["year_to"]), (2018, 2025))


class TestReadersAndExports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def write(self, name, text):
        p = os.path.join(self.tmp, name)
        Path(p).write_text(text, encoding="utf-8")
        return p

    def test_scopus_csv(self):
        p = self.write("scopus.csv",
                       "Authors,Title,Year,Source title,DOI,Abstract,Author Keywords,Index Keywords,Document Type,EID\n"
                       'A B.,"Bridge SHM, a study",2020,Eng Struct,10.1/x,"An abstract",SHM; IoT,MEMS,Article,2-s2\n')
        df, info = pc.read_source(p)
        self.assertEqual(info["name"], "Scopus")
        self.assertEqual(df["title"].iloc[0], "Bridge SHM, a study")
        self.assertEqual(df["keywords"].iloc[0], "SHM; IoT; MEMS")
        self.assertEqual(int(df["year"].iloc[0]), 2020)

    def test_ris_and_bib(self):
        ris = self.write("x.ris", "TY  - JOUR\nTI  - A RIS title here\nAU  - Doe, J\nPY  - 2019\nDO  - 10.2/r\nKW  - iot\nER  - \n")
        df, info = pc.read_source(ris)
        self.assertEqual(info["format"], "ris")
        self.assertEqual(df["doc_type"].iloc[0], "Article")
        bib = self.write("x.bib", '@article{k1, title={A {BibTeX} title}, author={Doe, J. and Roe, R.}, year=2018, doi="10.3/b"}\n')
        df, info = pc.read_source(bib)
        self.assertEqual(df["title"].iloc[0], "A BibTeX title")
        self.assertEqual(df["authors"].iloc[0], "Doe, J.; Roe, R.")

    def test_medline_and_wos_tagged(self):
        nb = self.write("p.nbib", "PMID- 1\nTI  - Medline title\n      continued\nAB  - abs\nDP  - 2021 Jan\n"
                                  "AID - 10.5/m [doi]\nPT  - Journal Article\nFAU - Doe, John\n\n")
        df, info = pc.read_source(nb)
        self.assertEqual(info["name"], "PubMed")
        self.assertEqual(df["title"].iloc[0], "Medline title continued")
        self.assertEqual(df["doi"].iloc[0], "10.5/m")
        wos = self.write("savedrecs.txt", "FN Clarivate\nVR 1.0\nPT J\nAU Doe, J\n   Roe, R\nTI Tagged WoS\n   title\n"
                                          "PY 2020\nDI 10.6/w\nDT Article\nER\nEF\n")
        df, info = pc.read_source(wos)
        self.assertEqual(info["format"], "wos_tagged")
        self.assertEqual(df["title"].iloc[0], "Tagged WoS title")
        self.assertEqual(df["authors"].iloc[0], "Doe, J; Roe, R")

    def test_endnote_semicolon_and_mislabeled(self):
        enw = self.write("x.enw", "%0 Journal Article\n%T EndNote title\n%A Doe, J.\n%A Roe, R.\n%D 2020\n"
                                  "%R 10.1016/e.1\n%K mems\n%G English\n\n%0 Conference Proceedings\n%T Second\n%D 2021\n")
        df, info = pc.read_source(enw)
        self.assertEqual((info["format"], len(df)), ("endnote", 2))
        self.assertEqual(df["authors"].iloc[0], "Doe, J.; Roe, R.")
        self.assertEqual(df["language"].iloc[0], "English")
        semi = self.write("excel_es.csv", "Title;Year;DOI;Language\nTítulo con, coma;2019;10.1016/s.1;Spanish\n")
        df, info = pc.read_source(semi)
        self.assertEqual(info["format"], "csv_semicolon")
        self.assertEqual(df["title"].iloc[0], "Título con, coma")
        tsv_as_xls = self.write("savedrecs.xls", "PT\tAU\tTI\tPY\tDI\tLA\nJ\tDoe\tTab title\t2020\t10.1016/t.1\tEnglish\n")
        df, info = pc.read_source(tsv_as_xls)
        self.assertEqual((info["format"], df["title"].iloc[0], info["name"]), ("tsv", "Tab title", "WoS"))
        ciw = self.write("export.ciw", "FN Clarivate\nVR 1.0\nPT J\nTI CIW title\nPY 2022\nLA English\nER\n")
        df, info = pc.read_source(ciw)
        self.assertEqual((info["format"], df["language"].iloc[0]), ("wos_tagged", "English"))
        html = self.write("fake.xls", "<html><body><table><tr><td>x</td></tr></table></body></html>")
        with self.assertRaises(ValueError):
            pc.read_source(html)
        xlsx_as_xls = os.path.join(self.tmp, "real_xlsx.xls")
        pd.DataFrame({"Title": ["Zip title"], "Year": [2018]}).to_excel(xlsx_as_xls, index=False, engine="openpyxl")
        df, info = pc.read_source(xlsx_as_xls)
        self.assertEqual((info["format"], df["title"].iloc[0]), ("excel", "Zip title"))
        nocols = self.write("raro.csv", "a,b\n1,2\n")
        with self.assertRaises(ValueError):
            pc.read_source(nocols)

    def test_exports_and_session(self):
        d, cfg = screening_fixture()
        out, _ = pc.run_screening(d, cfg)
        out.loc[out.index[0], "abstract"] = "bad\x07char"
        counts = pc.compute_counts(out)
        prov = pc.build_provenance([{"name": "Scopus", "file": "s.csv", "n": 7, "sha256": "abc", "format": "csv"}])
        xlsx = os.path.join(self.tmp, "o.xlsx")
        pc.export_workbook(xlsx, out, counts, cfg, prov)
        self.assertTrue(os.path.exists(xlsx))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "o_config.json")))
        sheets = pd.read_excel(xlsx, sheet_name=None)
        self.assertIn("Incluidos", sheets)
        self.assertEqual(len(sheets["Todos"]), len(out))
        ris = os.path.join(self.tmp, "o.ris")
        pc.export_ris(ris, out[out["Status"] == pc.STATUS_INCLUDED])
        back, _ = pc.read_source(ris)
        self.assertEqual(len(back), counts["included"])
        lay = pc.prisma_layout(counts, "Prueba")
        self.assertIn("<svg", pc.layout_to_svg(lay))
        png = os.path.join(self.tmp, "d.png")
        pc.layout_to_png(lay, png)
        self.assertTrue(os.path.getsize(png) > 1000)
        sess = os.path.join(self.tmp, "s.prisma")
        out.loc[out.index[1], "TA_Note"] = "nota"
        pc.save_session(sess, out, cfg, "Prueba", [])
        loaded = pc.load_session(sess)
        self.assertEqual(loaded["df"]["TA_Note"].iloc[1], "nota")
        self.assertEqual(loaded["df"]["Status"].tolist(), out["Status"].tolist())
        self.assertIn("INFORME PRISMA", pc.build_text_report(counts, "Prueba", cfg, prov))

    def test_reviewer_roundtrip(self):
        d, cfg = screening_fixture()
        out, _ = pc.run_screening(d, cfg)
        sheet = pc.reviewer_sheet(out)
        sheet["Decision_R2"] = "Incluir"
        p = os.path.join(self.tmp, "r2.xlsx")
        sheet.to_excel(p, index=False)
        imp, invalid = pc.import_reviewer_sheet(p)
        self.assertEqual(invalid, 0)
        self.assertEqual(len(imp), len(sheet))


class TestPresets(unittest.TestCase):
    def test_defaults_valid(self):
        for cfg in pp.DEFAULT_PRESETS.values():
            pp.validate_preset_cfg(cfg)
        pp.validate_preset_cfg(pp.PRESET_TEMPLATE)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            pp.validate_preset_cfg({"year_from": "2015", "exclude_mode": "x", "min_blocks": 9,
                                    "search_blocks": {"B1": {"terms": "a"}}})


if __name__ == "__main__":
    unittest.main()
