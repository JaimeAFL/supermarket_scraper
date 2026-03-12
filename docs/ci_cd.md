# CI/CD: Pipeline paralelo con GitHub Actions

Documentación técnica del sistema de automatización que ejecuta los scrapers semanalmente, maneja fallos parciales y mantiene la base de datos actualizada con commits automáticos.

## Arquitectura del pipeline

El workflow divide el trabajo en **8 jobs independientes**: 7 scrapers en paralelo + 1 job de merge.

```
                        ┌─ mercadona (~30s)  ─→ mercadona.csv  ─┐
                        ├─ carrefour (~15m)  ─→ carrefour.csv  ─┤
                        ├─ dia       (~1m)   ─→ dia.csv        ─┤
Lunes 7:00 AM (España) ──┼─ alcampo   (~17m)  ─→ alcampo.csv   ─┼─→ guardar-en-db ─→ git push
                        ├─ eroski    (~62m)  ─→ eroski.csv     ─┤     (~2 min)
                        ├─ consum    (~2m)   ─→ consum.csv     ─┤
                        └─ condis    (~5m)   ─→ condis.csv     ─┘

Tiempo total: ~64 min (lo que tarda Eroski + merge)
```

## Flujo detallado

### Fase 1: Scraping paralelo (7 jobs simultáneos)

Cada job es una máquina Ubuntu independiente que:

1. Hace checkout del repositorio.
2. Instala Python 3.11 y dependencias (`pip install -r requirements.txt`).
3. Instala Playwright si el scraper lo necesita (Carrefour, Dia, Alcampo, Eroski).
4. Configura variables de entorno desde GitHub Secrets.
5. Ejecuta `run_scraper.py <super> --export-csv export/<super>.csv --skip-db`.
6. Sube el CSV como **artifact** de GitHub Actions.

El flag `--skip-db` es clave: cada job solo genera un CSV, sin tocar la base de datos (cada job tiene su propia máquina con su propio disco — no comparten filesystem).

### Fase 2: Merge (1 job final)

El job `guardar-en-db` se ejecuta cuando los 7 jobs anteriores han terminado (exitosos o fallidos). Su trabajo es:

1. Descargar los artifacts de los 7 jobs.
2. Ejecutar `import_results.py export/*.csv`:
   - Lee cada CSV con pandas.
   - Deduplica por `(Id, Supermercado)`.
   - Pasa cada producto por el normalizador.
   - Hace upsert en `productos` e inserta en `precios`.
3. Hacer `git add database/*.db && git commit && git push`.

## Trigger

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'    # Lunes 6:00 UTC = 7:00 España (invierno) / 8:00 (verano)
  workflow_dispatch:         # Ejecución manual desde la UI de GitHub
```

`workflow_dispatch` permite lanzar el pipeline manualmente desde `Actions → Scraper Semanal → Run workflow`. Útil para recuperar datos tras un fallo o forzar una actualización.

## Estructura del workflow

```yaml
jobs:
  mercadona:          # API REST, sin Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 10
    continue-on-error: true

  dia:                # API REST + cookie automática con Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 10
    continue-on-error: true

  carrefour:          # Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 25
    continue-on-error: true

  alcampo:            # Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 30
    continue-on-error: true

  eroski:             # Playwright + scroll infinito, el más pesado
    runs-on: ubuntu-latest
    timeout-minutes: 80
    continue-on-error: true

  consum:             # API REST, sin Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 10
    continue-on-error: true

  condis:             # API Empathy (REST), sin Playwright
    runs-on: ubuntu-latest
    timeout-minutes: 15
    continue-on-error: true

  guardar-en-db:      # Merge final
    needs: [mercadona, dia, carrefour, alcampo, eroski, consum, condis]
    if: always()
    steps: [checkout, python, deps, download-artifacts (x7), import_results.py, git-commit-push]
