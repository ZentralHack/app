from app.agent.normalize import is_too_vague, normalize_profile
from tests.factories import field, make_profile, sensora_profile, treuhand_profile, vague_profile


def test_valid_profile_is_unchanged():
    profile = sensora_profile()
    assert normalize_profile(profile) == profile


def test_unknown_values_are_dropped_and_noted():
    profile = make_profile(art_des_vorhabens=["prototyp", "raumfahrt", "prototyp"])
    result = normalize_profile(profile).fields["art_des_vorhabens"]
    assert result.value == ["prototyp"]
    assert result.status == "angegeben"
    assert result.note == "Nicht erkannte Werte verworfen: raumfahrt."


def test_nothing_left_becomes_fehlt():
    profile = make_profile(branche=field(["firmenanlass"], "annahme"))
    result = normalize_profile(profile).fields["branche"]
    assert result.value is None
    assert result.status == "fehlt"
    assert "firmenanlass" in result.note


def test_scalar_value_is_wrapped():
    result = normalize_profile(make_profile(applicant_type="kmu")).fields["applicant_type"]
    assert result.value == ["kmu"]


def test_empty_partner_list_means_no_partner():
    result = normalize_profile(make_profile(partner=[])).fields["partner"]
    assert result.value == []
    assert result.status == "angegeben"


def test_empty_project_type_list_becomes_fehlt():
    result = normalize_profile(make_profile(art_des_vorhabens=[])).fields["art_des_vorhabens"]
    assert result.status == "fehlt"
    assert result.note == "Kein Wert erkannt."


def test_fehlt_and_other_fields_are_left_alone():
    profile = make_profile(partner=None, laufzeit=18)
    assert normalize_profile(profile) == profile


def test_too_vague():
    assert is_too_vague(vague_profile())
    assert not is_too_vague(sensora_profile())
    # A description alone is enough to run, even if no project type fits.
    assert not is_too_vague(make_profile(vorhaben_beschreibung="Firmenfest"))
    assert not is_too_vague(treuhand_profile())
