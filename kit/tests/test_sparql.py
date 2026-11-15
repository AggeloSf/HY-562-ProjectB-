import tempfile
import unittest
from pathlib import Path

import pyoxigraph as ox

from sumqa.sparql import SparqlClient


class LocalQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        path = self.root / "store"
        store = ox.Store(str(path))
        store.load('<urn:subject> <urn:property> "hello" .', format=ox.RdfFormat.N_TRIPLES)
        store.flush()
        del store
        self.endpoint = f"oxigraph:{path}"
        self.client = SparqlClient(self.endpoint, cache_dir=str(self.root / "cache"), timeout=10)

    def tearDown(self):
        self.client.close()
        self.client._store = None
        self.temp.cleanup()

    def test_select_ask_and_syntax_error(self):
        result = self.client.query('SELECT ?o WHERE { <urn:subject> <urn:property> ?o }')
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["answers"], ["hello"])
        self.assertEqual(self.client.query('ASK { <urn:subject> ?p ?o }')["answers"], ["true"])
        self.assertEqual(self.client.query('ASK { <urn:missing> ?p ?o }')["answers"], ["false"])
        invalid = self.client.query('this is not SPARQL')
        self.assertFalse(invalid["ok"])
        self.assertIn("SyntaxError", invalid["error"])

    def test_timeout_is_not_cached_and_client_recovers(self):
        query = 'SELECT ?s WHERE { ?s ?p ?o }'
        self.client.timeout = 0.000001
        timed_out = self.client.query(query)
        self.assertFalse(timed_out["ok"])
        self.assertIn("timeout", timed_out["error"])
        self.client.timeout = 10
        result = self.client.query(query)
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["answers"], ["urn:subject"])


if __name__ == "__main__":
    unittest.main()
