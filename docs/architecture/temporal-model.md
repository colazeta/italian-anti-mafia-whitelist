# Temporal model

The canonical history deliberately distinguishes three temporal dimensions.

## Effective time

`effective_period` answers: **when is/was the represented fact valid in the administrative world?**

It may be unknown. It must not be inferred mechanically from a nominal expiry date.

## Observation time

`observation_period` answers: **during which interval do the acquired public sources support this canonical representation?**

A fact that disappears from a later snapshot may close its observation period without creating an administrative removal.

## System time

`system_period` answers: **during which interval was this row the archive's canonical representation?**

A later correction closes the earlier system period and inserts a new row. The old row remains queryable.

All ranges follow `[start, end)` semantics. A currently open interval is represented by a **true unbounded PostgreSQL range**, e.g. `tstzrange(start_time, NULL, '[)')`. It is deliberately *not* represented using the timestamp value `'infinity'`, because PostgreSQL treats an unbounded range bound differently from an element value equal to timestamp infinity.

`NULL` for the range itself means the interval is not determinable; it does not mean “still open”.

## Nominal validity

`nominal_valid_from` and `nominal_valid_until` reproduce dates asserted by the administrative source. They do not by themselves determine `legal_effect_status_code`.

## Integrity

For the main canonical White List state tables, GiST exclusion constraints compare:

- the subject identifier;
- effective time;
- observation time; and
- system time.

Two versions are rejected only when all relevant dimensions overlap. When `effective_period` is unknown, the integrity expression treats it as an unbounded wildcard so that an unknown-effective assertion cannot silently coexist with a known-effective assertion over the same observation and system intervals.

This is an integrity rule only: it does **not** convert an unknown effective period into an assertion that the fact was valid for all time.
