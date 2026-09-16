# Arcs de cercle et formats d'échange — analyse et plan de travail

> Document de travail interne. Objet : permettre à django-oapif de servir des géométries à segments
> circulaires (`CIRCULARSTRING`, `COMPOUNDCURVE`, `CURVEPOLYGON`, `MULTICURVE`, `MULTISURFACE`) à un
> client QGIS, et répartir le travail en branches.
>
> **Cadre fixé pour cette étude :**
> 1. **Client cible : QGIS `master` et versions futures uniquement.** La série 3.x n'est pas
>    considérée.
> 2. **La sérialisation appartient au middleware.** PostGIS sérialise *la géométrie*, ligne par
>    ligne ; c'est Django qui assemble l'entité et le conteneur. Pas d'agrégat serveur type
>    `ST_AsFlatGeobuf` ni de `ST_AsGeoJSON(record)`.
> 3. **Patcher QGIS est possible**, mais on cherche à rester dans un format standard.
>
> Les affirmations marquées **[vérifié]** ont été reproduites localement : PostGIS 3.5.2,
> GDAL 3.12.0 / 3.13.2 / 3.14dev (= `master`), pile `docker compose` du dépôt, lecture du code source
> QGIS `master` / `release-4_2` / `release-4_0`. Commandes en
> [annexe](#annexe--reproduction-des-mesures).

---

## 1. Résumé

**Il existe une réponse normative OGC au problème, et QGIS l'implémente déjà : JSON-FG.**
La norme *OGC Features and Geometries JSON* (21-045r1) définit une classe de conformité
**Circular Arcs** couvrant exactement nos cinq types, et le fournisseur OAPIF de QGIS ≥ 4.0 sait déjà
la négocier. Le travail est donc **entièrement côté serveur** : pas de patch client pour la lecture.

| Option | Porte les arcs ? | Middleware | Client QGIS | Verdict |
|---|---|---|---|---|
| **GeoJSON** (actuel) | **Non — impossible** | — | natif | statu quo : HTTP 500 sur données courbes |
| **JSON-FG** | **Oui — classe de conformité OGC** | JSON pur, **zéro dépendance** | **déjà supporté** | ✅ **cible** |
| **FlatGeobuf** | **Oui** [vérifié] | encodeur à écrire (GDAL ou pur Python) | **déjà supporté** | ✅ meilleur compromis perf/standard |
| **GML 3.2** | **Oui** [vérifié] | XML à assembler | **déjà supporté** | ⚠️ repli, hors classe de conformité |
| **GeoArrow** (`geoarrow.wkb`) | **Oui** [vérifié] — voir §5.4 | pyarrow (~50 Mo), mais **encodeur trivial** | GDAL lit ; **QGIS n'a aucun import Arrow** | ⚠️ viable, mais seul à exiger un patch en lecture |
| **WKB hex dans le GeoJSON** | Oui | **le plus rapide** (passe-plat) | patch C++, non standard | ❌ perf. gagnante, contrat perdant — voir §5.5 |

**Quatre conclusions structurantes :**

1. **La lecture ne demande aucun patch QGIS.** JSON-FG, FlatGeobuf et GML sont déjà négociés par le
   fournisseur OAPIF via les liens `rel="items"`. En revanche la liste des types de médias acceptés
   est une **liste blanche fermée** : il faut annoncer exactement l'un d'eux. [§3.1]
2. **Le budget « patch QGIS » doit aller à l'écriture, pas à la lecture.** QGIS renvoie ses
   modifications en `application/geo+json` dans toutes les versions, `master` inclus : un client qui
   reçoit un arc, déplace un sommet et enregistre **relinéarise silencieusement**. Aucun standard ne
   couvre l'écriture des arcs — c'est le seul endroit où un patch est à la fois nécessaire et sans
   alternative normative. [§3.3, §7.5]
3. **La contrainte « le middleware sérialise » crée un problème neuf : Python ne sait pas lire une
   courbe — et il faut corriger à *deux* niveaux.** Le GEOS du conteneur (3.11.1) rejette le WKB
   courbe ; **GEOS 3.13 le lit correctement**, mais Django échoue quand même par-dessus
   (`KeyError: 8`), son `_GEOS_CLASSES` ne couvrant que les identifiants 0 à 7. Le correctif annoncé
   pour `django.contrib.gis.geos` doit donc **s'accompagner d'une montée de GEOS à ≥ 3.13** (base
   *trixie* au lieu de *bookworm*). Alternative sans dépendance : un lecteur WKB maison de ~60 lignes.
   **C'est la brique à traiter en premier.** [§2.3, §7.1]
4. **Le passe-plat WKB est bien ~10 à 16× moins cher que de matérialiser des coordonnées** — mesuré
   des deux côtés (§4.3). Mais JSON-FG reste **moins cher que le chemin GeoJSON actuel**, donc
   l'adopter n'est pas une régression. Et surtout : **FlatGeobuf donne le bénéfice du WKB sans patch
   client**, le parsing étant payé en C++ par GDAL. Le WKB n'est pas à abandonner — il est à placer
   dans le bon conteneur.

Trois axes à ne pas confondre : **encodage** (quel conteneur) · **fidélité** (linéarisé ou arcs
exacts) · **direction** (lecture ou écriture).

---

## 2. Le constat, vérifié

### 2.1 Où se situe la limite

L'hypothèse « limitation de lwgeom » est **exacte mais incomplète** : deux limites se superposent.

**a) RFC 7946 (GeoJSON) n'a pas d'arcs.** Sept types permis, aucune courbe. Ce n'est donc pas un
défaut réparable dans PostGIS. L'OGC le dit dans OAPIF Part 1 (17-069r4), qui range parmi les cas
hors périmètre de GeoJSON :

> « Geometries that include non-linear curve interpolations that cannot be simplified
> (e.g., use of arcs in authoritative geometries) »

**b) liblwgeom refuse plutôt que de linéariser** [vérifié] :

```
ST_AsGeoJSON('CIRCULARSTRING(0 0, 1 1, 2 0)')
  ERROR XX000: lwgeom_to_geojson: 'CircularString' geometry type not supported
```

`asgeojson_geometry()` (`liblwgeom/lwout_geojson.c`) n'a pas de branche pour les types courbes et
tombe dans un `lwerror`. Idem pour les quatre autres types, avec ou sans `bbox=true`. PostGIS
documente lui-même la limite ainsi : *« GeoJSON only supports SFS 1.1 geometry types (no curve
support for example) »*. Le comportement est inchangé de PostGIS 2.0 à `master`, et aucun ticket ne
prévoit de l'amender.

C'est une **erreur PostgreSQL au niveau de l'instruction** : **une seule ligne courbe fait échouer la
totalité de la réponse `/items`**. Vérifié de bout en bout sur la pile du dépôt [vérifié] :

```
GET /oapif/collections/tests.geometry_2056/items      (1 ligne droite + 1 arc)
  → HTTP 500
    django.db.utils.InternalError: lwgeom_to_geojson: 'CircularString' geometry type not supported

# la même requête après suppression de la seule ligne courbe
  → HTTP 200  {"type": "FeatureCollection", "features": [ … ]}
```

### 2.2 Le chemin actuel dans ce dépôt

Dans [`django_oapif/handler.py`](django_oapif/handler.py) :

```python
qs = qs.only("pk", *self.get_fields(request))           # get_fields() exclut le champ géométrie
geometry_query = geom_field if crs.srid == self.srid else Transform(geom_field, crs.srid)
qs = qs.annotate(_oapif_geometry=Cast(AsGeoJSON(geometry_query, bbox=True), JSONField()))
```

L'architecture est déjà celle que l'on veut garder : **PostGIS sérialise la géométrie ligne par
ligne, Django assemble l'entité.** Le refactoring consiste à rendre *l'expression de géométrie*
et *l'assembleur* interchangeables, pas à déplacer le travail vers la base.

Quatre propriétés à connaître avant d'y toucher :

