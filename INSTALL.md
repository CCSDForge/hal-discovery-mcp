# Minimal instructions

# With docker

## Installation

`make build up`

## Apache configuration notes

To declare MCP access without authentication, those URL must return 404, it's generally not required to have specific instructions, but in case of those Urls doesn't return 404, you will need to add some code like that.
`
    <LocationMatch  "/.well-known/oauth-protected-resource">
         Redirect 404 /
    </LocationMatch>
    <LocationMatch  "/.well-known/oauth-authorization-server">
         Redirect 404 /
    </LocationMatch>
    <LocationMatch  "/.well-known/openid-configuration*">
         Redirect 404 /
    </LocationMatch>
`

## Public URL and VOSviewer links

The `build_network` tool returns links to VOSviewer Online that point back to this server
(`<PUBLIC_URL>/network.json`). Set the public address of the MCP when starting the container:

`make up PUBLIC_URL=https://api-preprod.archives-ouvertes.fr/mcp` (default: `https://api.archives-ouvertes.fr/mcp`)

Apache must forward `/mcp/network.json` to the container like `/mcp`, and must not strip the
`Access-Control-Allow-Origin` header: VOSviewer Online (https://app.vosviewer.com) loads this
JSON from the user's browser.
