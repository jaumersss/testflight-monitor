# Monitor de enlaces públicos de Apple TestFlight

Proyecto simple en Python para revisar enlaces públicos de TestFlight cada 5 minutos con GitHub Actions y enviar una alerta por Telegram solo cuando un enlace cambia de `full` a `open`.

## 1. Crear el bot con BotFather

1. Abre Telegram y busca `@BotFather`.
2. Envía `/newbot`.
3. Sigue los pasos para elegir nombre y usuario.
4. Guarda el token que te da BotFather. Ese valor será `TELEGRAM_BOT_TOKEN`.

## 2. Conseguir el TELEGRAM_CHAT_ID

1. Abre un chat con tu bot y envíale cualquier mensaje.
2. Abre esta URL en el navegador, cambiando `<TOKEN>` por el token del bot:

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

3. Busca el campo `chat.id`.
4. Ese número será `TELEGRAM_CHAT_ID`.

## 3. Crear los secrets en GitHub

En tu repositorio de GitHub:

1. Entra en `Settings`.
2. Entra en `Secrets and variables` > `Actions`.
3. Crea estos secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

Los secrets deben pasarse al workflow como variables de entorno. Este proyecto ya lo hace en `.github/workflows/testflight-check.yml`.

## 4. Editar links.json

Edita `links.json` y añade o cambia entradas con este formato:

```json
{
  "name": "Nombre de la app",
  "url": "https://testflight.apple.com/join/XXXXXXXX"
}
```

## 5. Subir el repo

```bash
git init
git add .
git commit -m "Initial TestFlight monitor"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

## 6. Lanzar una prueba manual

En GitHub:

1. Entra en `Actions`.
2. Selecciona `TestFlight check`.
3. Pulsa `Run workflow`.

## 7. Cambiar la frecuencia del cron

Edita esta línea en `.github/workflows/testflight-check.yml`:

```yaml
- cron: "*/5 * * * *"
```

El cron de GitHub Actions usa sintaxis cron en YAML. Por ejemplo, cada 10 minutos:

```yaml
- cron: "*/10 * * * *"
```

## 8. Cómo funciona

- Lee los enlaces desde `links.json`.
- Guarda el último estado conocido en `state.json`.
- No envía alertas repetidas si todo sigue igual.
- Solo envía Telegram cuando un enlace pasa de `full` a `open`.
- Si hay errores HTTP o de red, marca el enlace como `error` y sigue con los demás.