- **Le point de rupture est cette unique annotation.** Le modèle de test `Geometry_2056`
  ([`models.py:150`](tests/django_oapif_tests/tests/models.py#L150)) utilise
  `models.GeometryField(srid=2056)` → colonne `geometry(Geometry, 2056)`, qui **accepte les cinq
  types courbes sans migration** [vérifié]. C'est le support de test naturel.
- **La colonne géométrie n'est jamais chargée en Python.** `only()` la laisse déférée : GEOS n'est
  pas dans la boucle de lecture — ce qui est précisément ce qui rend le support des courbes possible
  aujourd'hui (§2.3).
- `_model_to_feature()` construit le schéma pydantic **par appel de constructeur** : **chaque
  géométrie est revalidée par pydantic pour chaque entité.** Coût Python non négligeable, hypothèse à
  falsifier au banc d'essai (§8.4 n° 2).
- `queryset_to_featurecollection()` calcule la bbox de collection en lisant `geometry.bbox` sur
  **chaque** entité — bbox fournie gratuitement par `ST_AsGeoJSON(…, bbox=true)`. **Tout autre
  encodage devra la fournir autrement** (annotation `Box2D()` ou agrégat `ST_Extent` sur la page).
  Dépendance cachée du refactoring.

Enfin, [`django_oapif/schema.py`](django_oapif/schema.py) : `OAPIFLink` n'a que
`href/rel/type/title`. Il faudra **ajouter le membre `profile`** (tableau de chaînes) — c'est ce que
QGIS lit pour découvrir JSON-FG (§3.1).

### 2.3 Le problème neuf : Python ne sait pas lire une courbe

C'est la conséquence directe de « le middleware sérialise ». Testé **dans le conteneur Django du
dépôt** [vérifié] :

```
GEOS (conteneur django) : 3.11.1-CAPI-1.17.1
GEOSGeometry(WKB courbe) -> FAIL: ParseException: Unknown WKB type 8
GEOSGeometry(WKT courbe) -> FAIL: ParseException: Unknown type: 'CIRCULARSTRING'
shapely: absent   pyarrow: absent   osgeo: absent   pyogrio: absent
```

**Le seuil de GEOS est 3.13**, établi en interrogeant `libgeos_c` directement (ctypes,
`GEOSWKBReader_read` / `GEOSWKTReader_read`) [vérifié] :

| GEOS | WKB courbe | WKT courbe |
|---|---|---|
| **3.11.1** (Debian bookworm — *le conteneur actuel*) | ❌ | ❌ |
| **3.13.1** (Debian trixie) | ✅ `CircularString`, `CurvePolygon` | ✅ |
| **3.15.0** (Debian sid) | ✅ | ✅ |

*(Le refus de shapely 2.1.2 malgré GEOS 3.13.1 — `NotImplementedError: Nonlinear geometry types are
not currently supported` — est bien un garde-fou de shapely, pas une limite de GEOS.)*

**Mais GEOS capable ne suffit pas : Django bloque par-dessus.** Avec Django 6.1 sur GEOS 3.13.1
[vérifié] :

```
GEOSGeometry(WKB courbe)  -> ECHEC  KeyError: 8
GEOSGeometry(WKT courbe)  -> ECHEC  KeyError: 8
```

La cause est à `django/contrib/gis/geos/geometry.py:55-65` : le dictionnaire `_GEOS_CLASSES` ne
couvre que les identifiants GEOS **0 à 7** (`Point` … `GeometryCollection`), et la ligne 65 fait
`_GEOS_CLASSES[self.geom_typeid]` — d'où le `KeyError` sur le type 8. Il manque les classes 8 à 12
(`CircularString`, `CompoundCurve`, `CurvePolygon`, `MultiCurve`, `MultiSurface`).

> **Le correctif maison annoncé pour `django.contrib.gis.geos` vise donc exactement cet endroit.
> En fournir la référence** (branche / PR) : il rend la route A ci-dessous facultative. Deux
> conditions à réunir ensemble :
> 1. **monter GEOS à ≥ 3.13** — le `Dockerfile` part de `python:3.12-bookworm`, qui apporte
>    GEOS 3.11.1 ; une base *trixie* suffit. **Sans cela le correctif Django ne servira à rien.**
> 2. **le correctif Django lui-même**, pour les identifiants 8 à 12.
>
> Bonne nouvelle sur le périmètre : pour JSON-FG il faut seulement *lire* des coordonnées, pas
> exécuter d'opérations géométriques sur des courbes (ça, c'est GEOS 3.15+, cf. la PR QGIS `#66866`).

À noter que la voie GEOS n'est pas forcément la plus économique : le lecteur WKB de la route A
ci-dessous fait ~60 lignes, n'a aucune dépendance, et parse 10 000 arcs en 21 ms (§4.3).

Deux routes pour amener les coordonnées d'un arc jusqu'à Python, toutes deux validées [vérifié] :

**Route A — un petit lecteur WKB ISO en Python pur** (~100-150 lignes, sans dépendance). Il consomme
la sortie de `ST_AsBinary` et rend `(type, coordonnées)`. C'est la brique la plus réutilisable :
elle sert JSON-FG, et servirait aussi un encodeur FlatGeobuf en Python pur.

**Route B — laisser PostGIS décomposer**, sans écrire de parseur :

```sql
-- points de contrôle d'un CircularString, en coordonnées JSON prêtes à l'emploi
SELECT ST_AsGeoJSON(ST_MakeLine(ARRAY(SELECT geom FROM ST_DumpPoints(g))));
--   {"type":"LineString","coordinates":[[0,0],[1,1],[2,0]]}   → il suffit de renommer le type

SELECT ST_NumCurves(cc);            -- 2
SELECT ST_AsText(ST_CurveN(cc, 1)); -- CIRCULARSTRING(0 0,1 1,2 0)
SELECT ST_AsText(ST_CurveN(cc, 2)); -- LINESTRING(2 0,3 0)
SELECT ST_AsText(ST_ExteriorRing(cp)); -- CIRCULARSTRING(0 0,4 0,4 4,0 4,0 0)
```

La route B évite tout parseur mais multiplie les allers-retours SQL et devient vite pénible sur les
géométries composées. **Recommandation : route A**, avec la route B comme secours de mise au point.
Chiffrer les deux fait partie de la tâche §7.1.

### 2.4 Ce que PostGIS sait déjà faire, ligne par ligne

Mesuré sur PostGIS 3.5.2 [vérifié]. Seules les fonctions *par géométrie* nous intéressent : les
agrégats (`ST_AsFlatGeobuf`, `ST_AsGeobuf`, `ST_AsMVT`) sortent du cadre de toute façon, puisque le
middleware assemble.

| Fonction (par géométrie) | Courbes | Remarque |
|---|---|---|
| `ST_AsGeoJSON` | ❌ | `ERROR … not supported` |
| **`ST_AsBinary`** | ✅ | WKB **ISO**, codes 8/9/10/11/12, Z/M en `+1000/+2000/+3000`, **sans SRID** |
| `ST_AsEWKB` / `ST_AsHEXEWKB` / `::text` | ✅ | EWKB : Z/M/SRID en bits hauts PostGIS — **moins portable** |
| `ST_AsText` / `ST_AsEWKT` | ✅ | |
| **`ST_AsGML(3, …)`** | ✅ | émet de vrais `<gml:ArcString>` |
| `ST_AsGML(2, …)`, `ST_AsKML`, `ST_AsTWKB`, `ST_AsMVTGeom` | ❌ | |
| `ST_AsSVG` | ✅ | vraies commandes d'arc `A` |
| *(rappel)* `ST_AsFlatGeobuf`, `ST_AsGeobuf` | ❌ | agrégats — hors cadre, et refusent les courbes |

Et les opérations dont dépend `query()` :

| Opération | Courbes | Remarque |
|---|---|---|
| stockage `geometry(Geometry, 2056)` | ✅ | un typmod strict (`geometry(LineString,…)`) rejette, comme attendu |
| index GiST, `&&` | ✅ | |
| `Box2D` / `ST_Envelope` / `ST_Extent` | ✅ | **bbox exacte de l'arc**, pas celle des points de contrôle |
| `ST_Transform` | ✅ | conserve `ST_CircularString` (ne reprojette que les points définissants) |
| `ST_HasArc` | ✅ | permet de repérer les collections concernées |
| `ST_CurveToLine(g, tol, 1, 0)` | ✅ | linéarisation à tolérance maîtrisée |
| `ST_Intersects` | ⚠️ | passe par GEOS → **strokage à 32 segments/quadrant** |

⚠️ Dernier point, piège réel : le filtre `bbox` de `query()` utilise `__intersects`, donc le filtrage
spatial sur données courbes est **approximatif** (bug amont PostGIS #5832). À documenter.

**Saveur WKB à retenir : `ST_AsBinary` (ISO), pas `ST_AsEWKB`** [vérifié] :

```
ST_AsBinary  : 0108000000 0300…         (ISO, type 8, sans SRID)
ST_AsEWKB    : 0108000020 08080000 03…  (EWKB, drapeau SRID 0x20000000)
```

L'ISO est ce que GDAL nomme `wkbVariantIso` et ce que QGIS consomme en interne
(`OGR_G_ExportToIsoWkb` + `QgsGeometry::fromWkb`). Le SRID est déjà transporté par OAPIF (`crs`,
`Content-Crs`).

**Corollaire important : `ST_AsBinary` est la primitive universelle du pipeline.** Elle coûte
0,2 µs/entité — **74× moins que `ST_AsGeoJSON`** (§4.1) — et à partir d'elle le middleware peut
produire JSON-FG, FlatGeobuf ou `geoarrow.wkb`. Le WKB n'est donc pas tant un *format de sortie*
qu'un **tuyau interne base → middleware**.

---

## 3. Ce que le client QGIS sait déjà faire

Établi en lisant le source QGIS (`master` = 4.3.0 dev, mêmes mécanismes dans `release-4_0` et
`release-4_2`).

### 3.1 La négociation de format existe déjà

`src/providers/wfs/oapif/qgsoapifitemsrequest.cpp` [vérifié] :

```cpp
QString acceptHeader = u"application/geo+json, application/json"_s;
if ( !mFeatureFormat.isEmpty() )  acceptHeader = mFeatureFormat;
…
if ( mFeatureFormat == "application/flatgeobuf"_L1 )  extension = u"fgb"_s;
else if ( isGML )                                     extension = u"gml"_s;
else                                                  extension = u"json"_s;
const QString vsimemFilename = u"/vsimem/oaipf_%1.%2"_s…arg( extension );
pReg->createProvider( "ogr", vsimemFilename, providerOptions );
```

Autrement dit : **QGIS ne parse pas lui-même** — il écrit la réponse dans `/vsimem` et l'ouvre avec
GDAL. C'est GDAL qui décide de ce qui survit. `nlohmann::json` ne sert que pour `id`, `properties`,
`links` et `numberMatched`.

Le format vient de l'URI (`mFeatureFormat = mURI.outputFormat()`, avec un sélecteur dans l'IHM depuis
`cdb7e8454`, 2025-11-20) et est résolu contre les liens de la collection
(`qgsoapifcollection.cpp:89`) [vérifié] :

```cpp
if ( link.rel == "items"_L1 )
{
  if ( link.type == "application/geo+json"_L1 || link.type == "application/flatgeobuf"_L1 ||
       link.type == PSEUDO_JSONFG_MEDIA_TYPE || link.type.startsWith( "application/gml+xml"_L1 ) )
  {
    if ( link.type == "application/geo+json"_L1 && link.profiles.size() == 1 )
    {
      if ( link.profiles[0] == "http://www.opengis.net/def/profile/ogc/0/jsonfg"_L1 )        { … }
      else if ( link.profiles[0] == "http://www.opengis.net/def/profile/ogc/0/jsonfg-plus"_L1 ) { … }
```

**Contrat serveur, à respecter au caractère près :**

- **liste blanche fermée** de types de médias — un type inconnu est **silencieusement ignoré** ;
- le membre JSON du lien est **`profile`**, un **tableau** de chaînes (`qgsoapifutils.cpp:72`) ;
- pour JSON-FG : `type == "application/geo+json"` **et exactement un** profil, comparé littéralement
  à `…/profile/ogc/0/jsonfg` ou `…/jsonfg-plus` (**`ogc` en minuscules**) ;
- `jsonfg-plus` n'est retenu que si aucun lien `jsonfg` n'existe.

C'est le mécanisme exigé par OAPIF Part 1, exigence 15 :

> « For each feature collection included in the response, the `links` property of the collection
> SHALL include an item for each supported encoding with a link to the features resource
> (relation: `items`). »

### 3.2 Ce que GDAL relit réellement

**Plancher retenu : GDAL ≥ 3.12** (sorti le 2025-11-03, donc antérieur à QGIS 4.0). Les versions
antérieures ne sont pas une cible. Testé sur 3.12.0, 3.13.2 et `master` (3.14.0dev), même arc
[vérifié] :

| Format | GDAL 3.12+ | Remarque |
|---|---|---|
| **JSON-FG** (`place`) | ✅ arcs | `CIRCULARSTRING` lu depuis `place` ; c'est 3.12 qui a apporté ce support |
| **FlatGeobuf** | ✅ arcs | y compris types mélangés et géométries nulles |
| **GML** (`gml:ArcString`) | ✅ arcs | exactement la sortie de `ST_AsGML(3, …)` |
| **Arrow** (`geoarrow.wkb`) | **lecture ✅** | mais **écriture GDAL ❌** — voir §5.4 |
| GeoJSON | ❌ linéarisé | témoin négatif : c'est la limite du format, pas de GDAL |

Les quatre formats candidats sont donc tous fidèles sur la cible. **La version de GDAL cesse d'être
un critère de choix** — ce qui simplifie l'arbitrage : il ne reste que le contrat (standard ou non)
et le coût (§4.3).

Une conséquence pour §5.1 : le mode `jsonfg-plus` **n'est plus requis pour QGIS**, puisque son GDAL
lira `place`. Il garde son intérêt pour les **clients non-QGIS** qui ne connaissent que le GeoJSON —
c'est un choix de compatibilité, plus une nécessité technique.

Le GML relu est *exactement* la sortie de `ST_AsGML(3, …)` : `gml:Curve/segments/ArcString` →
`CIRCULARSTRING`, `gml:Ring/curveMember` → `CURVEPOLYGON`, segments mixtes → `COMPOUNDCURVE`.

Précisions FlatGeobuf, contre les inquiétudes de la proposition :

- **Index spatial optionnel** : `SPATIAL_INDEX=NO` produit un fichier valide **qui préserve l'ordre
  des entités**. Avec l'index, GDAL trie en ordre de Hilbert et réordonne *au sein de la page* —
  l'ordre global reste celui du `ORDER BY` SQL, la pagination `offset` n'est pas cassée.
- **Lisible en flux non seekable** : `cat sans-index.fgb | ogrinfo /vsistdin/` fonctionne.
- Types mélangés et géométries nulles : ✅ [vérifié].

### 3.3 L'écriture : le seul endroit où un patch est nécessaire

`qgsoapifcreatefeaturerequest.cpp` sur `master` [vérifié] :

```cpp
json j = exporter.exportFeatureToJsonObject( fModified );   // QgsJsonExporter
sendPOST( sharedData->mItemsUrl, "application/geo+json", jsonFeature.toUtf8(), … )
```

`addFeatures` → `createFeature`, `changeGeometryValues` → `patchFeature`/`putFeature` : **tout part en
GeoJSON**, y compris sur `master`. Aucun encodage d'écriture alternatif n'existe, et **JSON-FG ne
normalise pas l'écriture**.

Côté serveur, même asymétrie : `collections.py` fait
`GEOSGeometry(feature.geometry.model_dump_json())` — or ce GEOS ne connaît pas les courbes (§2.3) —
et [`django_oapif/geojson.py`](django_oapif/geojson.py) ne modélise que les sept types GeoJSON.

**C'est donc là qu'il faut dépenser la capacité de patcher QGIS**, et c'est traité en §7.5. Pour
rester « sous un format standard » autant que possible, la proposition est de **réutiliser
l'encodage géométrique JSON-FG (`place`) dans le sens requête** : la norme ne le prévoit pas, mais
elle ne l'interdit pas, l'encodage est déjà spécifié, et QGIS sait déjà le produire en lecture — donc
rien n'est inventé, seule la direction change.

### 3.4 Le précédent à copier : QGIS Server

QGIS Server sert déjà du FlatGeobuf en OAPIF (`f27bc6ea0`, 2026-05-22) et des profils GeoJSON /
JSON-FG (`#66462`, 2026-07-07). Contrat de protocole à reprendre tel quel
[vérifié, `src/server/services/wfs3/qgswfs3handlers.cpp`] :

```cpp
setHeader( "Content-Type", "application/flatgeobuf" );
setHeader( "Content-Disposition", "inline; filename=\"<couche>.fgb\"" );
// pagination en en-tête, puisque le binaire ne peut pas porter links[]
addHeader( "Link", "<…>; rel=\"next\"; title=\"Next page\"; type=\"application/flatgeobuf\"" );
```

Et le client sait les lire : `QgsOAPIFGetNextLinkFromResponseHeader( mResponseHeaders, mFeatureFormat )`.
**C'est la réponse à « comment transporter `links` / `numberMatched` dans un format non JSON ».**

---

## 4. Mesures

10 000 entités, EPSG:2056, sans reprojection. Tailles exactes ; **temps sous émulation amd64 sur
Apple Silicon — à lire en rapports, jamais en absolu**. Ces chiffres mesurent la **part base** du
pipeline ; la part middleware reste à mesurer (§8).

### 4.1 Géométries linéaires (lignes de 50 sommets)

| Expression (par géométrie) | Octets | /entité | gzip -6 | Sérialisation PostGIS |
|---|---:|---:|---:|---:|
| `ST_AsGeoJSON` (9 déc.) — **actuel** | 12 880 000 | 1 288 | 2 710 461 | **141,6 ms** |
| `ST_AsGeoJSON` (6 déc.) | 12 760 000 | 1 276 | — | — |
| **`ST_AsBinary`** (WKB brut) | 8 090 000 | 809 | — | **1,9 ms** |
| WKB en hex | 16 180 000 | 1 618 | 2 312 059 | 55,3 ms |
| WKB en base64 | 10 810 000 | 1 080 | 2 480 245 | 40,6 ms |
| `ST_AsGML(3)` | 12 320 000 | 1 232 | — | 100,3 ms |
| `geom::bytea` — *aucune sérialisation* | — | — | — | 2,1 ms |

**Le résultat qui compte pour l'architecture retenue :** `ST_AsBinary` est **quasi gratuit**
(0,2 µs/entité, une copie de la représentation interne), **74× plus rapide que `ST_AsGeoJSON`**.
Puisque le middleware assemble de toute façon, faire remonter du WKB plutôt que du GeoJSON décharge
la base presque entièrement. Reste à vérifier que Python ne reprend pas d'une main ce que PostgreSQL
a rendu de l'autre — c'est l'hypothèse n° 2 du banc d'essai.

À noter : le passage `hex` coûte 53 des 55 ms — c'est l'encodage texte, pas le WKB. **Un conteneur
binaire (FGB, Arrow) supprime ce coût ; un conteneur JSON le paie.**

Enfin, le chemin actuel utilise la précision par défaut de l'`AsGeoJSON` de Django, ce qui gonfle la
charge utile. **Réduire la précision est un gain indépendant et bien moins cher que tout changement
de format** — à tester séparément pour ne pas l'attribuer par erreur au nouveau format.

### 4.2 Géométries courbes (`CIRCULARSTRING` à 3 points)

| Encodage | Octets | /entité | Sommets | gzip -6 | Sérialisation |
|---|---:|---:|---:|---:|---:|
| GeoJSON de `ST_CurveToLine` (défaut) | 25 040 000 | 2 504 | 65 | 3 615 916 | 223,6 ms |
| GeoJSON de `CurveToLine(tol 0,05 m)` | 7 130 000 | 713 | 17 | — | 98,8 ms |
| **WKB hex** (arc exact) | 1 140 000 | **114** | 3 | **128 034** | **4,9 ms** |
| WKB brut (arc exact) | 570 000 | 57 | 3 | — | — |
| **`ST_AsGML(3)`** (arc exact) | 1 940 000 | 194 | 3 | **110 884** | 14,2 ms |

**C'est ici que se joue la décision.** Sur données courbes, servir l'arc exact est simultanément plus
fidèle, **22× plus léger** (28× après gzip) et **46× moins coûteux** en CPU base que servir sa
linéarisation. **Aucun compromis à arbitrer** : le statu quo (erreur 500) et la linéarisation sont
tous deux dominés.

> Ces chiffres portent sur la géométrie seule. Le mode `jsonfg-plus` transporte les *deux*
> représentations : son surcoût est mesuré en §4.3.

### 4.3 Où sérialiser, et ce que ça coûte

Deux questions liées : **peut-on produire le `place` JSON-FG dans la base ?** et **le WKB en
passe-plat est-il vraiment plus performant ?**

**Oui, PostGIS sait produire le `place`**, bien qu'il ne connaisse pas JSON-FG — il suffit de ne
jamais lui demander de sérialiser une courbe *en tant que* courbe. Deux voies fonctionnelles
[vérifié] :

```sql
-- A. dumper les points de contrôle, puis renommer le type
jsonb_build_object('type','CircularString','coordinates',
  (ST_AsGeoJSON(ST_MakeLine(ARRAY(SELECT dp.geom FROM ST_DumpPoints(geom) dp)))::jsonb)->'coordinates')

-- B. réécrire le code de type WKB (8 -> 2), laisser ST_AsGeoJSON travailler, puis renommer
jsonb_set(ST_AsGeoJSON(ST_GeomFromWKB(set_byte(ST_AsBinary(geom),1,2), 2056))::jsonb,
          '{type}', '"CircularString"')          -- penser à retirer le membre "crs" ajouté au passage
```

Les deux rendent exactement `{"type":"CircularString","coordinates":[[…],[…],[…]]}`. La voie B se
généralise mal aux types composés (`CompoundCurve`, `CurvePolygon`), qui demanderaient une fonction
PL/pgSQL récursive sur `ST_CurveN` / `ST_ExteriorRing` / `ST_GeometryN`.

**Coûts mesurés, 10 000 `CIRCULARSTRING`, meilleur de 5.** Attention : les temps PostGIS sont sous
**émulation amd64**, les temps Python en **arm64 natif** — les deux colonnes ne sont donc **pas
comparables entre elles**, seulement à l'intérieur de chacune.

| Travail sur la géométrie | Dans PostGIS | Dans le middleware (Python) |
|---|---:|---:|
| **WKB brut, passe-plat** (`ST_AsBinary`) | **5,0 ms** | — |
| **hex, passe-plat** (hex tel quel dans une chaîne JSON) | 4,9 ms | **2,2 ms** |
| `place` JSON-FG — voie A (dump/relabel) | 74,6 ms | — |
| `place` JSON-FG — voie B (patch du type WKB) | 55,2 ms | — |
| `place` JSON-FG — lecteur WKB maison + `json.dumps` | — | 35,2 ms *(dont 21,0 ms de parsing)* |
| `geometry` de repli (`ST_CurveToLine` → GeoJSON) | 41,2 ms | — |
| *(repère)* `ST_AsGeoJSON` sur la version linéarisée | 142,3 ms | — |

Et sur des géométries **linéaires** de 50 sommets, côté Python : parsing WKB 177 ms, parsing +
`json.dumps` **448 ms**, contre **28,1 ms** pour passer l'hex tel quel — soit le même rapport de ~16×.

**Trois conclusions :**

1. **Le passe-plat WKB est effectivement ~10 à 16× moins cher** que matérialiser des coordonnées,
   des deux côtés. L'intuition est juste : le WKB ne doit pas être abandonné.
2. **Mais le JSON-FG en middleware reste bon marché en absolu** : 35 ms pour 10 000 entités
   courbes, sur un lecteur WKB de ~60 lignes sans dépendance — et c'est **moins que ce que fait le
   code aujourd'hui** (`ST_AsGeoJSON` seul : 142 ms sur la version linéarisée, plus la validation
   pydantic par entité). Passer à JSON-FG n'est donc pas une régression de performance par rapport à
   l'existant ; c'est simplement moins optimal qu'un passe-plat.
