from core.mcp import mcp


import hal_tools.search_authors
import hal_tools.search_author_publications
import hal_tools.get_author_affiliations
import hal_tools.search_structures
import hal_tools.search_structure_publications
import hal_tools.get_structure_topics
import hal_tools.search_publications_by_topic
import hal_tools.search_projects
import hal_tools.get_project_publications
import hal_tools.search

HOST = "0.0.0.0"
PORT = 8000

app = mcp.streamable_http_app(stateless_http=True, host=HOST)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT, stateless_http=True)