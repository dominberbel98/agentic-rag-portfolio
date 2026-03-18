# Despliegue Final: domingoberbel.com

## Estado

✅ Todos los secretos configurados en `infra/aca/azure.env`
✅ Documentos listos en `documentos/`
✅ Backend con guardrails de trayectoria profesional
✅ Frontend con formulario de contacto recruiter
✅ Sin captcha
✅ Rate limit activado
✅ Logging de preguntas para auditoría

## Próximos pasos (en orden)

### 1. Az login
```bash
az login
```

### 2. Deploy a Azure (crea infraestructura + publica imágenes)
```bash
cd /home/domin/PROYECTOS
source infra/aca/azure.env
chmod +x scripts/deploy_azure.sh
./scripts/deploy_azure.sh
```

⚠️ **Guarda los FQDN que imprime al final** (backend y frontend). Los necesitarás para DNS.

### 3. Ingesta documental (indexa CV + carta)
```bash
pip install python-docx
export PYTHONPATH=/home/domin/PROYECTOS
python scripts/index_documents.py
```

### 4. Setup presupuesto (tope 15 USD/mes)
```bash
chmod +x scripts/setup_budget.sh
./scripts/setup_budget.sh
```

### 5. Hostinger DNS (configuración)

En tu panel de Hostinger:

**Para `api.domingoberbel.com`:**
```
Type: CNAME
Name: api
Value: <backend-fqdn-del-paso-2>
```

**Para `www.domingoberbel.com`:**
```
Type: CNAME
Name: www
Value: <frontend-fqdn-del-paso-2>
```

**Para `domingoberbel.com` (raíz):**
Si Hostinger permite ALIAS/ANAME:
```
Type: ALIAS
Name: @
Value: www.domingoberbel.com
```

Si no, usa redirect HTTP 301 desde Hostinger: `@` -> `www.domingoberbel.com`

### 6. Azure Container Apps - Custom domains

En Azure CLI:
```bash
RG=rg-rag-domingo-prod
az containerapp hostname add -g $RG -n rag-backend --hostname api.domingoberbel.com
az containerapp hostname add -g $RG -n rag-frontend --hostname www.domingoberbel.com
```

También puedes hacerlo en portal.azure.com:
- Container App > Ingress > Custom domains > Add

### 7. Verifica SSL y DNS

```bash
# Debe retornar 200 OK
curl https://api.domingoberbel.com/health

# Debe mostrar tu chat
curl https://www.domingoberbel.com
```

### 8. Auditar preguntas (logs)

Para ver las preguntas que recibe tu RAG:
```bash
curl -H "x-admin-key: <ADMIN_READ_KEY>" \
  https://api.domingoberbel.com/api/admin/questions
```

---

## Estimado de coste

Con 50k tokens/día y gpt-4o:
- Entrada: ~$5-8/mes
- Salida: ~$3-5/mes
- Container Apps: ~$5/mes
- **Total: ~$13-15/mes** ✅ Dentro del presupuesto

## Troubleshooting

**"DNS no resuelve"**
- Espera 24h para que los cambios en Hostinger propaguen
- Verifica CNAME + TXT en Hostinger

**"SSL no funciona"**
- Verifica que TXT de validación esté en Hostinger
- Espera a que Azure emita el certificado gestionado

**"Imagen no se pushea a ACR"**
- Verifica credenciales: `az acr credential show -n <acr-name>`
- Aumenta timeout: `az acr build ... --timeout 600`

**"Documentos no indexan"**
- Verifica que tus .docx estén en `/documentos/`
- Verifica credenciales de Search: `az search admin-key show -g <rg>`