3. **`jsonfg-plus` paie les deux** : `place` (55 ms) + `geometry` de repli (41 ms) ≈ 96 ms côté base,
   soit ~19× le passe-plat WKB. C'est le prix de la rétrocompatibilité, et c'est le chiffre à
   surveiller si le volume grandit.

**Le vrai classement, du plus au moins performant sur le travail de géométrie :**

| Rang | Représentation | Travail sur la géométrie | Patch client ? |
|---|---|---|---|
| 1 | `geoarrow.wkb` | **aucun** — les octets de `ST_AsBinary` vont tels quels dans la colonne | **oui** (QGIS n'importe pas Arrow) |
| 2 | WKB hex dans du JSON | aucun — l'hex va tel quel dans une chaîne | **oui** + non standard |
| 3 | FlatGeobuf | parsing du WKB, mais **en C++** (GDAL) et non en Python | non |
| 4 | JSON-FG | coordonnées matérialisées (~35 ms/10k en Python) | **non**, et **standard** |
| 5 | GeoJSON actuel | sérialisation JSON dans PostGIS + revalidation pydantic | non, mais **pas d'arcs** |

L'arbitrage n'est donc pas « rapide contre lent » mais **« le plus rapide au prix d'un patch client »
contre « assez rapide, standard, et sans patch »**. Et c'est précisément pourquoi **FlatGeobuf est
intéressant : c'est le seul qui transporte du WKB sans exiger de patch client** — le coût de parsing
est payé en C++ par GDAL, ni en SQL ni en Python.

---

## 5. Évaluation des options

### 5.1 JSON-FG — la cible

JSON-FG (*OGC Features and Geometries JSON*, OGC 21-045r1) définit une classe de conformité
**Circular Arcs** — `http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs` — couvrant
« CircularString, CompoundCurve, CurvePolygon, MultiCurve, and MultiSurface geometries to support
curves with linear and circular arc interpolation » : **exactement nos cinq types**.

L'architecture est celle qu'il nous faut : les géométries non représentables en GeoJSON vont dans un
membre **additif `place`**, tandis que `geometry` peut porter une **version linéarisée de repli**
(« This fallback geometry could be a simplified version of the value of the `place` member »).
**Le document reste du GeoJSON valide pour tout client qui ignore `place`.**

Encodage exact, obtenu en faisant écrire GDAL lui-même [vérifié] — noter que `CurvePolygon` et
`CompoundCurve` utilisent un membre **`geometries`**, et non `coordinates` :

```json
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [ … ] },   // repli linéarisé (mode jsonfg-plus)
  "place": { "type": "CircularString", "coordinates": [[0,0],[1,1],[2,0]] },
  "properties": { … } }

"place": { "type": "CurvePolygon",  "geometries": [ {"type":"CircularString","coordinates":[…]} ] }
"place": { "type": "CompoundCurve", "geometries": [ {"type":"CircularString","coordinates":[…]},
                                                    {"type":"LineString","coordinates":[…]} ] }
```

Le document racine porte un `conformsTo`, tel que GDAL l'écrit :

```json
"conformsTo": ["http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
               "http://www.opengis.net/spec/json-fg-1/1.0/conf/types-schemas",
               "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs"]
```

- ✅ **Standard OGC**, classe de conformité dédiée à notre problème exact.
- ✅ **Zéro dépendance nouvelle** : c'est du JSON, écrit par le middleware. Le fait que PostGIS ignore
  JSON-FG est **sans objet** — PostGIS n'a qu'à fournir les coordonnées (§2.3).
- ✅ **Négociation standardisée par profil, déjà implémentée par QGIS** (§3.1) : c'est la version
  normalisée de l'idée « le client annonce ce qu'il sait lire ».
- ✅ **Rétrocompatible à la demande** via `jsonfg-plus` (repli linéarisé dans `geometry`) — utile pour
  les clients non-QGIS, facultatif pour QGIS (§3.2).
- ✅ Précédent serveur : ldproxy (le commentaire QGIS renvoie à `ldproxy/ldproxy#1551`), QGIS Server.
- ⚠️ Charge utile plus lourde en `jsonfg-plus` (deux représentations) — à mesurer.
- ⚠️ Demande la brique de §2.3 (coordonnées d'une courbe en Python).
- ❌ Ne résout pas l'écriture (§3.3).

### 5.2 FlatGeobuf

- ✅ **Porte les arcs sans perte** [vérifié de GDAL 3.12.0 à `master`], types mélangés et géométries
  nulles compris.
- ✅ **Déjà consommé par QGIS**, avec sélecteur d'IHM et **test de non-régression en amont**
  (`test_provider_oapif.py::testFlatgeobufOutputFormat`).
- ✅ Index optionnel, ordre préservé, lisible en flux — **la crainte initiale est levée**.
- ✅ Conteneur binaire : supprime le coût d'encodage texte (§4.1).
- ✅ Contrat de protocole déjà documenté par QGIS Server (§3.4).
- ❌ **Un encodeur est à écrire dans le middleware.** Deux voies : GDAL/`pyogrio` (dépendance
  d'exécution, mais accepte directement le WKB de `ST_AsBinary`), ou un encodeur flatbuffers en
  Python pur (aucune dépendance, mais exige la brique §2.3 pour les coordonnées).
  *(`ST_AsFlatGeobuf` est hors cadre par principe — et refuserait les courbes de toute façon
  [vérifié].)*
- ⚠️ `links` / `numberMatched` en en-têtes HTTP (§3.4) : chemin de code distinct du chemin JSON.
- ❌ Ne résout pas l'écriture.

### 5.3 GML 3.2

- ✅ Production de la géométrie **native et triviale** : `ST_AsGML(3, geom)` par ligne. Le middleware
  n'assemble que l'enveloppe XML.
- ✅ **Déjà consommé par QGIS** [vérifié].
- ✅ Le plus compact après gzip sur données courbes (§4.2).
- ⚠️ **Hors profil OAPIF standard** : les classes `gmlsf0`/`gmlsf2` sont **restreintes au linéaire**
  (« restricted to data with 2D geometries with linear/planar interpolation »). Il faut servir
  `application/gml+xml; version=3.2` **sans** profil SF et **ne pas** revendiquer `gmlsf0`/`gmlsf2`
  dans `/conformance`. Permis (OAPIF Core n'impose aucun encodage) mais **aucune classe de conformité
  existante** — contrairement à JSON-FG.
- ⚠️ Le pilote GML de GDAL déduit le typage des champs via un fichier `.gfs` (que QGIS nettoie).
  **Risque : typage variable d'une page à l'autre.**
- ⚠️ `ST_GeomFromGML` ne relit pas les courbes SQL/MM : sortie seulement.
- ❌ Ne résout pas l'écriture.

### 5.4 GeoArrow via `geoarrow.wkb` — la question posée

**L'intuition est juste, et elle se vérifie.** GeoArrow n'a aucun encodage *natif* de courbe — la
liste des noms d'extension est close (`geoarrow.point` … `geoarrow.multipolygon`,
`geoarrow.geometry`, `geoarrow.geometrycollection`, `geoarrow.box`, `geoarrow.wkb`, `geoarrow.wkt`)
et la spec se réclame de Simple Feature Access. **Mais `geoarrow.wkb` est une colonne d'octets
opaques**, et rien n'empêche d'y placer du WKB ISO courbe.

Vérifié : un fichier Arrow fabriqué à la main avec pyarrow, dont la colonne `geometry` porte
`ARROW:extension:name = geoarrow.wkb` et contient le WKB ISO **exact produit par
`ST_AsBinary`**, est relu par GDAL **sans aucune perte** — en format IPC *file* comme en format IPC
*stream*, celui qu'une réponse HTTP transporterait. Testé sur **3.13.2** (dernière version publiée,
2026-07-20) **et sur `master`** (3.14.0dev), résultat identique [vérifié] :

```
OGRFeature(hand):0  name = arc           CIRCULARSTRING (0 0,1 1,2 0)
OGRFeature(hand):1  name = curvepolygon  CURVEPOLYGON (CIRCULARSTRING (0 0,4 0,4 4,0 4,0 0))
OGRFeature(hand):2  name = linestring    LINESTRING (0 0,2 1)
```

Il y a donc une **asymétrie nette** dans GDAL — mêmes résultats sur 3.13.2 et sur `master` :

- **lecture** : GDAL relit parfaitement les arcs d'une colonne `geoarrow.wkb` ;
- **écriture via `ogr2ogr`** : les courbes sont **linéarisées**, même avec `GEOMETRY_ENCODING=WKB` —
  `Warning 1: Attempt to write curve geometries to layer … They will be linearized`.

**Et la cause de cette asymétrie est bénigne.** Ce n'est ni une limite du format, ni du chemin WKB du
pilote : c'est une **capacité non déclarée**. `OGRArrowWriterLayer::TestCapability()`
(`ogr/ogrsf_frmts/arrow_common/ograrrowwriterlayer.hpp:2394`, `master`) ne renvoie `true` que pour
`OLCCreateField`, `OLCCreateGeomField`, `OLCSequentialWrite`, `OLCFastWriteArrowBatch`,
`OLCStringsAsUTF8` et `OLCMeasuredGeometries` — **pas pour `OLCCurveGeometries`**. Or `ogr2ogr` lit
justement ce drapeau et linéarise **en amont du pilote** :

```cpp
// apps/ogr2ogr_lib.cpp:5844
psInfo->m_bSupportCurves = CPL_TO_BOOL( poDstLayer->TestCapability( OLCCurveGeometries ) );
// :7302  if ( !psInfo->m_bHasWarnedAboutCurves && !psInfo->m_bSupportCurves && … )  → linéarisation
```

Deux conséquences :

1. Côté amont, le manque est à une déclaration de capacité près (plus la vérification que le chemin
   WKB laisse passer les octets) — ce n'est pas un obstacle de fond.
2. **Côté nous, c'est sans objet** : dans l'architecture retenue, c'est le middleware qui écrit
   l'Arrow avec pyarrow, pas GDAL. La seule chose qui compte est que GDAL sache **lire**, et il sait.

Conséquence favorable, qu'il faut reconnaître : **c'est l'encodeur middleware le plus simple des
trois.** Les octets de `ST_AsBinary` vont directement dans une colonne binaire — **aucun décodage de
géométrie n'est nécessaire**, donc la brique §2.3 n'est même pas requise (contrairement à JSON-FG et
à un FlatGeobuf en Python pur).

**Y a-t-il un plan pour « implémenter l'écriture des arcs » dans GeoArrow ?** Recherché, réponse :
**non, et il n'y en a pas besoin** [vérifié, requêtes API GitHub] —

- `geoarrow/geoarrow` : **aucune** issue ni PR sur les courbes (les deux résultats de recherche sont
  des faux positifs). Aucun encodage natif de courbe n'est envisagé ;
- `OSGeo/gdal` : **aucun** ticket demandant `OLCCurveGeometries` pour le pilote Arrow ;
- `qgis/QGIS` : la PR d'import Arrow **#65885 « Add OGR specialization for arrow » est fermée, non
  fusionnée** (dernière activité 2026-05-13).

Mais la question est en partie mal posée : **écrire des arcs en GeoArrow ne demande aucune évolution
amont.** `geoarrow.wkb` est une colonne d'octets opaques ; nous écrivons le fichier nous-mêmes avec
pyarrow, et GDAL le relit déjà. La seule pièce manquante est **la lecture côté QGIS**, et là rien
n'est en cours.

Ce qui bloque n'est donc ni la spec ni GDAL, mais le client et l'écosystème :

- ❌ **QGIS n'a aucun chemin d'import Arrow.** `QgsArrowIterator` (QGIS 4.0) est **export seulement**
  (QGIS → `geoarrow.wkb` pour pyarrow) ; la PR d'import n'est pas fusionnée. Et un type
  `application/vnd.apache.arrow.stream` sur un lien `rel="items"` serait **silencieusement ignoré**
  par la liste blanche (§3.1). C'est un **chemin de format entier** à ajouter côté client — le seul
  des candidats à en demander un **en lecture**, alors que FlatGeobuf offre déjà le même service
  nativement.
- ❌ Aucune classe de conformité OGC pour un encodage Arrow en OAPIF ; aucun serveur OAPIF n'en sert.
- ❌ Dépendance pyarrow (~50 Mo par wheel Linux) dans un projet qui ne dépend aujourd'hui que de
  django, ninja et psycopg2.
- ❌ Les deux atouts d'Arrow seraient **annulés par le client** : QGIS tamponne toute la réponse
  (fin du streaming) puis itère entité par entité dans `QgsFeature` (fin du colonnaire).

**Verdict : viable, et côté serveur c'est même l'option la plus légère à écrire — mais elle n'apporte
rien que FlatGeobuf ne donne déjà, tout en étant la seule à exiger un patch QGIS *pour la lecture*.**
Le budget de patch est mieux dépensé sur l'écriture (§7.5), qui elle n'a aucune alternative. À garder
comme *spike* documenté (§7.6) — et le fait que GDAL sache déjà lire signifie qu'un portage futur
serait peu coûteux si QGIS gagne un import Arrow.

### 5.5 WKB hex dans le GeoJSON — l'option la plus rapide, mais la moins standard

**À ne pas écarter sur un malentendu : sur le plan des performances, c'est bien la meilleure**, avec
`geoarrow.wkb` (§4.3). L'hex passe tel quel de PostgreSQL à la réponse : ~2 ms pour 10 000 entités
côté Python contre ~35 ms pour construire le `place` JSON-FG, soit **~16×**. Aucun parsing, aucune
matérialisation de coordonnées, ni en SQL ni en Python.

Ce qui la disqualifie n'est donc pas la performance mais le contrat :

- ❌ elle produit un `application/geo+json` **non conforme à RFC 7946** — un client tiers qui suit le
  type de média reçoit un document invalide ;
- ❌ elle n'est **pas découvrable** par la liste blanche QGIS (§3.1) sans inventer un profil maison,
  là où JSON-FG en a déjà un, normalisé et implémenté ;
- ❌ elle exige un patch client **en lecture**, alors que JSON-FG n'en demande aucun — et il n'existe
  aucune option d'ouverture GDAL permettant de l'éviter [vérifié] :

```
$ ogrinfo -al wkb-en-propriete.geojson -oo GEOM_POSSIBLE_NAMES=geom_wkb
Warning 6: driver GeoJSON does not support open option GEOM_POSSIBLE_NAMES
$ ogrinfo -al wkb-en-colonne.csv -oo GEOM_POSSIBLE_NAMES=geom_wkb     # témoin : marche en CSV
  CIRCULARSTRING (0 0,1 1,2 0)
```

**La bonne façon de garder le bénéfice sans le coût, c'est de choisir un conteneur qui transporte
déjà du WKB** : `geoarrow.wkb` (passe-plat total, mais patch client) ou **FlatGeobuf** (parsing payé
en C++ par GDAL, **sans patch client**). Le WKB reste donc au centre du dispositif — comme tuyau
interne (§2.4) et comme contenu de ces conteneurs — sans qu'on ait à le glisser dans un GeoJSON qui
n'en veut pas.

Si l'on décidait malgré tout de l'exposer (par exemple pour un client maison, hors QGIS), le
signalement doit passer par un **profil** sur `application/geo+json`, jamais par un `?f=`
propriétaire : OAPIF Part 1 ne normalise pas `f=` et impose de déclarer tout paramètre maison dans la
définition d'API, sous peine de 400.

**Le WKB reste central** — comme tuyau interne base → middleware (§2.4), comme contenu de FlatGeobuf
et de `geoarrow.wkb`, et comme encodage d'entrée du chemin d'écriture (§7.5).

---

## 6. Recommandation

1. **`main` d'abord : l'infrastructure de négociation + la brique « courbe → Python »** (§7.1).
   Préalable commun à toutes les branches.
2. **JSON-FG comme cible** (§7.2), en `jsonfg`, plus `jsonfg-plus` si l'on veut ménager les clients
   non-QGIS. Seule option à la fois
   normalisée, déjà négociée par QGIS, rétrocompatible et **sans dépendance nouvelle**. Elle n'est
   pas la plus rapide — matérialiser les coordonnées coûte ~10× un passe-plat WKB — mais elle reste
   **moins chère que le chemin GeoJSON actuel** (§4.3), donc l'adopter n'est pas une régression.
3. **FlatGeobuf ensuite** (§7.3) comme représentation binaire — et c'est le **meilleur compromis
   performance/standard** : c'est le seul conteneur qui transporte le WKB de bout en bout **sans
   patch client**, le parsing étant payé en C++ par GDAL plutôt qu'en SQL ou en Python (§4.3). Si le
   banc d'essai montre que la construction du `place` JSON-FG pèse réellement sur le temps de
   réponse, **c'est vers FlatGeobuf qu'il faut basculer**, pas vers du WKB dans du GeoJSON.
4. **GML 3.2** (§7.4) : petit lot bon marché, utile surtout comme second témoin de fidélité — un
   deuxième chemin arc de bout en bout, très peu coûteux à écrire, qui valide l'infrastructure.
5. **Écriture** (§7.5) : **c'est là que va le budget « patch QGIS »**, et c'est le seul verrou sans
   réponse normative. À traiter dès que la lecture fonctionne, sous peine de livrer une fidélité en
   trompe-l'œil.
6. **GeoArrow** (§7.6) : spike, prototype d'encodeur autorisé pour le chiffrer — mais pas de
   livrable tant qu'aucun client ne sait le lire. C'est l'option la plus légère à écrire côté
   serveur, et la seule à réclamer un patch QGIS **en lecture** : le patch est mieux investi en §7.5.

**Décision de produit à prendre avant de coder : le mode dégradé par défaut.** Une collection courbe
renvoie aujourd'hui une 500 sur `application/geo+json`. Le défaut doit rester du RFC 7946 valide :
il faut choisir entre `ST_CurveToLine(geom, tolérance)` (linéarisation configurable, réponse
utilisable, perte silencieuse) et l'erreur explicite.
**Proposition : linéariser par défaut, tolérance réglable par collection, signalée dans les
métadonnées.** Une 500 sur une donnée valide est un pire défaut qu'une approximation annoncée — et
cette linéarisation est de toute façon nécessaire comme géométrie de repli JSON-FG, donc le travail
est mutualisé.

---

## 7. Travaux à répartir

Une branche par tâche. Tout ce qui est générique atterrit d'abord dans `main`.

### 7.1 `main` — négociation de sortie + lecture des courbes en Python *(préalable)*

**Deux livrables indissociables.**

**a) La brique « courbe → Python »** (§2.3), qui conditionne tout le reste :

Trois routes possibles ; **trancher en premier, car tout le reste en dépend** :

- **route GEOS** — monter la base du `Dockerfile` de *bookworm* (GEOS 3.11.1) à *trixie*
  (GEOS 3.13.1, qui lit les courbes [vérifié]) **et** appliquer le correctif
  `django.contrib.gis.geos` pour les identifiants 8 à 12 (§2.3). C'est la route la plus « propre »
  si le correctif existe et peut être maintenu ; en obtenir la référence avant d'arbitrer ;
- **route A** — lecteur WKB ISO en Python pur (types 8/9/10/11/12, Z/M via les décalages
  `+1000/+2000/+3000`, petit- et gros-boutiste), consommant `ST_AsBinary`. ~60 lignes, aucune
  dépendance, 21 ms pour 10 000 arcs (§4.3). Route de repli sûre, et indépendante de la version de
  GEOS déployée ;
- **route B** — décomposition côté SQL (`ST_CurveN`, `ST_ExteriorRing`, `ST_DumpPoints`) : aucun
  parseur, mais multiplie les allers-retours et se généralise mal aux types composés.

Dans tous les cas : tests d'aller-retour contre `ST_AsText` pour les cinq types, en 2D et 3D.

**b) L'abstraction d'encodeur** (nouveau module, p. ex. `django_oapif/encoders.py`), portant pour
chaque représentation : type de média, `profile` éventuel, extension ; **l'expression SQL de géométrie
à annoter** (`ST_AsGeoJSON`, `ST_AsBinary`, `ST_AsGML`, ou les *deux* pour `jsonfg-plus`) ; la
fabrication de la réponse depuis le queryset ; et la manière de porter `links`, `numberMatched`,
`numberReturned`, `bbox` — dans le corps pour le JSON, **dans les en-têtes HTTP pour le binaire**
(copier QGIS Server, §3.4).

