# CI/CD: Pipeline paralelo con GitHub Actions

Documentación técnica del sistema de automatización que ejecuta los 5
scrapers semanalmente, maneja fallos parciales y mantiene la base de datos
actualizada con commits automáticos.

## Problema inicial

La primera versión del workflow ejecutaba los 5 scrapers **en secuencia**
dentro de un único job:

```
Mercadona (30s) → Carrefour (15m) → Dia (1m) → Alcampo (17m) → Eroski (62m)
                                                                    │
                                                            Total: ~96 min
```

GitHub Actions tiene un **timeout máximo de 360 minutos** por job, así que
96 minutos no lo superaba. Pero había dos problemas graves:

1. **Si Eroski fallaba en el minuto 60, se perdían los datos de los 4
   supermercados anteriores** que ya se habían scrapeado correctamente.
   Todo corría en el mismo proceso, así que un crash afectaba a todos.

2. **El tiempo era innecesariamente largo.** Los 5 scrapers son independientes
   entre sí — no hay razón para que Mercadona espere a que Eroski termine.

## Solución: Jobs paralelos + merge

El workflow actual divide el trabajo en **6 jobs independientes**: 5 scrapers
que corren en paralelo + 1 job de merge que consolida los resultados.

```
                        ┌─ mercadona (~30s)  ─→ mercadona.csv  ─┐
                        ├─ carrefour (~15m)  ─→ carrefour.csv  ─┤
    Lunes 7:00 AM (España) ───┼─ dia       (~1m)   ─→ dia.csv        ─┼─→ guardar-en-db ─→ git push
                        ├─ alcampo   (~17m)  ─→ alcampo.csv    ─┤     (~2 min)
                        └─ eroski    (~62m)  ─→ eroski.csv     ─┘
                        
    Tiempo total: ~64 min (lo que tarda el más lento + merge)
    Antes:        ~96 min (secuencial)
    Ahorro:       ~32 min (33%)
```

### Flujo detallado

#### Fase 1: Scraping paralelo (5 jobs simultáneos)

Cada job es una máquina Ubuntu independiente que:

1. Hace checkout del repositorio.
2. Instala Python 3.11 y dependencias (`pip install -r requirements.txt`).
3. Instala Playwright si el scraper lo necesita.
4. Configura variables de entorno desde GitHub Secrets.
5. Ejecuta `run_scraper.py <super> --export-csv export/<super>.csv --skip-db`.
6. Sube el CSV como **artifact** de GitHub Actions.

El flag `--skip-db` es clave: cada job solo genera un CSV, sin tocar
la base de datos. Esto es necesario porque cada job tiene su propia
máquina con su propio disco — no comparten filesystem.

El flag `--export-csv` guarda el DataFrame completo en un CSV que luego
será recogido por el job de merge.

#### Fase 2: Merge (1 job final)

El job `guardar-en-db` se ejecuta **solo cuando los 5 jobs anteriores
han terminado** (exitosos o fallidos). Su trabajo es:

1. Descargar los artifacts de los 5 jobs.
2. Ejecutar `import_results.py export/*.csv` que:
   - Lee cada CSV con pandas.
   - Deduplica por `(Id, Supermercado)`.
   - Pasa cada producto por el normalizador.
   - Hace upsert en la tabla `productos`.
   - Inserta registro de precio en la tabla `precios`.
3. Hacer `git add database/*.db && git commit && git push`.

## Manejo de fallos

### `continue-on-error: true`

Cada job de scraper tiene esta directiva. Significa que si Eroski falla
(timeout, error de red, cambio en la web), **los otros 4 jobs no se
ven afectados** y sus CSVs se suben correctamente.

```yaml
eroski:
    runs-on: ubuntu-latest
    timeout-minutes: 80
    continue-on-error: true    # ← Si falla, no bloquea el pipeline
```

### `if: always()` en el job de merge

El job de merge se ejecuta **siempre**, independientemente de cuántos
scrapers hayan fallado:

```yaml
guardar-en-db:
    needs: [mercadona, dia, carrefour, alcampo, eroski]
    if: always()    # ← Se ejecuta aunque algún job haya fallado
```

### Descarga de artifacts con `continue-on-error`

Cada paso de descarga de artifact también tiene `continue-on-error: true`.
Si Eroski falló y no subió su CSV, el paso de descarga falla silenciosamente
y el merge continúa con los 4 CSVs disponibles:

```yaml
- name: Descargar resultados de Eroski
  uses: actions/download-artifact@v4
  with:
    name: eroski
    path: export/
  continue-on-error: true    # ← Si no existe el artifact, continúa
```

### Escenarios de fallo

| Escenario | Resultado |
|---|---|
| Todo OK | 5 CSVs → merge → ~30.000 productos actualizados |
| Eroski falla | 4 CSVs → merge → ~20.000 productos (Eroski mantiene datos del día anterior) |
| Eroski + Carrefour fallan | 3 CSVs → merge → ~17.500 productos actualizados |
| Todos fallan | 0 CSVs → merge no hace nada → DB sin cambios |
| Merge falla | CSVs se conservan como artifacts 3 días → se puede re-ejecutar |

## Timeouts por job

Cada job tiene un timeout calculado como **1.3x el tiempo real medido**,
con un mínimo de 10 minutos:

