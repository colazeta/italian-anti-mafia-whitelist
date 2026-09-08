# Territorial register labels and date presentation

The ordinary register is one register type, with separate territorial registers.
The approved dataset contains `cosenza-ordinary`, `parma-ordinary` and
`pistoia-ordinary`, all exactly named `White List ordinaria`: there are no whitespace
or character variants in these labels. The old selector keyed by register identity
but displayed only the common name. It now displays the name and issuing Prefecture.
Bologna's provincial and post-sisma registers remain distinct. No identity or
population semantics change and no observation is deduplicated by display name.

The existing 5,052 observations contain 1,334 primary dates in Italian day/month/year
format and 3,718 in ISO year-month-day format. All edition reference dates are ISO.
These are differences in source/parser representation, not differences in meaning.
Application, decision, observed listing, registration and observed expiry remain
separate date fields with their existing labels.

## Display contract

- Complete, calendar-valid `YYYY-MM-DD` or `D/M/YYYY` dates display as `DD/MM/YYYY`.
- Gregorian month lengths and leap years are checked; invalid dates retain their
  original text and an explicit invalid-date label. No automatic rollover occurs.
- Partial, two-digit-year or otherwise uninterpretable values retain their original
  text and an explicit source-value label. No day, month or century is invented.
- Calendar dates never enter JavaScript's timezone-dependent Date parser.
- Check timestamps require an explicit timezone and display as `DD/MM/YYYY HH:mm:ss UTC`.
- Missing dates remain missing. Original values remain accessible in company detail,
  source transcriptions and approved CSV/JSON downloads. Download formats and source
  observations are unchanged; display formatting is not a migration of source data.
- Both original and formatted dates are searchable. Sorting continues to use the
  existing source/reference values, not day-first display strings.

Tests cover territorial label uniqueness, preserved keys and input values, leap
and invalid dates, partial dates, and identical calendar rendering in three timezones.
The real-artifact browser gate checks unique register options, date presentation,
company detail and all existing registry behaviour at desktop and mobile widths.