| Fichier | Fonction | Changement |
|---|---|---|
| `django_oapif/handler.py` | `query()` | l'annotation `_oapif_geometry` devient paramétrée par l'encodeur au lieu d'`AsGeoJSON` en dur |
| `django_oapif/handler.py` | `queryset_to_featurecollection()` | ne plus lire `geometry.bbox` par entité (§2.2) : annoter `Box2D()` ou agréger `ST_Extent` sur la page |
| `django_oapif/handler.py` | `get_geometry_schema()` | prévoir les représentations non-GeoJSON |
| `django_oapif/collections.py` | `get_items()`, `get_item()` | résolution de l'encodeur (`Accept` + profil), réponse brute possible |
| `django_oapif/collections.py` | `get_collection_response()` | **un lien `rel="items"` par représentation**, avec `type` et `profile` (§3.1) |
| `django_oapif/schema.py` | `OAPIFLink` | **ajouter `profile: list[str] \| None`** |
| `django_oapif/conformance.py` | `conformance()` | ajouter les URI des encodages réellement servis |

**À vérifier dans la tâche :** comment django-ninja permet de renvoyer des octets avec un
`Content-Type` maison en gardant un OpenAPI correct, sachant que `get_items` déclare
`response=GenericFeatureCollection`.

**Contraintes :**

