from mcp.server.mcpserver import MCPServer

# host/port/stateless_http ne sont plus des paramètres du constructeur en mcp>=2 :
# ils se passent à chaque appel de run()/streamable_http_app() (voir server.py).
mcp = MCPServer(
    "hal",
    instructions=(
        "Serveur d'accès à l'archive ouverte HAL. Transparence obligatoire : quand une réponse "
        "s'appuie sur hal_solr_search, terminer par une section « Requêtes Solr utilisées » qui "
        "recopie tel quel le champ `solr_queries` de chaque appel retenu, pour que l'utilisateur "
        "puisse vérifier et rejouer la recherche. Pour les autres outils, donner les liens "
        "`verification_url` ou `verification_urls` renvoyés. Ne citer que des publications "
        "présentes dans les résultats."
    ),
)
