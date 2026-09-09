\set ON_ERROR_STOP on

DO $$
DECLARE
    n integer;
    source_country char(2);
    derived_country char(2);
    route text;
BEGIN
    SELECT count(*) INTO n FROM core.address;
    IF n <> 1298 THEN
        RAISE EXCEPTION 'Expected 1298 Cosenza canonical address objects, got %', n;
    END IF;

    SELECT count(*) INTO n FROM core.address WHERE country_code IS NOT NULL;
    IF n <> 0 THEN
        RAISE EXCEPTION 'Source-supported core.address.country_code must not inherit Italy from the Prefecture; found % non-null rows', n;
    END IF;

    SELECT count(*) INTO n
    FROM geo.address_country_assessment
    WHERE upper_inf(system_period);
    IF n <> 1298 THEN
        RAISE EXCEPTION 'Expected one current country assessment for every Cosenza address, got %', n;
    END IF;

    SELECT count(*) INTO n
    FROM geo.address_country_assessment
    WHERE upper_inf(system_period) AND route_code='italian_anncsu';
    IF n <> 1260 THEN
        RAISE EXCEPTION 'Expected 1260 defensibly Italian ANNCSU routes, got %', n;
    END IF;

    SELECT count(*) INTO n
    FROM geo.address_country_assessment
    WHERE upper_inf(system_period) AND route_code='foreign_fallback';
    IF n <> 1 THEN
        RAISE EXCEPTION 'Expected one explicit foreign route, got %', n;
    END IF;

    SELECT count(*) INTO n
    FROM geo.address_country_assessment
    WHERE upper_inf(system_period) AND route_code='unresolved_fallback';
    IF n <> 37 THEN
        RAISE EXCEPTION 'Expected 37 unresolved-country fallback routes, got %', n;
    END IF;

    SELECT ca.source_country_code, ca.derived_country_code, ca.route_code
      INTO source_country, derived_country, route
    FROM core.address a
    JOIN geo.address_country_assessment ca USING(address_id)
    WHERE a.full_address='PARIGI (FR)Rue du Cardinal Demoine 62'
      AND upper_inf(ca.system_period);

    IF source_country IS DISTINCT FROM 'FR'
       OR derived_country IS NOT NULL
       OR route IS DISTINCT FROM 'foreign_fallback' THEN
        RAISE EXCEPTION 'Known Paris source form classified incorrectly: source=%, derived=%, route=%', source_country, derived_country, route;
    END IF;

    SELECT count(*) INTO n
    FROM core.address a
    JOIN geo.address_geocode_result g USING(address_id)
    WHERE a.full_address='PARIGI (FR)Rue du Cardinal Demoine 62'
      AND g.provider_name='anncsu'
      AND upper_inf(g.system_period);
    IF n <> 0 THEN
        RAISE EXCEPTION 'Foreign Paris address leaked into current ANNCSU results (% rows)', n;
    END IF;

    SELECT count(*) INTO n
    FROM geo.address_country_assessment ca
    WHERE upper_inf(ca.system_period)
      AND ca.route_code='italian_anncsu'
      AND COALESCE(ca.source_country_code,ca.derived_country_code) <> 'IT';
    IF n <> 0 THEN
        RAISE EXCEPTION 'Found % ANNCSU routes without defensible Italian country evidence', n;
    END IF;
END;
$$;