- Le défaut, sans `Accept` particulier, reste **exactement** l'actuel : GeoJSON RFC 7946 — pour les
  clients non-QGIS (navigateurs, autres SIG).
- `tests/conformance` (suite ETS OGC) doit continuer à passer.
- `tests/integration/test_integration_qgis.py` tourne aujourd'hui sur `qgis/qgis:3.44-noble` :
  **migrer l'image vers 4.x**, puisque 3.x n'est plus une cible.

### 7.2 Branche `jsonfg` — sortie JSON-FG avec arcs *(cible principale)*

- Sérialiser `place` en Python selon §5.1 : `coordinates` pour `CircularString`/`MultiCurve`,
  **`geometries`** pour `CurvePolygon` et `CompoundCurve`.
- Émettre le `conformsTo` racine (`…/conf/core`, `…/conf/types-schemas`, `…/conf/circular-arcs`).
- Servir `jsonfg` (strict) — **c'est le mode principal**, suffisant pour QGIS puisque son GDAL ≥ 3.12
  lit `place` (§3.2). Ajouter `jsonfg-plus` (`place` + `geometry` linéarisée via `ST_CurveToLine`,
  tolérance configurable) **pour les clients non-QGIS** qui ne comprennent que le GeoJSON ; c'est un
  choix de compatibilité, pas une nécessité technique, et il coûte ~2× en sérialisation (§4.3).
