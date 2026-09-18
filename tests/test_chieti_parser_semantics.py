from white_list_archive.parsers.chieti_legacy_doc import _applicant_status, _listed_status, _source_date, _source_identifiers


def test_chieti_dates_are_conservative():
    assert _source_date("13 ottobre 2026") == "2026-10-13"
    assert _source_date("27/05/2015") == "2015-05-27"
    assert _source_date("1° LUGLIO 2019") == "2019-07-01"
    assert _source_date("23 maggio 20256") == ""
    assert _source_date("8 febbario 2022") == ""


def test_chieti_identifier_extraction_preserves_only_strict_shapes():
    assert _source_identifiers("c.f.DLRRRT65S18D763Z p.IVA 01994310694") == ["01994310694", "DLRRRT65S18D763Z"]
    assert _source_identifiers("p.IVA 003253330695") == []


def test_chieti_statuses_require_positive_source_text():
    assert _listed_status("") == "listed"
    assert _listed_status("Richiesta di rinnovo in data 09/07/2026") == "renewal_update_in_progress"
    assert _listed_status("ISCRIZIONE SCADUTA") == "expired_observed"
    assert _listed_status("richiesta cancellazione per trasferimento sede legale") == "cancellation_related"
    assert _applicant_status("IN ISTRUTTORIA") == "pending"
    assert _applicant_status("") == "pending"
    assert _applicant_status("Istanza archiviata con D.P. 1") == "other_or_unknown"
    assert _applicant_status("Istruttoria trasferita per competenza alla Prefettura di Pescara") == "other_or_unknown"
    assert _applicant_status("Istanza respinta a seguito di informativa interdittiva") == "rejected_or_denied"
