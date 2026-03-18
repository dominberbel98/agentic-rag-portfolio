# Dominio domingoberbel.com en Azure Container Apps

1. Localiza los FQDN generados:
- `az containerapp show -g <rg> -n rag-frontend --query properties.configuration.ingress.fqdn -o tsv`
- `az containerapp show -g <rg> -n rag-backend --query properties.configuration.ingress.fqdn -o tsv`

2. En tu proveedor DNS crea:
- `CNAME @ -> <frontend-fqdn>` (o ALIAS/ANAME si tu DNS no soporta CNAME en root)
- `CNAME api -> <backend-fqdn>`
- `TXT asuid -> <valor-verificacion-front>`
- `TXT asuid.api -> <valor-verificacion-back>`

3. Obtén el valor `asuid` de cada Container App:
- `az containerapp hostname list -g <rg> -n rag-frontend`
- `az containerapp hostname list -g <rg> -n rag-backend`

4. Vincula hostnames en Azure:
- `az containerapp hostname add -g <rg> -n rag-frontend --hostname domingoberbel.com`
- `az containerapp hostname add -g <rg> -n rag-backend --hostname api.domingoberbel.com`

5. Espera la emisión del certificado administrado y verifica HTTPS en ambos hostnames.

6. Ajusta CORS del backend para permitir solo `https://domingoberbel.com`.