- Annoncer les liens `rel="items"` : `type: application/geo+json`, `profile:
  ["http://www.opengis.net/def/profile/ogc/0/jsonfg"]` (resp. `…/jsonfg-plus`). **Exactement un
  profil par lien, `ogc` en minuscules** — QGIS compare littéralement (§3.1).
- **Test de fidélité** : sur GDAL ≥ 3.12, `place` doit revenir en `CIRCULARSTRING` / `CURVEPOLYGON`
  (matrice de §3.2 à figer en test). Les versions antérieures ne sont pas une cible.
- Décider quels autres membres JSON-FG émettre (`featureType`, `coordRefSys`, `time`).

### 7.3 Branche `flatgeobuf` — encodeur middleware

1. **Choisir l'encodeur** : GDAL/`pyogrio` (accepte directement le WKB de `ST_AsBinary`, mais
   dépendance d'exécution) contre flatbuffers en Python pur (aucune dépendance, mais dépend de la
   brique §7.1a). **Vérifier d'abord si `django.contrib.gis` impose déjà libgdal** — si oui,
   l'argument « dépendance lourde » tombe. *(Rappel : le conteneur Django installe `gdal-bin` mais
   **pas** les bindings Python `osgeo` [vérifié].)*
2. `SPATIAL_INDEX=NO` ou index ? Mesurer, vérifier l'effet sur la pagination.
3. Réponse en flux ou tamponnée ? (QGIS tamponne côté client — décider sur la mémoire serveur.)
4. Reproduire le contrat QGIS Server (§3.4) : `Content-Type`, `Content-Disposition`, pagination en
   en-tête `Link`.
5. Test d'intégration sur une image `qgis/qgis:4.x`.

**Piège de méthode découvert pendant l'analyse :** ne pas vérifier la fidélité avec
`ogr2ogr -f CSV … -lco GEOMETRY=AS_WKT`. Sur une couche contenant une géométrie nulle, ce chemin
produit `ERROR 6: Unsupported WKB type 0` et **décale silencieusement les géométries** ; le fichier
FGB, lui, est correct. Vérifier avec `ogrinfo -al` ou l'API OGR Python.

### 7.4 Branche `gml-arcs` — sortie GML 3.2 *(petit lot)*

- `Func` Django pour `ST_AsGML(3, geom, …)` (absent de `django.contrib.gis.db.models.functions`).
- Encodeur `application/gml+xml; version=3.2`, assemblage de l'enveloppe XML côté middleware.
- **Ne pas** revendiquer `gmlsf0`/`gmlsf2` dans `/conformance` (§5.3).
- Tester la stabilité du typage déduit par GDAL (`.gfs`) sur plusieurs pages.

### 7.5 Branche `write-arcs` — l'aller-retour d'édition *(le vrai verrou)*

Deux moitiés ; la première a de la valeur **même sans patch QGIS**.

