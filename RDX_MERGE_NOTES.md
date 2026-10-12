# RDX feature integration notes

This build ports the RDX primary-button styling, lossless/source-aware media delivery helper, and TMDB backdrop toggle into the VJ-based codebase. Existing IMDb metadata remains enabled/controlled by the existing IMDb setting; TMDB backdrop is an independent setting.

## Added/modified
- `button_style.py`: RDX color styling for inline buttons (primary blue, success green, danger red).
- `media_delivery.py`: RDX source-message copy and thumbnail-preserving delivery helper.
- `database/tmdb_client.py`: RDX TMDB search/image helper.
- `info.py`: RDX channel/owner link defaults, bin channel default, expanded language tokens, `TMDB_BACKDROP`, and URL fallback.
- `database/users_chats_db.py`: new `tmdb_backdrop` group setting default.
- `utils.py`: backward-compatible `tmdb_backdrop` default for existing groups.
- `plugins/commands.py`: use source-aware thumbnail delivery for primary file delivery routes; RDX user-facing links.
- `plugins/pm_filter.py`: TMDB backdrop toggle and backdrop artwork on search results; IMDb metadata remains.
- Other Python UI/caption strings: VJ public channel/owner labels and links changed to RDX branding, while explicit upstream attribution comments are retained.

## Important deployment settings
- Set `URL` to your actual Heroku web app base URL; this build uses `https://rdxmovieseriesbot.herokuapp.com/` only as a fallback and it may need to be changed to your deployed app's exact domain.
- `BIN_CHANNEL`, `CHANNELS`, `LOG_CHANNEL`, and `REQST_CHANNEL` have RDX source defaults but explicit Heroku config vars take precedence. Confirm the bot has the required permissions in those channels before deploying.
- `TMDB_BACKDROP` environment variable can enable the backdrop setting default; group admins can also toggle it in `/settings`.

## Verification status
Static syntax/import-structure checks only; no live Telegram, Heroku, MongoDB, or stream-server integration test was possible here.
