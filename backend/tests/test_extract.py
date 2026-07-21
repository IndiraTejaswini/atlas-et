"""Entity extraction regex sanity checks."""
from app.extract import extract_entities


def test_extracts_equipment_tags():
    ents = extract_entities("Pump P-101A tripped; exchanger E-104 fouling observed.")
    assert "P-101A" in ents["equipment"]
    assert "E-104" in ents["equipment"]


def test_extracts_oisd_standard():
    ents = extract_entities("Tested per OISD-STD-132 requirements.")
    assert "OISD-STD-132" in ents["standard"]


def test_extracts_factories_act_section():
    ents = extract_entities("Governed by Factories Act Section 31.")
    assert "Factories Act Sec 31" in ents["standard"]


def test_extracts_failure_mode_seal():
    ents = extract_entities("Mechanical seal failure observed on the pump.")
    assert "Mechanical seal failure" in ents["failure_mode"]


def test_extracts_docref():
    ents = extract_entities("See work order WO-2415 for details.")
    assert "WO-2415" in ents["docref"]


def test_equipment_survives_ocr_run_together_artifact():
    # OCR frequently drops the space between a tag and the following word —
    # the trailing lookahead (not \b) in EQUIPMENT_RE exists for this case.
    ents = extract_entities("P-101ACrude Charge Pump inspected.")
    assert "P-101A" in ents["equipment"]


def test_no_false_positive_on_plain_number():
    ents = extract_entities("The reading was 42 barg at the gauge.")
    assert not ents["equipment"]


# --- Entity resolution: case-insensitivity + canonicalisation -----------

def test_equipment_tag_matches_regardless_of_case():
    ents = extract_entities("pump p-101a tripped on low flow.")
    assert "P-101A" in ents["equipment"]
    assert "p-101a" not in ents["equipment"]  # canonicalised, not a separate key


def test_equipment_tag_reformatted_case_collapses_to_one_node():
    # The actual "no entity resolution" gap this closes: the same tag
    # written two different ways in the same document must produce ONE
    # counter entry, not two disconnected ones.
    ents = extract_entities("P-101A tripped. Later, p-101a was restarted.")
    assert ents["equipment"]["P-101A"] == 2
    assert len(ents["equipment"]) == 1


def test_docref_matches_regardless_of_case():
    ents = extract_entities("see work order wo-2415 for the full history.")
    assert "WO-2415" in ents["docref"]


def test_standard_pattern_matches_regardless_of_case():
    ents = extract_entities("tested per oisd-std-132 requirements.")
    assert "OISD-STD-132" in ents["standard"]


def test_known_doc_ids_recognises_ids_the_generic_pattern_misses():
    # "OEM-SLZ-OHH" has no prefix DOCREF_RE recognises (OEM isn't in its
    # list) and isn't in SPECIAL_DOC_IDS either — this is a fictional id
    # standing in for "some other corpus's document naming scheme" to prove
    # the mechanism generalises, not just the six hardcoded examples.
    ents = extract_entities("Refer to PLANT2-MANUAL-07 for details.", known_doc_ids={"PLANT2-MANUAL-07"})
    assert "PLANT2-MANUAL-07" in ents["docref"]


def test_known_doc_ids_matching_is_case_insensitive():
    ents = extract_entities("refer to plant2-manual-07 for details.", known_doc_ids={"PLANT2-MANUAL-07"})
    assert "PLANT2-MANUAL-07" in ents["docref"]


def test_known_doc_ids_none_falls_back_to_special_doc_ids_only():
    # Zero-context callers (e.g. graph.py's cause-clause parser) must still
    # get the small built-in floor without needing to pass anything.
    ents = extract_entities("See OEM-SLZ-OHH Section 6 for flush requirements.")
    assert "OEM-SLZ-OHH" in ents["docref"]


# --- Person extraction: pattern-based, not a fixed name list ------------

def test_extracts_a_person_not_in_the_old_fixed_list():
    ents = extract_entities("Reviewed by J. Patel on site.")
    assert "J. Patel" in ents["person"]


def test_person_pattern_does_not_false_positive_on_degree_celsius():
    # Regression test: "design 28 barg @ 240 °C. Insulated, hot service."
    # from the real corpus (pid-unit300.md) previously extracted a fake
    # person "C. Insulated" — a temperature unit ending a sentence,
    # followed by a new capitalised sentence, looked identical to an
    # initial + surname without the (?<![°\d]) guard.
    ents = extract_entities("design 28 barg @ 240 °C. Insulated, hot service.")
    assert "C. Insulated" not in ents["person"]


def test_person_pattern_does_not_false_positive_on_digit_before_letter():
    ents = extract_entities("Set pressure 6.0 barg. Registered under Factories Act.")
    assert not any(p.startswith("0. ") or p == "C. Registered" for p in ents["person"])