**Serveur :**
- accepter une géométrie courbe en entrée sur POST/PUT/PATCH, encodée en **JSON-FG `place`**
  (même encodage qu'en lecture — rien de nouveau à spécifier) et/ou en **WKB hex** ;
- **insérer sans passer par GEOS** : `ST_GeomFromWKB()` / `ST_GeomFromText()` en expression SQL au
  lieu de `GEOSGeometry(...)` dans `collections.py` — obligatoire, puisque le GEOS du conteneur
  rejette les courbes (§2.3) ;
- étendre les schémas pydantic de `geojson.py`.

**Client (QGIS) :**
- d'abord **constater le comportement actuel** : que produit `QgsJsonExporter` sur une géométrie
  courbe — linéarisation ou géométrie nulle ? Cela dit ce qu'un QGIS non modifié renvoie
  réellement, et donc l'ampleur du dégât aujourd'hui.
- puis patcher `qgsoapifcreatefeaturerequest.cpp` / `…patchfeaturerequest` pour émettre `place`
  quand la collection annonce le profil JSON-FG. **Proposer l'extension en amont** : c'est la seule
  brique qui sorte du standard, autant qu'elle y rentre.

### 7.6 Branche `geoarrow-spike` — investigation, encodeur optionnel

§5.4 a déjà établi l'essentiel : `geoarrow.wkb` porte les arcs et **GDAL les relit** [vérifié]. Le
spike sert donc à décider si l'on paie le patch client, pas à savoir si c'est possible.

- Écrire un prototype d'encodeur (il est court : les octets de `ST_AsBinary` vont tels quels dans une
  colonne binaire `geoarrow.wkb`, format IPC *stream*) et le mesurer contre FlatGeobuf sur les axes
  de §8 — c'est le seul chiffre qui pourrait justifier de préférer Arrow.
- Chiffrer le patch QGIS d'import Arrow, et regarder l'état de la PR amont.
- Conditions de réévaluation à consigner : fusion de l'import Arrow dans QGIS, ajout du type à la
  liste blanche, apparition d'une classe de conformité OGC.

**Ne pas livrer d'encodeur en production tant qu'aucun client ne peut le consommer.**

---

## 8. Banc d'essai

Le harnais existe mais est **désactivé** : `.github/workflows/benchmark.yml.disabled`,
`tests/benchmark/time.sh` (hyperfine + curl + jq → `benchmark.dat`), `tests/benchmark/plot.py`
(plotly). **Le réactiver et l'étendre plutôt qu'en écrire un nouveau.**

### 8.1 Ce qu'il faut mesurer

| Métrique | Pourquoi elle change la décision |
|---|---|
| **Fidélité** (arcs conservés / repli / perdus) | axe de **correction**, pas de vitesse — première colonne, **ventilée par version de GDAL** |
| Octets bruts **et gzippés** | l'ordre s'inverse entre les deux (§4.1) : ne rapporter que l'un serait trompeur |
| Temps total de requête | ce que l'utilisateur perçoit |
| **Décomposition** PostGIS / middleware / HTTP | **la métrique clé de l'architecture retenue** : si le middleware domine, changer d'expression SQL ne sert à rien |
| Temps de décodage client | un format compact mais lent à parser ne sert à rien |
| Mémoire serveur crête | discriminant entre réponse en flux et tamponnée (FGB) |

### 8.2 Matrice

- **Formats** : GeoJSON (référence), GeoJSON linéarisé à tolérance, **GeoJSON à précision réduite**
  (témoin bon marché, §4.1), JSON-FG `jsonfg` et `jsonfg-plus`, FlatGeobuf (± index), GML 3.2.
- **Expression SQL de géométrie** : `ST_AsGeoJSON` contre `ST_AsBinary` + assemblage Python — c'est
  l'arbitrage architectural central, il mérite son propre axe.
- **Géométries** : celles du dépôt (`point_2056_10fields`, `line_2056_10fields`, `polygon_2056`,
  `nogeom_*`) **plus de nouvelles couches courbes** — `CIRCULARSTRING`, `COMPOUNDCURVE`,
  `CURVEPOLYGON`. `Geometry_2056` les accepte déjà sans migration (§2.2).
- **Nombre d'entités** : 1 / 10 / 10² / 10³ / 10⁴ / 10⁵ (axe existant).
- **Sommets par entité** : l'axe qui *dominerait* le résultat sur données courbes (3 contre 65 après
  linéarisation, §4.2) — doit apparaître explicitement.
- **Version de GDAL client** : 3.12 et 3.13+ seulement — axe de **correction**, pas de performance.
- **CRS** : SRID de stockage == demandé, contre `Transform`.
- Axes de moindre intérêt : nombre de propriétés, 2D/3D.

### 8.3 Outillage

Garder shell + hyperfine — en place, mesure le vrai HTTP de bout en bout, déjà branché sur la CI — et
l'étendre :

- **colonne format** dans `benchmark.dat` → une série par format dans `plot.py` ;
- coût base seul en SQL direct (méthode de §4, réutilisable telle quelle) ;
- coût middleware avec `flameprof` / `gprof2dot`, déjà dans `requirements-dev.txt` ;
- côté client, chronométrer `ogr2ogr` par format et par version de GDAL (images
  `ghcr.io/osgeo/gdal:alpine-small-<version>`, légères) ;
- pour QGIS, `test_integration_qgis.py` charge déjà une couche via le fournisseur OAPIF — harnais
  client naturel, à porter sur une image 4.x.

### 8.4 Hypothèses que le banc doit pouvoir *falsifier*

Un banc qui ne peut rien réfuter n'est qu'une décoration.

1. « Faire remonter du WKB plutôt que du GeoJSON décharge le serveur. » — **mesuré et vrai** côté
   base (facteur 74, §4.1) ; **partiellement repris par le middleware** dès qu'on matérialise des
   coordonnées (§4.3). Reste à trancher **de bout en bout**, requête HTTP comprise : c'est
   l'hypothèse qui valide ou invalide l'architecture.
2. « Le goulot est PostGIS. » — §4.1/§4.3 donnent au plus ~142 ms pour 10 000 entités côté base et
   ~35 ms côté Python pour JSON-FG. Si la requête HTTP complète est d'un ordre de grandeur au-dessus,
   **le goulot est ailleurs** (validation pydantic par entité, §2.2) et *changer de format ne réglera
   pas grand-chose*. **C'est l'hypothèse la plus importante du lot** : elle conditionne l'utilité de
   tout le reste.
3. « `jsonfg-plus` coûte cher parce qu'il transporte deux géométries. » — **mesuré côté base** :
   `place` 55 ms + repli 41 ms ≈ 96 ms/10k, contre 5 ms pour un passe-plat WKB (§4.3). Reste à
   mesurer l'effet sur le temps de réponse complet et sur les octets transmis.
4. « FlatGeobuf est plus rapide que le GeoJSON. » — à mesurer une fois l'encodeur middleware écrit ;
   les 34 ms mesurées en base ne s'appliquent pas à l'architecture retenue.
5. « Servir les arcs exacts est plus rapide que les linéariser. » — §4.2 dit oui d'un facteur ~46 en
   base ; à confirmer de bout en bout.
6. « L'index spatial FlatGeobuf coûte cher. » — à mesurer ; l'inquiétude initiale n'est pas étayée.
7. « Réduire la précision de coordonnées ne suffirait pas. » — témoin bon marché à écarter
   explicitement avant d'attribuer un gain au changement de format.

### 8.5 Reproductibilité

Graine fixe (`setseed`), préchauffage, répétitions, et **publier ce qui a été tronqué** (formats non
testés, tailles écartées) : une troncature silencieuse se lit comme une couverture complète.

---

## 9. Risques et questions ouvertes

