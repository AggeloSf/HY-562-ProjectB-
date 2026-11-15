"""Run one read-only local query in a process that the client can time out.

Oxigraph's Python query API has no cancellation parameter. Process isolation lets
SparqlClient enforce its existing timeout without leaving a query running in a
background thread. Input and output are JSON on stdin and stdout.
"""
import json
import sys

import pyoxigraph as ox


def main():
    request = json.load(sys.stdin)
    try:
        store = ox.Store.read_only(request["store"])
        result = store.query(request["query"])
        if isinstance(result, bool) or type(result).__name__ == "QueryBoolean":
            answers = ["true" if bool(result) else "false"]
        else:
            answers = sorted({value.value for row in result for value in row if value is not None})
        response = {"answers": answers}
    except Exception as error:
        response = {"error": f"{type(error).__name__}: {error}"}
    json.dump(response, sys.stdout)


if __name__ == "__main__":
    main()
