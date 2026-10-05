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
