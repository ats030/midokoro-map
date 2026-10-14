# Third-party code and dependencies

No project-wide open-source reuse license has been selected for the original application code in this publication. Third-party components retain their respective terms.

| Component | Scope | License and evidence |
| --- | --- | --- |
| Leaflet 1.9.4 | `frontend/vendor/leaflet*`, associated images | BSD-2-Clause. [Bundled notice](frontend/vendor/leaflet-LICENSE), [upstream](https://github.com/Leaflet/Leaflet/blob/v1.9.4/LICENSE). |
| Leaflet.markercluster 1.5.3 | `frontend/vendor/leaflet.markercluster.js`, `MarkerCluster*.css` | MIT. [Bundled notice](frontend/vendor/markercluster-LICENSE), [upstream](https://github.com/Leaflet/Leaflet.markercluster/blob/v1.5.3/MIT-LICENCE.txt). |
| modernc.org/sqlite v1.29.10 | Go dependency installed separately | BSD-3-Clause. [Retained notice](docs/sqlite-LICENSE), [upstream](https://gitlab.com/cznic/sqlite/-/blob/v1.29.10/LICENSE). |
| Go | Local build and tests; runtime not repackaged | BSD-3-Clause and dependency notices. [Go license](https://go.dev/LICENSE). |
| Playwright 1.61.0 | Installed separately for local capture | Apache-2.0. [Upstream](https://github.com/microsoft/playwright/blob/main/LICENSE). |
| Pillow 12.2.0 | Installed separately for local GIF generation | MIT-CMU. [Upstream](https://github.com/python-pillow/Pillow/blob/main/LICENSE). |
| pytest 9.1.1 | Installed separately for audit regressions | MIT. [Upstream](https://github.com/pytest-dev/pytest/blob/main/LICENSE). |

Go modules are pinned in `go.mod` and `go.sum`. Their distributions and transitive dependency licenses are obtained through the normal Go module installation, not repackaged here.

The fixture entries, descriptions, polygons, and background tiles are original synthetic material. No production catalog database, production-catalog photograph, map tile dataset, model weights, or summary cache is bundled. Existing source HTML for the application's themed pages is retained with its source links; those pages are not part of the offline fixture walkthrough.

The original application can use OpenStreetMap tiles, Wikipedia, Commons, other external data APIs, and a local language model. Their attribution and service terms remain applicable when those features are used. This publication does not grant API access or change hosting plans. The local fixture walkthrough substitutes synthetic background tiles and labels them explicitly.

Review date: 2026-10-14. See [publication-license-review.json](docs/publication-license-review.json) for the scoped license decisions.

## Story photographs

The following Commons-provided 960px thumbnails are distributed unchanged, without cropping, under the individually stated licenses. These photo licenses do not apply to the application code.

- `/stories/photos/cape-muroto.jpg`: Motokoka, [File:Cape Muroto, Muroto city 01.jpg](https://commons.wikimedia.org/wiki/File:Cape_Muroto,_Muroto_city_01.jpg), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- `/stories/photos/kuniga-coast.jpg`: Yuvalr, [File:Matengai Cliff at Kuniga coast, Nishinoshima.jpg](https://commons.wikimedia.org/wiki/File:Matengai_Cliff_at_Kuniga_coast,_Nishinoshima.jpg), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- `/stories/photos/tedori-gorge.jpg`: 紫煙, [File:Tedorikyou.jpg](https://commons.wikimedia.org/wiki/File:Tedorikyou.jpg), [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- `/stories/photos/hara-castle.jpg`: shikabane taro, [File:原城跡 - panoramio (2).jpg](https://commons.wikimedia.org/wiki/File:%E5%8E%9F%E5%9F%8E%E8%B7%A1_-_panoramio_(2).jpg), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
