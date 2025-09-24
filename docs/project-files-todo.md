# Project Files To-Do

## Backend
- [x] Implement `GET /project/{project_id}/files` returning per-file metadata sourced from `projects/<id>/assets`.
- [x] Replace current upload route with `POST /project/{project_id}/files` supporting multi-file uploads and strict path validation.
- [x] Add `GET /project/{project_id}/files/{path}` for secure download/preview and guard against traversal.
- [x] Add `DELETE /project/{project_id}/files/{path}` and optional rename/move support (`PUT`).
- [x] Wire filesystem monitor events into the session WebSocket (or a dedicated channel) to broadcast file CRUD updates.
- [x] Emit structured file-update events alongside existing project/run broadcasts for UI consistency.

## Frontend
- [x] Create a MobX `projectFilesStore` that loads listings, tracks operations, and applies WebSocket diffs.
- [x] Connect the Project Files panel to the store: list files, show upload state, and surface error toasts.
- [x] Implement upload workflows (modal/drag-drop) calling the new `POST` endpoint with optimistic feedback.
- [x] Add per-file actions (download, delete, rename) with confirmation flows and store updates.
- [x] Ensure project switching triggers store refresh and handles stale selections gracefully.
- [x] Handle WebSocket disconnect/polling fallbacks for keeping the file list current.

## Operations & Safety
- [x] Enforce file size/type allowlists and per-project quota limits; surface user-facing errors.
- [x] Add audit logging for file mutations and decide on soft-delete retention strategy.
- [x] Harden the filesystem watcher (debounce per project, recover on startup, ignore `.deleted`).
- [ ] Cover new endpoints with API/e2e tests, including quota failures and WebSocket message assertions.
