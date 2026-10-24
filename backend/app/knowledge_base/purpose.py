"""The instrument's purpose as a generated `muss` criterion.

Every other criterion asks about one condition; none asks whether the project is what the
instrument funds at all. Without it, an instrument for wood heating whose specific criteria do
not apply to a heat pump would come out as "passt gut". The text is the instrument's own
description from the knowledge base (program purpose if there is none), never invented.
"""

from app.models.program import Criterion, Instrument, Program

PURPOSE_ID = "foerdergegenstand"

_NOTE = (
    "Prüft nur die Art des Vorhabens: Ist es das, was dieses Angebot fördert (z. B. Forschung "
    "und Entwicklung, eine Holzfeuerung, eine Bürgschaft für einen Bankkredit)? Zeitpunkt, "
    "Abrechnungsbasis, Ort, Grösse, Kosten und Finanzierung prüfen die anderen Kriterien; sie "
    "entscheiden dieses Kriterium nicht. Beschreibt das Vorhaben klar etwas anderes (z. B. eine "
    "Wärmepumpe, wo Holzfeuerungen gefördert werden), ist es nicht erfüllt, mit dem Zitat aus "
    "dem Text."
)


def purpose_criterion(program: Program, instrument: Instrument) -> Criterion:
    description = instrument.description or program.purpose
    return Criterion(
        id=PURPOSE_ID,
        text=f"Das Vorhaben ist von der Art, die das Angebot fördert: {description}",
        kind="muss",
        about="vorhaben",
        profile_fields=["vorhaben_beschreibung", "art_des_vorhabens"],
        source=instrument.source,
        notes=_NOTE,
    )
