from core.mcp import mcp


import hal_tools.search_authors
import hal_tools.search_author_publications
import hal_tools.get_author_affiliations
import hal_tools.search_structures
import hal_tools.count_anr_publications
import hal_tools.get_publication_statistics_by_structure
import hal_tools.search_lab_keyword_statistics

HOST = "0.0.0.0"
PORT = 8000

app = mcp.streamable_http_app(stateless_http=True, host=HOST)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT, stateless_http=True)