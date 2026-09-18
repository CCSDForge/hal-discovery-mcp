from mcp.server.mcpserver import MCPServer

# host/port/stateless_http ne sont plus des paramètres du constructeur en mcp>=2 :
# ils se passent à chaque appel de run()/streamable_http_app() (voir server.py).
mcp = MCPServer("hal")
