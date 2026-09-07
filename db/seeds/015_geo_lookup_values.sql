INSERT INTO registry.geographic_unit_level(code,label,description) VALUES
('country','Country','Country-level unit'),
('nuts1','NUTS 1','NUTS level 1 statistical region'),
('nuts2','NUTS 2','NUTS level 2 statistical region'),
('nuts3','NUTS 3','NUTS level 3 statistical region'),
('region','Region','Italian administrative region'),
('province','Province','Italian province-level administrative unit'),
('metropolitan_city','Metropolitan city','Italian metropolitan city'),
('autonomous_province','Autonomous province','Italian autonomous province'),
('municipality','Municipality','Italian comune/municipality')
ON CONFLICT DO NOTHING;

INSERT INTO registry.geocode_match_status(code,label,description) VALUES
('candidate','Candidate','Candidate returned by a geocoding process'),
('accepted','Accepted','Accepted geocoding result for current use'),
('rejected','Rejected','Rejected geocoding candidate'),
('not_found','Not found','No geocoding candidate found'),
('error','Error','Geocoding attempt failed')
ON CONFLICT DO NOTHING;

INSERT INTO registry.geocode_precision(code,label,description) VALUES
('civic_access','Civic access','Official coordinate of the physical civic access/entrance represented by the address source'),
('address','Address','Address/building-level geocoder result; coordinate may represent an address point or object centroid'),
('rooftop','Rooftop','Building/rooftop-level coordinate'),
('parcel','Parcel','Parcel or cadastral-level coordinate'),
('street','Street','Street-level coordinate'),
('postal_code','Postal code','Postal-code centroid/area'),
('locality','Locality','Municipality/locality-level coordinate'),
('admin','Administrative unit','Higher administrative-unit coordinate'),
('centroid','Centroid','Geographic-unit centroid'),
('unknown','Unknown','Spatial precision cannot be established')
ON CONFLICT DO NOTHING;

INSERT INTO registry.geographic_assignment_method(code,label,description) VALUES
('point_in_polygon','Point in polygon','Assigned from accepted coordinates against a versioned boundary'),
('provider','Provider response','Administrative/statistical unit asserted by the geocoding provider'),
('official_crosswalk','Official crosswalk','Assigned through an official ISTAT/Eurostat code crosswalk'),
('text_match','Text match','Assigned from normalised source address text'),
('manual','Manual','Human-reviewed assignment')
ON CONFLICT DO NOTHING;

INSERT INTO registry.activity_type(code,label) VALUES
('geocode','Geocode'),
('geographic_enrich','Geographic enrichment')
ON CONFLICT DO NOTHING;