| # | Sujet | Détail |
|---|---|---|
| R1 | **Aller-retour d'édition** | Aucun format ne le résout seul (§3.3). C'est le seul point exigeant un patch QGIS, et le seul sans réponse normative. À traiter tôt : une lecture fidèle sans écriture fidèle rend la perte *invisible*. |
| R2 | **Lecture des courbes en Python** | Le GEOS du conteneur (3.11.1) rejette le WKB courbe et `django.contrib.gis.geos` n'a pas de classe de courbe (§2.3). Un correctif maison est annoncé : **en obtenir la référence et établir le seuil de GEOS requis** — sinon le correctif Django ne suffira pas sans monter GEOS. À défaut, lecteur WKB maison (~60 lignes, 21 ms/10k). |
| R2b | **Coût de matérialisation des coordonnées** | JSON-FG impose de matérialiser les coordonnées : ~10× un passe-plat WKB (§4.3). Bon marché en absolu, mais c'est l'axe sur lequel FlatGeobuf devient préférable si le volume grandit. |
| R3 | **Version de GDAL côté client** | Plancher retenu **GDAL ≥ 3.12** (2025-11-03, antérieur à QGIS 4.0) : les quatre formats candidats sont alors fidèles, et la version de GDAL cesse d'être un critère de choix (§3.2). Reste à confirmer que les paquets QGIS visés embarquent bien ≥ 3.12 — QGIS ne déclare qu'un minimum de 3.2. |
| R4 | **Filtrage `bbox` approximatif** | `__intersects` passe par GEOS, qui strokie les courbes à 32 segments/quadrant (PostGIS #5832). À documenter. |
| R5 | **Mode dégradé par défaut** | 500 actuelle contre linéarisation configurable (§6). Décision produit, avant de coder. |
| R6 | **Aucun test amont sur les arcs** | QGIS n'a **aucune** couverture de test pour les géométries courbes via OAPIF, quel que soit le format. Les chemins sont confirmés par lecture du code et par nos essais GDAL, mais non protégés en amont : nos tests d'intégration sont le seul filet. |
| R7 | **Dépendance GDAL pour FlatGeobuf** | Vérifier si `django.contrib.gis` impose déjà libgdal ; le conteneur a `gdal-bin` mais pas les bindings Python. |
| R8 | **Conformité OGC** | Ajouter des encodages est permis. JSON-FG **a** une classe de conformité pour les arcs ; le GML à arcs n'en a **aucune** — ne pas revendiquer `gmlsf0`/`gmlsf2`. |
| R9 | **Typage GML instable** | Le `.gfs` de GDAL déduit les types par échantillonnage ; risque d'incohérence entre pages (§5.3). |
| R10 | **Image de test QGIS** | `tests/docker-compose.dev.yml` épingle `qgis/qgis:3.44-noble` — à migrer en 4.x, 3.x n'étant plus une cible. |

---

## Annexe — reproduction des mesures

### PostGIS

```bash
docker run -d --platform linux/amd64 --name probe \
  -e POSTGRES_PASSWORD=probe -e POSTGRES_DB=probe postgis/postgis:17-3.5
docker exec probe psql -U postgres -d probe -c "SELECT postgis_full_version();"
# POSTGIS="3.5.2" GEOS="3.9.0-CAPI-1.16.2" PROJ="7.2.1"

docker exec probe psql -U postgres -d probe \
  -c "SELECT ST_AsGeoJSON('CIRCULARSTRING(0 0,1 1,2 0)'::geometry);"
# ERROR:  lwgeom_to_geojson: 'CircularString' geometry type not supported

docker exec probe psql -U postgres -d probe \
  -c "SELECT encode(ST_AsBinary('CIRCULARSTRING(0 0,1 1,2 0)'::geometry),'hex');" \
  -c "SELECT ST_AsGML(3,'CIRCULARSTRING(0 0,1 1,2 0)'::geometry);" \
  -c "SELECT ST_AsText(ST_CurveN('COMPOUNDCURVE(CIRCULARSTRING(0 0,1 1,2 0),(2 0,3 0))'::geometry,1));"
```

Les mesures de §4 se reproduisent avec la même image : table de 10 000 entités via
`generate_series` + `setseed(0.42)`, `sum(length(<expression>))` pour les tailles, boucle plpgsql
« meilleur de 5 » sur `clock_timestamp()` pour les temps, `jit` et parallélisme désactivés.

### Le 500 de bout en bout

```bash
export COMPOSE_FILE="tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.arm64.yml"
docker compose up --build -d postgres django
docker compose exec django python manage.py migrate --no-input
# insérer une ligne courbe dans une collection à géométrie générique, puis :
curl -i http://0.0.0.0:7180/oapif/collections/tests.geometry_2056/items
```

### Ce que Python sait (et ne sait pas) lire

```bash
docker compose exec django python -c "
from django.contrib.gis.geos import GEOSGeometry
GEOSGeometry('CIRCULARSTRING(0 0,1 1,2 0)')"
# GEOS_ERROR: ParseException: Unknown type: 'CIRCULARSTRING'   (GEOS 3.11.1)

docker run --rm python:3.12-slim sh -c 'pip install -q shapely && python -c "
import shapely; print(shapely.geos_version_string)
shapely.from_wkt(\"CIRCULARSTRING(0 0,1 1,2 0)\")"'
# 3.13.1 ; NotImplementedError: Nonlinear geometry types are not currently supported
```

### Où sérialiser : les mesures de §4.3

Côté base — `place` JSON-FG construit en SQL, et comparaison au passe-plat (mêmes 10 000 arcs) :

```sql
-- voie B, la plus rapide des deux
SELECT jsonb_set(ST_AsGeoJSON(ST_GeomFromWKB(set_byte(ST_AsBinary(geom),1,2),2056))::jsonb,
                 '{type}','"CircularString"')
FROM bench_arc;                       -- 55,2 ms   contre   ST_AsBinary : 5,0 ms
```

Côté middleware — lecteur WKB ISO d'une soixantaine de lignes (`struct.unpack_from`, codes 8-12,
décalages ISO `+1000/+2000/+3000`), puis `json.dumps` :

```
ARCS (CircularString, 3 pts), 10 000 entites    LINEAIRE (LineString, 50 pts), 10 000 entites
  parse WKB -> dict            21,0 ms            parse WKB -> dict            177,0 ms
  parse + json.dumps           35,2 ms            parse + json.dumps           448,0 ms
  hex tel quel dans du JSON     2,2 ms            hex tel quel dans du JSON     28,1 ms
```

⚠️ Les temps PostGIS sont sous **émulation amd64**, les temps Python en **arm64 natif** : comparer
uniquement à l'intérieur de chaque colonne.

### GDAL — fidélité des arcs par format et par version

```bash
for v in 3.10.3 3.11.3 3.12.0; do
docker run --rm ghcr.io/osgeo/gdal:alpine-small-$v sh -c '
cd /tmp
printf "%s\n" "id,wkt" "1,\"CIRCULARSTRING(0 0,1 1,2 0)\"" > s.csv

# FlatGeobuf et GML : arcs conservés dès 3.10
ogr2ogr -f FlatGeobuf o.fgb -lco SPATIAL_INDEX=NO -oo GEOM_POSSIBLE_NAMES=wkt s.csv
ogrinfo -al o.fgb | grep CIRCULAR

# JSON-FG : dépend de la version (repli < 3.12, arc réel >= 3.12)
cat > fg.json <<EOF
{"type":"FeatureCollection",
 "conformsTo":["http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs"],
 "features":[{"type":"Feature","id":1,
   "place":{"type":"CircularString","coordinates":[[0,0],[1,1],[2,0]]},
   "geometry":{"type":"LineString","coordinates":[[0,0],[1,1],[2,0]]},
   "properties":{}}]}
EOF
ogrinfo --version; ogrinfo -al fg.json 2>&1 | grep -iE "CIRCULARSTRING|LINESTRING|warning"
'; done
```

Encodage JSON-FG canonique, obtenu en faisant écrire GDAL, et preuve que l'Arrow linéarise :

```bash
docker run --rm ghcr.io/osgeo/gdal:alpine-small-3.12.0 sh -c '
cd /tmp; printf "%s\n" "id,wkt" "1,\"CURVEPOLYGON(CIRCULARSTRING(0 0,4 0,4 4,0 4,0 0))\"" > s.csv
ogr2ogr -f JSONFG out.json -oo GEOM_POSSIBLE_NAMES=wkt s.csv && cat out.json'

docker run --rm ghcr.io/osgeo/gdal:ubuntu-full-latest sh -c '
cd /tmp; printf "%s\n" "id,wkt" "1,\"CIRCULARSTRING(0 0,1 1,2 0)\"" > s.csv
ogr2ogr -f Arrow a.arrow -lco GEOMETRY_ENCODING=WKB -nlt CIRCULARSTRING -a_srs EPSG:2056 \
        -oo GEOM_POSSIBLE_NAMES=wkt s.csv'
# Warning 1: Attempt to write curve geometries to layer arc that does not support them.
#            They will be linearized
```

…mais GDAL sait **lire** un `geoarrow.wkb` courbe fabriqué à la main. Écrire le fichier avec pyarrow
(colonne `binary` + métadonnée `ARROW:extension:name = geoarrow.wkb`, remplie avec le WKB ISO de
`ST_AsBinary`), puis :

```bash
docker run --rm -v "$PWD:/probe" python:3.12-slim \
  sh -c 'pip install -q pyarrow && python /probe/mk_geoarrow.py'
for v in 3.13.2 latest; do   # 'latest' = 3.14.0dev = master
  docker run --rm -v "$PWD:/probe" ghcr.io/osgeo/gdal:ubuntu-full-$v ogrinfo -al /probe/hand.arrows
done
#   name (String) = arc           CIRCULARSTRING (0 0,1 1,2 0)
#   name (String) = curvepolygon  CURVEPOLYGON (CIRCULARSTRING (0 0,4 0,4 4,0 4,0 0))
```

Cause de l'asymétrie écriture/lecture, dans le source de `master` :

```bash
# le pilote Arrow ne déclare pas OLCCurveGeometries…
curl -s https://raw.githubusercontent.com/OSGeo/gdal/master/ogr/ogrsf_frmts/arrow_common/ograrrowwriterlayer.hpp \
  | sed -n '2394,2412p'
# …et ogr2ogr linéarise en amont du pilote sur la foi de ce drapeau
curl -s https://raw.githubusercontent.com/OSGeo/gdal/master/apps/ogr2ogr_lib.cpp \
  | sed -n '5844,5845p;7300,7312p'
```

### QGIS — code source

```bash
# négociation de format et liste blanche des types de médias
curl -s https://raw.githubusercontent.com/qgis/QGIS/master/src/providers/wfs/oapif/qgsoapifcollection.cpp \
  | sed -n '85,120p'

# le membre JSON "profile" est un tableau
curl -s https://raw.githubusercontent.com/qgis/QGIS/master/src/providers/wfs/oapif/qgsoapifutils.cpp \
  | sed -n '70,85p'

# l'écriture part en application/geo+json, sans alternative
curl -s https://raw.githubusercontent.com/qgis/QGIS/master/src/providers/wfs/oapif/qgsoapifcreatefeaturerequest.cpp \
  | grep -nE 'sendPOST|exportFeatureToJsonObject'

# contrat de protocole de QGIS Server (à copier pour FlatGeobuf)
curl -s https://raw.githubusercontent.com/qgis/QGIS/master/src/server/services/wfs3/qgswfs3handlers.cpp \
  | grep -nE 'flatgeobuf|SPATIAL_INDEX|rel=.next'
```

### Sources normatives

- **JSON-FG 1.0 (OGC 21-045r1)** — classe de conformité *Circular Arcs*
  (`http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs`), membre `place`, géométrie de
  repli dans `geometry`, négociation par profil : <https://docs.ogc.org/is/21-045r1/21-045r1.html>
- **OGC API - Features Part 1 (17-069r4)** — encodages non obligatoires, arcs hors périmètre de
  GeoJSON, exigence 15 sur les liens `rel="items"` : <https://docs.ogc.org/is/17-069r4/17-069r4.html>
- Profil GML Simple Features restreint au linéaire :
  `ogcapi-features/core/standard/clause_8_encodings.adoc`
- **GeoArrow** — liste close des noms d'extension, dont `geoarrow.wkb` :
  <https://github.com/geoarrow/geoarrow/blob/main/extension-types.md>
