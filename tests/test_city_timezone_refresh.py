import unittest
from scripts.city_timezone_refresh import retrieve,valid_timezone_record,STATUS

class ZoneRefreshTests(unittest.TestCase):
    def original(self):
        return {"latitude":34.0522,"longitude":-118.2437,"geonames_id":5368361,
            "name":"Los Angeles","admin1":"California","country_code":"US",
            "precision":"CITY_CENTROID_NOT_STADIUM_COORDINATE"}
    def good(self):
        return {"id":5368361,"latitude":34.0522,"longitude":-118.2437,
            "country_code":"US","timezone":"America/Los_Angeles"}
    def test_exact_geoname_and_coords_required(self):
        self.assertEqual(valid_timezone_record(self.original(),self.good()),
                         "America/Los_Angeles")
        bad=self.good();bad["id"]=999
        self.assertIsNone(valid_timezone_record(self.original(),bad))
        bad=self.good();bad["longitude"]=-88
        self.assertIsNone(valid_timezone_record(self.original(),bad))
        bad=self.good();bad["timezone"]="PST"
        self.assertIsNone(valid_timezone_record(self.original(),bad))
    def test_only_missing_city_zones_are_fetched(self):
        first=self.original()
        second={**first,"geonames_id":22,"timezone":"America/Los_Angeles"}
        calls=[]
        def fetch(k):
            calls.append(k)
            return self.good()
        cache,qa=retrieve({"first":first,"second":second},fetch=fetch)
        self.assertEqual(calls,[5368361])
        self.assertEqual(cache["first"]["timezone"],"America/Los_Angeles")
        self.assertEqual(qa["completed_with_verified_timezone"],1)
        self.assertFalse(qa["historical_source_publication_authenticated"])
    def test_invalid_response_is_not_guessed(self):
        cache,qa=retrieve({"first":self.original()},fetch=lambda _:{"error":"Unavailable"})
        self.assertIsNone(cache["first"].get("timezone"))
        self.assertEqual(qa["unresolved"],1)
    def test_request_budget_guards_cost(self):
        with self.assertRaisesRegex(ValueError,"budget"):
            retrieve({"first":self.original()},max_requests=0,fetch=lambda _:self.good())
if __name__=="__main__":unittest.main()
