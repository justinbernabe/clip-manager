# clip-manager — the editor layer

`clip-manager` is a fork of [MediaCMS](https://github.com/mediacms-io/mediacms)
that adds a **non-destructive, in-browser clip editor** on top of MediaCMS's
upload → transcode → serve pipeline. It's deployed in the JabLab homelab as the
GameDVR portal (`gamedvr.jabflix.net`).

This doc is the architecture + roadmap. It's grounded in what MediaCMS actually
gives us, so we extend the framework instead of fighting it.

## What MediaCMS already provides (and we reuse)

| Capability | Where | How we use it |
|---|---|---|
| Upload, library, web player, users, sharing | `files/`, `frontend/` | The shell. The editor is a new surface inside it. |
| Transcoding pipeline (Celery + ffmpeg) | `files/tasks.py`, `files/helpers.py` | A rendered clip is just a **new `Media`** — saving it auto-encodes. |
| In-place **trim** (single/multi-segment cut + concat) | `files/helpers.py::trim_video_method`, `files/views/pages.py::trim_video`, `api/v1/media/<token>/trim_video` | We reuse the **segment-cut + concat** ffmpeg recipe, but render to a **new** file/Media instead of overwriting the source. |
| `Media.save()` → `post_save` → `media_init()` → `encode()` | `files/models/media.py` | Create a `Media` with the rendered file, `save()`, done — encoding + thumbnails + HLS happen for free. |
| ffmpeg command runner | `files/helpers.py::run_command` | All editor ffmpeg work goes through it. |

**Design rule:** the editor never mutates a source clip. Every render produces a
new `Media`. The source stays pristine; edits are re-render-able from their EDL.

## The model: a project + an EDL

A user edits a **project**, not a file. A project holds an **Edit Decision List**
(EDL) — an ordered list of operations against one or more source clips. Rendering
walks the EDL, drives ffmpeg, and emits a new `Media`.

```
EditProject
  owner        -> users.User
  title
  status       draft | rendering | done | failed
  edl          JSON   (the timeline; see schema below)
  output_media -> files.Media  (set when a render completes)
```

EDL schema (versioned — `v1` implemented, later ops are additive):

```jsonc
{
  "version": 1,
  "tracks": [
    {
      "kind": "video",                 // video | overlay | text  (P3+)
      "clips": [
        { "source": "<friendly_token>", // a source Media
          "in": "00:00:03.0",           // timestamps, ffmpeg-style
          "out": "00:00:09.5",
          "transition_in":  null,       // P4: fade | dissolve | cut
          "transition_out": null }
      ]
    }
  ],
  "overlays": [],                       // P3: {type:image|text, ...}
  "output": { "format": "mp4" }
}
```

## Roadmap

| Phase | Scope | State |
|---|---|---|
| **P1 — Cut & assemble → new clip** | Single track: pick in/out across one or more source clips, concat in order, render to a **new** `Media`. Reuses MediaCMS's proven `-ss/-t -c copy` + concat recipe (stream-copy = fast, lossless). REST API end-to-end. | **Implemented** (`clip_editor/`) — backend MVP |
| **P2 — Montage across clips** | Multi-source timeline, re-encode path for mismatched codecs/resolutions (concat demuxer needs uniform streams; fall back to filter_complex concat). | Scaffolded (render.py has the seam) |
| **P3 — Overlays & text** | Image/logo overlays, text/captions via ffmpeg `overlay` / `drawtext`. Forces a re-encode track. | Designed (EDL `overlays`, `text` track) |
| **P4 — Transitions + timeline UI** | `xfade`/`acrossfade` transitions; the React timeline editor in `frontend/` (scrubber, in/out handles, drag clips, live preview). | Designed |

## Where the code lives

| Piece | Path |
|---|---|
| Editor Django app (models, API, render) | `clip_editor/` |
| ffmpeg EDL → file renderer (pure, testable) | `clip_editor/render.py` |
| Celery render task (creates the new `Media`) | `clip_editor/tasks.py` |
| REST API (`/api/v1/editor/...`) | `clip_editor/urls.py`, `clip_editor/views.py` |
| Timeline UI (P4) | `frontend/src/static/js/components/editor/` (new) |
| App registration | `cms/settings.py` INSTALLED_APPS, `cms/urls.py` |

## API (P1)

```
POST /api/v1/editor/projects                 create a project (title, edl)
GET  /api/v1/editor/projects                 list my projects
GET  /api/v1/editor/projects/<id>            project + status + output token
PATCH/api/v1/editor/projects/<id>            update the EDL (draft only)
POST /api/v1/editor/projects/<id>/render     kick off a render (-> Celery)
```

Render is async: `render` returns `202` + status `rendering`; poll the project
until `status=done`, then `output_media` is the playable clip's friendly_token.

## Build & deploy

The fork ships as a Docker image to GHCR (`.github/workflows/build-image.yml` →
`ghcr.io/justinbernabe/clip-manager`). The JabLab `mediacms` stack swaps its
`image:` from `mediacms/mediacms:latest` to the GHCR tag — nothing else changes.

## License

MediaCMS is AGPL-3.0; this fork inherits it. The deployed portal serves personal
game clips, and per AGPL the modified source is the public repo you're reading.