| Job | Tiempo real | Timeout | Margen |
|---|---|---|---|
| Mercadona | ~30 seg | 10 min | Muy amplio (API rápida y estable) |
| Dia | ~1 min | 10 min | Muy amplio (API rápida) |
| Carrefour | ~15 min | 25 min | +67% |
| Alcampo | ~17 min | 30 min | +76% |
| Eroski | ~62 min | 80 min | +29% |
| Merge | ~2 min | 15 min | Muy amplio |

Eroski tiene el margen más ajustado porque ya es el job más largo.
Si la web de Eroski se vuelve más lenta, puede ser necesario subir
el timeout.

## Secrets de GitHub

El workflow usa los siguientes secrets configurados en
Settings → Secrets and variables → Actions:

| Secret | Usado por | Descripción |
|---|---|---|
| `CODIGO_POSTAL` | Dia, Alcampo, Carrefour, Eroski | Código postal/contexto de tienda donde aplica |
| `COOKIE_DIA` | Dia | Cookie de sesión (fallback si la obtención automática falla) |
| `COOKIE_CARREFOUR` | Carrefour | Cookie opcional de fallback/compatibilidad |

## Artifacts

Los CSVs generados por cada job se suben como artifacts de GitHub Actions
con una retención de 3 días:

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: mercadona
    path: export/mercadona.csv
    retention-days: 3
```

Esto permite:
- Que el job de merge los descargue.
- Inspección manual si algo falla.
- Re-ejecución del merge sin re-ejecutar los scrapers.

Después de 3 días, los artifacts se eliminan automáticamente para
no consumir almacenamiento.

## Git commit automático

El paso final del merge hace commit de la base de datos actualizada:

```yaml
- name: Commit y push
  run: |
    git config --local user.email "github-actions[bot]@users.noreply.github.com"
    git config --local user.name "github-actions[bot]"
    git add database/*.db
    git diff --staged --quiet || git commit -m "Precios actualizados - $(date +'%Y-%m-%d %H:%M')"
    git push
```

Puntos importantes:

- `git diff --staged --quiet || git commit` evita hacer commits vacíos
  si nada cambió (e.g., todos los scrapers fallaron).
- El usuario del commit es `github-actions[bot]` para distinguirlo
  de commits manuales en el historial de git.
- El mensaje incluye fecha y hora para trazabilidad.
- Solo se commitea la base de datos (`database/*.db`), no los CSVs
  temporales ni los logs.

## Trigger

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'    # Lunes 6:00 UTC = 7:00 España (invierno) / 8:00 (verano)
  workflow_dispatch:         # Ejecución manual desde la UI de GitHub
```

`workflow_dispatch` permite ejecutar el pipeline manualmente desde
Actions → Scraper Semanal de Supermercados → Run workflow. Útil para testing y para
recuperar datos tras un fallo.

## Estructura del workflow

```yaml
# scraper_semanal.yml

jobs:
  mercadona:          # Job 1: scraper
    runs-on: ubuntu-latest
    timeout-minutes: 10
    continue-on-error: true
    steps: [checkout, python, deps, run, upload-artifact]

  dia:                # Job 2: scraper
    ...

  carrefour:          # Job 3: scraper
    ...

  alcampo:            # Job 4: scraper
    ...

  eroski:             # Job 5: scraper
    ...

  guardar-en-db:      # Job 6: merge
    needs: [mercadona, dia, carrefour, alcampo, eroski]
    if: always()
    steps: [checkout, python, deps,
            download-artifacts (x5),
            import_results.py,
            git-commit-push]
```

## Coste

GitHub Actions ofrece 2.000 minutos/mes gratis para repositorios públicos
y 2.000 para privados (plan gratuito).

Consumo semanal del pipeline:
- 5 jobs paralelos: Mercadona (1) + Dia (1) + Carrefour (15) + Alcampo (17) + Eroski (62) = **96 minutos-máquina**
- 1 job merge: ~2 minutos
- **Total: ~98 minutos/semana**

Consumo mensual: ~98 × 4 = **~392 minutos/mes**.

Muy por debajo del límite gratuito tanto en repositorios públicos
(minutos ilimitados) como privados (2.000 minutos/mes).

## Ejecución local

El mismo pipeline se puede reproducir localmente:

```bash
# Opción 1: secuencial (lo que hace main.py)
python main.py

# Opción 2: paralelo con scripts
python run_scraper.py mercadona --export-csv export/mercadona.csv --skip-db &
python run_scraper.py dia --export-csv export/dia.csv --skip-db &
python run_scraper.py carrefour --export-csv export/carrefour.csv --skip-db &
python run_scraper.py alcampo --export-csv export/alcampo.csv --skip-db &
python run_scraper.py eroski --export-csv export/eroski.csv --skip-db &
wait
python import_results.py export/*.csv

# Opción 3: un solo scraper directo a DB
python run_scraper.py mercadona
```

## Evolución futura

- **Notificaciones:** añadir un paso que envíe un resumen por email o
  Telegram si algún scraper falla.
- **Cache de dependencias:** usar `actions/cache` para cachear pip y
  Playwright, reduciendo el tiempo de setup de ~45s a ~5s por job.
- **Matrix strategy:** refactorizar los 5 jobs de scraper a un solo
  job con `strategy.matrix` para reducir duplicación de YAML.
  No se hizo inicialmente porque cada scraper tiene requisitos distintos
  (Mercadona no necesita Playwright, Dia necesita secrets específicos).