```

## Manejo de fallos

### `continue-on-error: true`

Si Eroski falla (timeout, error de red, cambio en la web), **los otros 5 jobs no se ven afectados** y sus CSVs se suben correctamente.

### `if: always()` en el job de merge

El merge se ejecuta siempre, independientemente de cuántos scrapers hayan fallado.

### Descarga de artifacts con `continue-on-error`

Cada paso de descarga de artifact tiene `continue-on-error: true`. Si un scraper falló y no subió su CSV, el paso de descarga falla silenciosamente y el merge continúa con los demás.

### Escenarios de fallo

| Escenario | Resultado |
|---|---|
| Todo OK | 7 CSVs → merge → ~44.800 productos actualizados |
| Eroski falla | 6 CSVs → merge → ~34.800 productos (Eroski mantiene datos anteriores) |
| Eroski + Carrefour fallan | 5 CSVs → merge → ~32.400 productos |
| Todos fallan | 0 CSVs → merge no hace nada → DB sin cambios |
| Merge falla | CSVs se conservan como artifacts 3 días → se puede re-ejecutar |

## Timeouts por job

| Job | Tiempo real | Timeout | Margen |
|---|---|---|---|
| Mercadona | ~30 seg | 10 min | Muy amplio |
| Dia | ~1 min | 10 min | Muy amplio |
| Carrefour | ~15 min | 25 min | +67% |
| Alcampo | ~17 min | 30 min | +76% |
| Eroski | ~62 min | 80 min | +29% |
| Consum | ~2 min | 10 min | Muy amplio |
| Condis | ~5 min | 15 min | +200% |
| Merge | ~2 min | 15 min | Muy amplio |

## Artifacts

Los CSVs se suben con retención de 3 días:

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: mercadona
    path: export/mercadona.csv
    retention-days: 3
```

Esto permite que el job de merge los descargue, permite inspección manual si algo falla, y permite re-ejecutar solo el merge sin repetir los scrapers.

## Git commit automático

```yaml
- name: Commit y push
  run: |
    git config --local user.email "github-actions[bot]@users.noreply.github.com"
    git config --local user.name "github-actions[bot]"
    git add database/*.db
    git diff --staged --quiet || git commit -m "Precios actualizados - $(date +'%Y-%m-%d %H:%M')"
    git push
```

- `git diff --staged --quiet || git commit` evita commits vacíos si nada cambió.
- Solo se commitea la base de datos (`database/*.db`), no los CSVs ni los logs.
- El usuario del commit es `github-actions[bot]` para distinguirlo de commits manuales.

## Secrets de GitHub

| Secret | Usado por | Descripción |
|---|---|---|
| `CODIGO_POSTAL` | Dia, Alcampo, Carrefour | Contexto geográfico de tienda |
| `COOKIE_DIA` | Dia | Cookie de sesión (fallback si la obtención automática falla) |
| `COOKIE_CARREFOUR` | Carrefour | Cookie opcional de fallback |

## Coste

GitHub Actions ofrece minutos gratuitos para repositorios públicos (ilimitados) y privados (2.000/mes en plan gratuito).

| Fase | Minutos-máquina |
|---|---|
| 7 scrapers paralelos | Mercadona(1) + Dia(1) + Carrefour(15) + Alcampo(17) + Eroski(62) + Consum(2) + Condis(5) = **103 min** |
| Merge | ~2 min |
| **Total por ejecución** | **~105 min** |
| **Total mensual (×4)** | **~420 min** |

Muy por debajo del límite gratuito en repositorios privados.

## Ejecución local equivalente

```bash
# Opción 1: secuencial con timeouts por proceso
python main.py

# Opción 2: paralelo manual (equivale a CI/CD)
python run_scraper.py mercadona --export-csv export/mercadona.csv --skip-db &
python run_scraper.py dia       --export-csv export/dia.csv       --skip-db &
python run_scraper.py carrefour --export-csv export/carrefour.csv --skip-db &
python run_scraper.py alcampo   --export-csv export/alcampo.csv   --skip-db &
python run_scraper.py eroski    --export-csv export/eroski.csv    --skip-db &
python run_scraper.py consum    --export-csv export/consum.csv    --skip-db &
python run_scraper.py condis    --export-csv export/condis.csv    --skip-db &
wait
python import_results.py export/*.csv

# Opción 3: un solo scraper directo a DB
python run_scraper.py mercadona
```
